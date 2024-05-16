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
from datetime import datetime
from pathlib import Path

import grpc
from farm_ng.core.event_pb2 import Event
from farm_ng.core.event_service import EventServiceGrpc
from farm_ng.core.event_service_pb2 import EventServiceConfig
from farm_ng.core.events_file_reader import proto_from_json_file
from google.protobuf.empty_pb2 import Empty
from google.protobuf.message import Message
from sick_scan_api import *

from utils import sick_scan_library, api_handle, to_proto

DATE_FORMAT = "%Y-%m-%d_%H-%M-%S_%f"
PUBLISH_RATE = 600


def pyCustomizedPointCloudMsgCb(api_handle, pointcloud_msg):
    """
    Implement a callback to process pointcloud messages
    Data processing to be done
    """
    global lidar_buffer, BASE_DIR

    new_file_path = os.path.join(BASE_DIR, datetime.now().strftime(DATE_FORMAT))

    with open(new_file_path, "ab") as file:
        protocol_buffer = to_proto(pointcloud_msg.contents)
        file.write(protocol_buffer.SerializeToString())

    lidar_buffer = protocol_buffer


class LIDARServer:

    def __init__(self, event_service: EventServiceGrpc) -> None:
        global lidar_buffer
        """Initialize the service.

        Args:
            event_service: The event service to use for communication.
        """
        self._event_service = event_service
        self._event_service.add_request_reply_handler(self.request_reply_handler)

        self._counter = 0
        self._rate: float = 1.0
        lidar_buffer = None

    @property
    def logger(self) -> logging.Logger:
        """Return the logger for this service."""
        return self._event_service.logger

    async def request_reply_handler(self, event: Event, message: Message) -> None:
        global lidar_buffer, BASE_DIR
        """The callback for handling request/reply messages."""
        if event.uri.path == "/start_scan":

            asyncio.create_task(self.perform_lidar_sweep())

        return Empty()

    async def perform_lidar_sweep(self):
        global BASE_DIR, lidar_buffer
        SickScanApiInitByLaunchfile(sick_scan_library, api_handle, cli_args_for_sick)
        # Register for pointcloud messages
        cartesian_pointcloud_callback = SickScanPointCloudMsgCallback(
            pyCustomizedPointCloudMsgCb
        )
        SickScanApiRegisterCartesianPointCloudMsg(
            sick_scan_library, api_handle, cartesian_pointcloud_callback
        )
        BASE_DIR = f"/mnt/managed_home/farm-ng-user-gsainsbury/lidar_{datetime.now().strftime(DATE_FORMAT)}"
        os.makedirs(BASE_DIR, exist_ok=True)
        await asyncio.sleep(60)
        lidar_buffer = None
        SickScanApiDeregisterCartesianPointCloudMsg(
            sick_scan_library,
            api_handle,
            cartesian_pointcloud_callback,
        )
        SickScanApiClose(sick_scan_library, api_handle)
        SickScanApiRelease(sick_scan_library, api_handle)
        SickScanApiUnloadLibrary(sick_scan_library)

    async def run(self) -> None:
        """Run the main task."""
        global lidar_buffer

        while True:

            if lidar_buffer is not None:
                await self._event_service.publish("/data", lidar_buffer)
                lidar_buffer = None

            await asyncio.sleep(1.0 / self._rate)

    async def serve(self) -> None:
        await asyncio.gather(self._event_service.serve(), self.run())


# async def shutdown(loop, event_service):
#     print("Shutdown initiated...")
#     await finalise_sick(event_service)
#     print("Shutdown complete.")
#     loop.stop()


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

        # for sig in (signal.SIGTERM, signal.SIGINT):
        #     loop.add_signal_handler(
        #         sig,
        #         lambda: asyncio.create_task(shutdown(loop, lidar_service)),
        #     )

        # wrap and run the service
        loop.run_until_complete(lidar_service.serve())
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        loop.close()
