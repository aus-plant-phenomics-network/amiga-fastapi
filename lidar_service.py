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
import datetime
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
from collections import deque

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
# os.environ["LD_LIBRARY_PATH"] = (
#     f"/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/sick_scan_ws/build"
# )

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


def to_proto(message_contents):
    message_for_pb = lidar_pb2.SickScanPointCloudMsg()

    message_for_pb.height = message_contents.height
    message_for_pb.width = message_contents.width
    message_for_pb.is_bigendian = message_contents.is_bigendian
    message_for_pb.point_step = message_contents.point_step
    message_for_pb.row_step = message_contents.row_step
    message_for_pb.is_dense = message_contents.is_dense
    message_for_pb.num_echos = message_contents.num_echos
    message_for_pb.segment_idx = message_contents.segment_idx

    header_for_pb = lidar_pb2.SickScanPointCloudMsg.SickScanHeader()
    header_for_pb.seq = message_contents.header.seq
    header_for_pb.timestamp_sec = message_contents.header.timestamp_sec
    header_for_pb.timestamp_nsec = message_contents.header.timestamp_nsec
    header_for_pb.frame_id = bytes(message_contents.header.frame_id)

    data_for_pb = lidar_pb2.SickScanPointCloudMsg.SickScanUint8Array()
    data_for_pb.capacity = message_contents.data.capacity
    data_for_pb.size = message_contents.data.size
    data_for_pb.buffer = bytes(message_contents.data.buffer)

    fields_for_pb = lidar_pb2.SickScanPointCloudMsg.SickScanPointFieldArray()

    fields_for_pb.capacity = message_contents.fields.capacity
    fields_for_pb.size = message_contents.fields.size

    num_fields = message_contents.fields.size
    msg_fields_buffer = message_contents.fields.buffer

    for n in range(num_fields):

        field_message_for_pb = lidar_pb2.SickScanPointCloudMsg.SickScanPointFieldMsg()
        field_message_for_pb.name = msg_fields_buffer[n].name
        field_message_for_pb.offset = msg_fields_buffer[n].offset
        # TODO: is this right?
        field_message_for_pb.datatype = 0  # msg_fields_buffer[n].datatype
        field_message_for_pb.count = 0  # msg_fields_buffer[n].count
        fields_for_pb.buffer.append(field_message_for_pb)

    message_for_pb.header.CopyFrom(header_for_pb)
    message_for_pb.data.CopyFrom(data_for_pb)
    message_for_pb.fields.CopyFrom(fields_for_pb)

    return message_for_pb


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
        global lidar_buffer, last_published, count, times

        times = []

        lidar_buffer = deque(maxlen=1)
        last_published = datetime.datetime.now() - datetime.timedelta(seconds=0.5)
        count = 0

        # Create a sick_scan instance and initialize a TiM-7xx
        api_handle = SickScanApiCreate(sick_scan_library)
        SickScanApiInitByLaunchfile(sick_scan_library, api_handle, cli_args_for_sick)

        # def pySickScanCartesianPointCloudMsgCallback(api_handle, msg):
        #     # global lidar_buffer
        #     global last_read
        #     """
        #     Implement a callback to process pointcloud messages
        #     Data processing to be done
        #     """
        #     # print(
        #     #     "Python PointCloudMsgCb: {} x {} pointcloud message received".format(
        #     #         msg.contents.width, msg.contents.height
        #     #     )
        #     # )
        #     # print(f"There are {msg.contents.fields.size} fields.")
        #     # for n in range(msg.contents.fields.size):
        #     #     field_name = ctypesCharArrayToString(msg.contents.fields.buffer[n].name)
        #     #     print(field_name)
        #     # if len(lidar_buffer) == 0:
        #
        #     xyz = pySickScanCartesianPointCloudMsgToXYZ(msg.contents)
        #     lidar_buffer.append(xyz)
        # last_read = xyz  # msg.contents

        def pySickScanCartesianPointCloudMsgCallback(api_handle, pointcloud_msg):
            global lidar_buffer, last_published, count, times
            pointcloud_msg = (
                pointcloud_msg.contents
            )  # dereference msg pointer (pointcloud_msg = pointcloud_msg[0])
            # Note: Pointcloud conversion and visualization consumes cpu time, therefore we convert and publish the cartesian pointcloud with low frequency.
            # cur_timestamp = datetime.datetime.now()
            # if cur_timestamp >= last_published + datetime.timedelta(seconds=0.5):
            # xyz = pySickScanCartesianPointCloudMsgToXYZ(pointcloud_msg)
            # last_published = cur_timestamp

            # TODO: Maybe don't buffer and just use ctypes.pointer(pointcloud_msg) to set it?
            # lidar_buffer.append(pointcloud_msg)
            # lidar_buffer.append(ctypes.pointer(pointcloud_msg))
            start_time = datetime.datetime.now()
            pb_message = to_proto(pointcloud_msg)
            end_time = datetime.datetime.now()
            times.append(end_time - start_time)
            lidar_buffer.append(pb_message)
            count += 1
            # print(count)

        # Register for pointcloud messages
        cartesian_pointcloud_callback = SickScanPointCloudMsgCallback(
            pySickScanCartesianPointCloudMsgCallback
        )
        SickScanApiRegisterCartesianPointCloudMsg(
            sick_scan_library, api_handle, cartesian_pointcloud_callback
        )

        # count = 0
        while True:  # self._counter < 2400:

            if len(lidar_buffer) > 0:
                # self.logger.warning(f"len lidar buffer {len(lidar_buffer)}")
                pointcloud_msg = lidar_buffer.pop()

                # pb_message = lidar_pb2.PBSickScanPointCloudMsg()
                # self.logger.warning(type(pointcloud_msg))
                # self.logger.warning(type(pb_message))
                # pb_message.data = bytes(pointcloud_msg)

                await self._event_service.publish("/data", pointcloud_msg)

                # new_read = pySickScanCartesianPointCloudMsgToXYZ(pointcloud_msg)
                #
                # point_cloud = lidar_pb2.GetLIDARResponse()
                #
                # for i in range(0, len(new_read[0])):
                #     point = point_cloud.points.add()
                #     point.x = new_read[0][i]
                #     point.y = new_read[1][i]
                #     point.z = self._counter  # new_read[2][i]
                #
                # await self._event_service.publish("/data", point_cloud)
                # only increase counter when data is sent to stop z-stretching
                self._counter += 1
            # await asyncio.sleep(5)

        SickScanApiDeregisterCartesianPointCloudMsg(
            sick_scan_library, api_handle, cartesian_pointcloud_callback
        )
        SickScanApiClose(sick_scan_library, api_handle)
        SickScanApiRelease(sick_scan_library, api_handle)
        SickScanApiUnloadLibrary(sick_scan_library)
        print(count)
        print(sum(delta.total_seconds() for delta in times) / len(times))
        exit()

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
