# Copyright (c) farm-ng, inc.
#
# Licensed under the Amiga Development Kit License (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/farm-ng/amiga-dev-kit/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import uvicorn
from farm_ng.core.event_client import EventClient
from farm_ng.core.event_service_pb2 import EventServiceConfigList
from farm_ng.core.event_service_pb2 import SubscribeRequest
from farm_ng.core.events_file_reader import proto_from_json_file
from farm_ng.core.uri_pb2 import Uri
from fastapi import FastAPI
from fastapi import WebSocket, Request, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.protobuf.json_format import MessageToJson
from functools import reduce

import open3d as o3d
import sys


import importlib

sys.path.append(
    f"/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/sick_scan_ws/sick_scan_xd/python/api"
)

sick_scan_api = importlib.import_module("sick_scan_api")

from sick_scan_api import *

# Load sick_scan_library
sick_scan_library = SickScanApiLoadLibrary(
    [
        "build/",
        "build_linux/",
        "../../build/",
        "../../build_linux/",
        "./",
        "../",
        "/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/sick_scan_ws/build/",
    ],
    "libsick_scan_xd_shared_lib.so",
)

logger = logging.getLogger("uvicorn")


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

templates = Jinja2Templates(
    "/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/templates"
)


@app.get("/simple_lidar")
async def simple_lidar(request: Request):
    return templates.TemplateResponse("simple_lidar.html", {"request": request})


# to store the events clients
clients: dict[str, EventClient] = {}


@app.get("/list_uris")
async def list_uris() -> JSONResponse:
    """Coroutine to list all the uris from all the event services

    Returns:
        JSONResponse: the list of uris as a json.

    Usage:
        curl -X GET "http://localhost:8042/list_uris"
    """
    all_uris = {}

    for service_name, client in clients.items():
        # get the list of uris from the event service
        uris: list[Uri] = []
        try:
            # NOTE: some services may not be available, so we need to handle the timeout
            uris = await asyncio.wait_for(client.list_uris(), timeout=0.1)
        except asyncio.TimeoutError:
            continue

        # convert the uris to a dict, where the key is the uri full path
        # and the value is the uri proto as a json string
        for uri in uris:
            all_uris[f"{service_name}{uri.path}"] = json.loads(MessageToJson(uri))

    return JSONResponse(content=all_uris, status_code=200)


@app.websocket("/subscribe/{service_name}/{uri_path}")
async def subscribe(
    websocket: WebSocket, service_name: str, uri_path: str, every_n: int = 1
):
    """Coroutine to subscribe to an event service via websocket.

    Args:
        websocket (WebSocket): the websocket connection
        service_name (str): the name of the event service
        uri_path (str): the uri path to subscribe to
        every_n (int, optional): the frequency to receive events. Defaults to 1.

    Usage:
        ws = new WebSocket("ws://localhost:8042/subscribe/oak0/left
    """

    client: EventClient = clients[service_name]

    await websocket.accept()

    if service_name == "lidar" and uri_path == "data":
        lidar_buffer = []

    try:

        async for _, message in client.subscribe(
            request=SubscribeRequest(uri=Uri(path=f"/{uri_path}"), every_n=every_n),
            decode=True,
        ):
            # print(f"Received message.")

            if service_name == "lidar" and uri_path == "data":
                lidar_buffer.append(message)

            await websocket.send_json(MessageToJson(message))

        await websocket.close()
    except WebSocketDisconnect:
        print("WebSocket disconnected remotely")

        print("finished")
        if service_name == "lidar" and uri_path == "data":
            logger.info("sending buffer to ply creator")
            await create_ply_file_from_buffer(lidar_buffer)
        # print(lidar_buffer)


