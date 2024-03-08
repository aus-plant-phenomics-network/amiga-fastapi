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
import argparse
import asyncio
import logging
from pathlib import Path
import os
import sys
import grpc
import numpy as np
from farm_ng.core.event_pb2 import Event
from farm_ng.core.event_service import EventServiceGrpc
from farm_ng.core.event_service_pb2 import EventServiceConfig
from farm_ng.core.events_file_reader import proto_from_json_file
from google.protobuf.empty_pb2 import Empty
from google.protobuf.message import Message

import lidar_pb2

"""Minimalistic usage example for sick_scan_api

Usage: minimum_sick_scan_api_client.py launchfile

Example:
    export LD_LIBRARY_PATH=.:./build:$LD_LIBRARY_PATH
    export PYTHONPATH=.:./python/api:$PYTHONPATH
    python3 ./examples/python/minimum_sick_scan_api_client.py ./launch/sick_tim_7xx.launch

See doc/sick_scan_api/sick_scan_api.md for further information.

"""

import os

# Add paths to LD_LIBRARY_PATH and PYTHONPATH
os.environ["LD_LIBRARY_PATH"] = (
    f"/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/sick_scan_ws/build"
)
os.environ["PYTHONPATH"] = (
    f"/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/sick_scan_ws/sick_scan_xd/python/api"
)


print(os.environ["PYTHONPATH"])


# Make sure sick_scan_api is searched in all folders configured in environment variable PYTHONPATH
def appendPythonPath():
    pythonpath = os.environ["PYTHONPATH"]
    print(os.environ["PYTHONPATH"])
    for folder in pythonpath.split(";"):
        sys.path.append(os.path.abspath(folder))
    print(sys.path)


try:
    # import sick_scan_api
    from sick_scan_api import *
except ModuleNotFoundError:
    print(
        "import sick_scan_api failed, module sick_scan_api not found, trying with importlib..."
    )
    appendPythonPath()
    import importlib

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


# Convert a SickScanCartesianPointCloudMsg to points
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


class LIDARServer:
    """A simple service that implements the AddTwoInts service."""

    def __init__(self, event_service: EventServiceGrpc) -> None:
        """Initialize the service.

        Args:
            event_service: The event service to use for communication.
        """
        self._event_service = event_service
        self._event_service.add_request_reply_handler(self.request_reply_handler)

        self._counter = 0

    @property
    def logger(self) -> logging.Logger:
        """Return the logger for this service."""
        return self._event_service.logger

    async def request_reply_handler(self, event: Event, message: Message) -> None:
        """The callback for handling request/reply messages."""
        if event.uri.path == "/reset_counter":
            self._counter = 0

        return Empty()

    async def run(self) -> None:
        """Run the main task."""
        global lidar_buffer

        lidar_buffer = []

        # Create a sick_scan instance and initialize a TiM-7xx
        api_handle = SickScanApiCreate(sick_scan_library)
        SickScanApiInitByLaunchfile(sick_scan_library, api_handle, cli_args_for_sick)

        def pySickScanCartesianPointCloudMsgCallback(api_handle, msg):
            global lidar_buffer
            """
            Implement a callback to process pointcloud messages
            Data processing to be done
            """
            # print(
            #     "Python PointCloudMsgCb: {} x {} pointcloud message received".format(
            #         msg.contents.width, msg.contents.height
            #     )
            # )
            # print(f"There are {msg.contents.fields.size} fields.")
            # for n in range(msg.contents.fields.size):
            #     field_name = ctypesCharArrayToString(msg.contents.fields.buffer[n].name)
            #     print(field_name)
            if len(lidar_buffer) == 0:
                xyz = pySickScanCartesianPointCloudMsgToXYZ(msg.contents)
                lidar_buffer.append(xyz)

        # Register for pointcloud messages
        cartesian_pointcloud_callback = SickScanPointCloudMsgCallback(
            pySickScanCartesianPointCloudMsgCallback
        )
        SickScanApiRegisterCartesianPointCloudMsg(
            sick_scan_library, api_handle, cartesian_pointcloud_callback
        )

        # count = 0
        while True:
            # print("Lidar buffer", type(lidar_buffer), lidar_buffer)

            if len(lidar_buffer) > 0:
                new_read = lidar_buffer.pop()

                point_cloud = lidar_pb2.GetLIDARResponse()

                for i in range(0, len(new_read[0])):
                    point = point_cloud.points.add()
                    point.x = new_read[0][i]
                    point.y = new_read[1][i]
                    point.z = self._counter  # new_read[2][i]

                await self._event_service.publish("/data", point_cloud)
                # only increase counter when data is sent to stop z-stretching
                self._counter += 1
            #await asyncio.sleep(1)
            # count += 1

        SickScanApiDeregisterCartesianPointCloudMsg(
            sick_scan_library, api_handle, cartesian_pointcloud_callback
        )
        SickScanApiClose(sick_scan_library, api_handle)
        SickScanApiRelease(sick_scan_library, api_handle)
        SickScanApiUnloadLibrary(sick_scan_library)

    async def serve(self) -> None:
        await asyncio.gather(self._event_service.serve(), self.run())

    # TODO: Add a "on killed or stopped" service function

    # Close lidar and release sick_scan api
    # SickScanApiDeregisterCartesianPointCloudMsg(sick_scan_library, api_handle, cartesian_pointcloud_callback)
    # SickScanApiClose(sick_scan_library, api_handle)
    # SickScanApiRelease(sick_scan_library, api_handle)
    # SickScanApiUnloadLibrary(sick_scan_library)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="farm-ng-service")
    parser.add_argument(
        "--service-config", type=Path, required=True, help="The service config."
    )
    parser.add_argument(
        "--lidar_address", type=str, required=True, help="The Lidar IP address"
    )

    args = parser.parse_args()

    cli_args_for_sick = f"/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/sick_scan_ws/sick_scan_xd/launch/sick_lms_4xxx.launch hostname:={args.lidar_address}"

    # load the service config
    service_config: EventServiceConfig = proto_from_json_file(
        args.service_config, EventServiceConfig()
    )

    # create the grpc server
    event_service: EventServiceGrpc = EventServiceGrpc(
        grpc.aio.server(), service_config
    )

    loop = asyncio.get_event_loop()

    try:
        # wrap and run the service
        loop.run_until_complete(LIDARServer(event_service).serve())
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        loop.close()
