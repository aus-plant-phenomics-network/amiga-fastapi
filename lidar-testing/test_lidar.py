"""Minimalistic usage example for sick_scan_api

Usage: minimum_sick_scan_api_client.py launchfile

Example:
    export LD_LIBRARY_PATH=.:./build:$LD_LIBRARY_PATH
    export PYTHONPATH=.:./python/api:$PYTHONPATH
    python3 ./examples/python/minimum_sick_scan_api_client.py ./launch/sick_tim_7xx.launch

See doc/sick_scan_api/sick_scan_api.md for further information.

"""

import os
import sys
import time
from datetime import datetime

from utils import to_proto


# Make sure sick_scan_api is searched in all folders configured in environment variable PYTHONPATH
def appendPythonPath():
    pythonpath = os.environ["PYTHONPATH"]
    for folder in pythonpath.split(";"):
        sys.path.append(os.path.abspath(folder))


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

# Load sick_scan_library
if os.name == "nt":  # Load windows dll
    sick_scan_library = SickScanApiLoadLibrary(
        [
            "build/Debug/",
            "build_win64/Debug/",
            "../../build/Debug/",
            "../../build_win64/Debug/",
            "./",
            "../",
        ],
        "sick_scan_xd_shared_lib.dll",
    )
else:  # Load linux so
    sick_scan_library = SickScanApiLoadLibrary(
        ["build/", "build_linux/", "../../build/", "../../build_linux/", "./", "../"],
        "libsick_scan_xd_shared_lib.so",
    )


def pyCustomizedPointCloudMsgCb(api_handle, msg):
    """
    Implement a callback to process pointcloud messages
    Data processing to be done
    """
    global message_count

    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S.%f")
    message_count += 1

    file_name = formatted_datetime
    new_file_path = os.path.join(new_folder_path, file_name)
    with open(new_file_path, "ab") as file:
        file.write(to_proto(msg.contents).SerializeToString())


cli_args = " ".join(sys.argv[1:])


# Create a sick_scan instance and initialize a TiM-7xx
api_handle = SickScanApiCreate(sick_scan_library)
SickScanApiInitByLaunchfile(sick_scan_library, api_handle, cli_args)

# Custom added code below

# This code is to make a new folder to save our lidar data. Folder
# name will be lidar_<last 3 digits of ip-address>_data.bin

# Get the directory of the current Python script
current_directory = os.path.dirname(os.path.abspath(__file__))

lidar_ip_addr = sys.argv[2]  # Get ip addresss
new_folder_name = "Lidar_" + lidar_ip_addr[-3:] + "_data"
# Create new folder path
new_folder_path = os.path.join(current_directory, new_folder_name)
# Check if the folder already exists, if not, create it
if not os.path.exists(new_folder_path):
    os.makedirs(new_folder_path)
    print(f"New Folder '{new_folder_name}' has been created.")
else:
    print(f"Folder '{new_folder_name}' already exists in the directory.")


# Register for pointcloud messages
cartesian_pointcloud_callback = SickScanPointCloudMsgCallback(
    pyCustomizedPointCloudMsgCb
)
SickScanApiRegisterCartesianPointCloudMsg(
    sick_scan_library, api_handle, cartesian_pointcloud_callback
)

# Run application or main loop
message_count = 0
run_time = 60
time.sleep(run_time)

# Close lidar and release sick_scan api
SickScanApiDeregisterCartesianPointCloudMsg(
    sick_scan_library, api_handle, cartesian_pointcloud_callback
)
SickScanApiClose(sick_scan_library, api_handle)
SickScanApiRelease(sick_scan_library, api_handle)
SickScanApiUnloadLibrary(sick_scan_library)

print(
    f"Application finished. Ran for {run_time} seconds and had {message_count} results. { message_count / run_time } Hz"
)