def pySickScanCartesianPointCloudMsgToXYZ(pointcloud_msg):
    # get pointcloud fields
    num_fields = pointcloud_msg.fields.size
    msg_fields_buffer = pointcloud_msg.fields.buffer
    field_offset_x = -1
    field_offset_y = -1
    field_offset_z = -1
    for n in range(num_fields):
        field_name = ctypesCharArrayToString(msg_fields_buffer[n].name)
        field_offset = msg_fields_buffer[n].offset
        if field_name == "x":
            field_offset_x = msg_fields_buffer[n].offset
        elif field_name == "y":
            field_offset_y = msg_fields_buffer[n].offset
        elif field_name == "z":
            field_offset_z = msg_fields_buffer[n].offset
    # Extract x,y,z
    cloud_data_buffer_len = (
        pointcloud_msg.row_step * pointcloud_msg.height
    )  # length of polar cloud data in byte
    assert (
        pointcloud_msg.data.size == cloud_data_buffer_len
        and field_offset_x >= 0
        and field_offset_y >= 0
        and field_offset_z >= 0
    )
    cloud_data_buffer = bytearray(cloud_data_buffer_len)
    for n in range(cloud_data_buffer_len):
        cloud_data_buffer[n] = pointcloud_msg.data.buffer[n]
    points_x = np.zeros(pointcloud_msg.width * pointcloud_msg.height, dtype=np.float32)
    points_y = np.zeros(pointcloud_msg.width * pointcloud_msg.height, dtype=np.float32)
    points_z = np.zeros(pointcloud_msg.width * pointcloud_msg.height, dtype=np.float32)
    point_idx = 0
    for row_idx in range(pointcloud_msg.height):
        for col_idx in range(pointcloud_msg.width):
            # Get lidar point in polar coordinates (range, azimuth and elevation)
            pointcloud_offset = (
                row_idx * pointcloud_msg.row_step + col_idx * pointcloud_msg.point_step
            )
            points_x[point_idx] = np.frombuffer(
                cloud_data_buffer,
                dtype=np.float32,
                count=1,
                offset=pointcloud_offset + field_offset_x,
            )[0]
            points_y[point_idx] = np.frombuffer(
                cloud_data_buffer,
                dtype=np.float32,
                count=1,
                offset=pointcloud_offset + field_offset_y,
            )[0]
            points_z[point_idx] = np.frombuffer(
                cloud_data_buffer,
                dtype=np.float32,
                count=1,
                offset=pointcloud_offset + field_offset_z,
            )[0]
            point_idx = point_idx + 1
    return points_x, points_y, points_z


# TODO: Finish implementing this.
def from_proto(protocol_message):

    header = SickScanHeader(
        seq=protocol_message.header.seq,
        timestamp_sec=protocol_message.header.timestamp_sec,
        timestamp_nsec=protocol_message.header.timestamp_nsec,
        frame_id=protocol_message.header.frame_id,
    )

    elements = []
    num_fields = protocol_message.fields.size

    for n in range(num_fields):
        field = SickScanPointFieldMsg(
            name=protocol_message.fields[n].name,
            offset=protocol_message.fields[n].offset,
            datatype=protocol_message.fields[n].datatype,
            count=protocol_message.fields[n].count,
        )
        elements.append(field)

    fields = SickScanPointFieldArray(
        capacity=protocol_message.fields.capacity,
        size=protocol_message.fields.size,
        buffer=elements,
    )

    data = SickScanUint8Array(
        capacity=protocol_message.capacity,
        size=protocol_message.data.size,
        buffer=protocol_message.data.buffer,
    )

    message_contents = SickScanPointCloudMsg(
        header=header,
        height=protocol_message.height,
        width=protocol_message.width,
        fields=fields,
        is_bigendian=protocol_message.is_bigendian,
        point_step=protocol_message.point_step,
        row_step=protocol_message.row_step,
        data=data,
        is_dense=protocol_message.is_dense,
        num_echoes=protocol_message.num_echoes,
        segment_idx=protocol_message.segment_idx,
    )

    return message_contents


async def create_ply_file_from_buffer(lidar_buffer):

    # xyz = np.random.rand(100, 3)

    logger.info("creating ply")

    list_of_points = []
    for read in lidar_buffer:
        message = from_proto(read)
        xyz = pySickScanCartesianPointCloudMsgToXYZ(message)
        list_of_points.extend(xyz)

    logger.info(f"number of points: {len(list_of_points)}")

    xyz = np.array(list_of_points)

    logger.info(xyz)
    logger.info(xyz.shape)

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(xyz)
    filename = f'/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/lidar_{datetime.now().strftime("%Y%m%d%H%M%S")}.ply'
    logger.info(filename)
    o3d.io.write_point_cloud(filename, pcd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True, help="config file")
    parser.add_argument("--port", type=int, default=8042, help="port to run the server")
    parser.add_argument("--debug", action="store_true", help="debug mode")
    args = parser.parse_args()

    # NOTE: we only serve the react app in debug mode
    if not args.debug:
        react_build_directory = Path(__file__).parent / "ts" / "dist"

        app.mount(
            "/",
            StaticFiles(directory=str(react_build_directory.resolve()), html=True),
        )

    # config list with all the configs
    config_list: EventServiceConfigList = proto_from_json_file(
        args.config, EventServiceConfigList()
    )

    for config in config_list.configs:
        if config.port == 0:
            continue  # skip invalid service configs
        # create the event client
        client = EventClient(config=config)

        # add the client to the clients dict
        clients[config.name] = client

    # run the server
    uvicorn.run(app, host="0.0.0.0", port=args.port)  # noqa: S104
