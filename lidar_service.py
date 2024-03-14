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
import importlib
import logging
import signal
import sys
from collections import deque
from pathlib import Path

import grpc
from farm_ng.core.event_pb2 import Event
from farm_ng.core.event_service import EventServiceGrpc
from farm_ng.core.event_service_pb2 import EventServiceConfig
from farm_ng.core.events_file_reader import proto_from_json_file
from google.protobuf.empty_pb2 import Empty
from google.protobuf.message import Message

from utils import to_proto

sys.path.append(
    f"/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/sick_scan_ws/sick_scan_xd/python/api"
)

sick_scan_api = importlib.import_module("sick_scan_api")

from sick_scan_api import *

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


def pySickScanCartesianPointCloudMsgCallback(api_handle, pointcloud_msg):
    global lidar_buffer, times
    pointcloud_msg = (
        pointcloud_msg.contents
    )  # dereference msg pointer (pointcloud_msg = pointcloud_msg[0])

    start_time = datetime.datetime.now()
    pb_message = to_proto(pointcloud_msg)
    end_time = datetime.datetime.now()
    times.append(end_time - start_time)
    lidar_buffer.append(pb_message)


class LIDARServer:
    """A simple service that implements the AddTwoInts service."""

    def __init__(self, event_service: EventServiceGrpc) -> None:
        """Initialize the service.

        Args:
            event_service: The event service to use for communication.
        """
        self.cartesian_pointcloud_callback = None
        self._event_service = event_service
        self._event_service.add_request_reply_handler(self.request_reply_handler)

        self._counter = 0

        self.api_handle = SickScanApiCreate(sick_scan_library)

        SickScanApiInitByLaunchfile(
            sick_scan_library, self.api_handle, cli_args_for_sick
        )

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
        global lidar_buffer, times

        times = []
        lidar_buffer = deque(maxlen=10)

        # Register for pointcloud messages
        self.cartesian_pointcloud_callback = SickScanPointCloudMsgCallback(
            pySickScanCartesianPointCloudMsgCallback
        )
        SickScanApiRegisterCartesianPointCloudMsg(
            sick_scan_library, self.api_handle, self.cartesian_pointcloud_callback
        )

        while True:  # self._counter < 1000:

            if len(lidar_buffer) > 0:
                pointcloud_msg = lidar_buffer.pop()

                await self._event_service.publish("/data", pointcloud_msg)

                self._counter += 1
            await asyncio.sleep(0.001)

        await finalise_sick(self.api_handle)

    async def serve(self) -> None:
        await asyncio.gather(self._event_service.serve(), self.run())

    # TODO: Add a "on killed or stopped" service function

    # Close lidar and release sick_scan api
    # SickScanApiDeregisterCartesianPointCloudMsg(sick_scan_library, api_handle, cartesian_pointcloud_callback)
    # SickScanApiClose(sick_scan_library, api_handle)
    # SickScanApiRelease(sick_scan_library, api_handle)
    # SickScanApiUnloadLibrary(sick_scan_library)


async def finalise_sick(event_service):
    global times
    print(len(times))
    print(sum(delta.total_seconds() for delta in times) / len(times), flush=True)

    SickScanApiDeregisterCartesianPointCloudMsg(
        sick_scan_library,
        event_service.api_handle,
        event_service.cartesian_pointcloud_callback,
    )
    SickScanApiClose(sick_scan_library, event_service.api_handle)
    SickScanApiRelease(sick_scan_library, event_service.api_handle)
    SickScanApiUnloadLibrary(sick_scan_library)


async def shutdown(loop, event_service):
    print("Shutdown initiated...")
    await finalise_sick(event_service)
    print("Shutdown complete.")
    loop.stop()


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

        lidar_service = LIDARServer(event_service)

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(shutdown(loop, lidar_service)),
            )

        # wrap and run the service
        loop.run_until_complete(lidar_service.serve())
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        loop.close()
