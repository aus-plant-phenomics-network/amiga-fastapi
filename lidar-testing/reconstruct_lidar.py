import datetime
import os
import sys

import numpy as np
import open3d as o3d

import lidar_pb2
from utils import from_proto, pySickScanCartesianPointCloudMsgToXYZ
from tqdm import tqdm

# Make sure sick_scan_api is searched in all folders configured in environment variable PYTHONP>
def appendPythonPath():
    pythonpath = os.environ["PYTHONPATH"]
    for folder in pythonpath.split(";"):
        sys.path.append(os.path.abspath(folder))


try:
    # import sick_scan_api
    from sick_scan_api import *
except ModuleNotFoundError:
    print(
        "import sick_scan_api failed, module sick_scan_api not found, trying with importlib"
    )
    appendPythonPath()
    import importlib

    sick_scan_api = importlib.import_module("sick_scan_api")


def read_and_parse_all_files(directory):
    parsed_data = []
    for file_name in sorted(os.listdir(directory)):
        file_path = os.path.join(directory, file_name)

        with open(file_path, "rb") as binary_file:
            binary_data = binary_file.read()
            parsed_data.append(binary_data)
    return parsed_data


# Replace "directory_path" with the path to the directory containing binary files
for lidar in ["102", "103"]:
    directory = f"Lidar_{lidar}_data"
    current_directory = os.path.dirname(os.path.abspath(__file__))

    lidar_directory = os.path.join(current_directory, directory)

    print(lidar_directory)

    parsed_data = read_and_parse_all_files(lidar_directory)

    pcd = o3d.geometry.PointCloud()

    for i, datum in tqdm(enumerate(parsed_data), total=len(parsed_data)):

        protocolbuf = lidar_pb2.SickScanPointCloudMsg()
        protocolbuf.ParseFromString(datum)

        pointcloud_msg = from_proto(protocolbuf)

        start_time = None

        x_vals, y_vals, z_vals = pySickScanCartesianPointCloudMsgToXYZ(
            pointcloud_msg, start_time
        )
        xyz_points = np.array(
            [[x, y, i / 100] for x, y, z in zip(x_vals, y_vals, z_vals)]
        )
        pcd.points.extend(o3d.utility.Vector3dVector(xyz_points))

    filename = f'/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/lidar_{lidar}_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}.ply'
    o3d.io.write_point_cloud(filename, pcd)
    print(filename, flush=True)
