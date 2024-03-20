import datetime
import importlib
import sys

import numpy as np
import open3d as o3d

import lidar_pb2

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


def to_proto(message_contents):
    protocolbuf = lidar_pb2.SickScanPointCloudMsg()

    protocolbuf.height = message_contents.height
    protocolbuf.width = message_contents.width
    protocolbuf.is_bigendian = message_contents.is_bigendian
    protocolbuf.point_step = message_contents.point_step
    protocolbuf.row_step = message_contents.row_step
    protocolbuf.is_dense = message_contents.is_dense
    protocolbuf.num_echos = message_contents.num_echos
    protocolbuf.segment_idx = message_contents.segment_idx

    protocol_buf_header = lidar_pb2.SickScanPointCloudMsg.SickScanHeader()
    protocol_buf_header.seq = message_contents.header.seq
    protocol_buf_header.timestamp_sec = message_contents.header.timestamp_sec
    protocol_buf_header.timestamp_nsec = message_contents.header.timestamp_nsec
    protocol_buf_header.frame_id = bytes(message_contents.header.frame_id)

    protocol_buf_data = lidar_pb2.SickScanPointCloudMsg.SickScanUint8Array()
    protocol_buf_data.capacity = message_contents.data.capacity
    protocol_buf_data.size = message_contents.data.size

    buffer = ctypes.cast(
        message_contents.data.buffer,
        ctypes.POINTER(ctypes.c_uint8 * message_contents.data.size),
    ).contents
    protocol_buf_data.buffer = bytes(buffer)

    protocol_buf_fields = lidar_pb2.SickScanPointCloudMsg.SickScanPointFieldArray()

    protocol_buf_fields.capacity = message_contents.fields.capacity
    protocol_buf_fields.size = message_contents.fields.size

    num_fields = message_contents.fields.size

    for n in range(num_fields):

        field_message_for_pb = lidar_pb2.SickScanPointCloudMsg.SickScanPointFieldMsg()

        field_message_for_pb.name = message_contents.fields.buffer[n].name
        field_message_for_pb.offset = message_contents.fields.buffer[n].offset
        field_message_for_pb.datatype = message_contents.fields.buffer[n].datatype
        field_message_for_pb.count = message_contents.fields.buffer[n].count

        protocol_buf_fields.buffer.append(field_message_for_pb)

    protocolbuf.header.CopyFrom(protocol_buf_header)
    protocolbuf.data.CopyFrom(protocol_buf_data)
    protocolbuf.fields.CopyFrom(protocol_buf_fields)

    return protocolbuf


def from_proto(protocol_message):

    header = SickScanHeader(
        seq=protocol_message.header.seq,
        timestamp_sec=protocol_message.header.timestamp_sec,
        timestamp_nsec=protocol_message.header.timestamp_nsec,
        frame_id=protocol_message.header.frame_id,
    )

    num_fields = protocol_message.fields.size
    array = SickScanPointFieldMsg * num_fields
    elements = array()

    for n in range(num_fields):
        field = SickScanPointFieldMsg(
            name=protocol_message.fields.buffer[n].name,
            offset=protocol_message.fields.buffer[n].offset,
            datatype=protocol_message.fields.buffer[n].datatype,
            count=protocol_message.fields.buffer[n].count,
        )
        elements[n] = field

    fields = SickScanPointFieldArray(
        capacity=protocol_message.fields.capacity,
        size=protocol_message.fields.size,
        buffer=elements,
    )

    byte_data = bytes(protocol_message.data.buffer)
    size = len(byte_data)
    buffer_copy = bytearray(byte_data)
    buffer_type = ctypes.c_uint8 * size
    buffer_instance = buffer_type.from_buffer(buffer_copy)

    data = SickScanUint8Array(
        capacity=protocol_message.data.capacity,
        size=protocol_message.data.size,
        buffer=buffer_instance,
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
        num_echos=protocol_message.num_echos,
        segment_idx=protocol_message.segment_idx,
    )

    return message_contents


def pySickScanCartesianPointCloudMsgToXYZ(pointcloud_msg, start_time=None):
    # get pointcloud fields
    num_fields = pointcloud_msg.fields.size
    msg_fields_buffer = pointcloud_msg.fields.buffer
    field_offset_x = -1
    field_offset_y = -1
    field_offset_z = -1

    if start_time is not None:
        scan_time = datetime.datetime.fromtimestamp(
            pointcloud_msg.header.timestamp_sec
        ) + datetime.timedelta(
            microseconds=pointcloud_msg.header.timestamp_nsec // 1000
        )
        delta = start_time - scan_time
        total_nanoseconds = delta.total_seconds() * 1e9 + delta.microseconds * 1000

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
            if start_time is None:
                points_z[point_idx] = np.frombuffer(
                    cloud_data_buffer,
                    dtype=np.float32,
                    count=1,
                    offset=pointcloud_offset + field_offset_z,
                )[0]
            else:
                # print(
                #     "here",
                #     pointcloud_msg.header.seq,
                #     pointcloud_msg.header.timestamp_sec,
                #     pointcloud_msg.header.timestamp_nsec,
                # )

                points_z[point_idx] = total_nanoseconds
            point_idx = point_idx + 1
    return points_x, points_y, points_z


async def create_ply_file_from_buffer(lidar_buffer, start_time):

    # xyz = np.random.rand(100, 3)
    pcd = o3d.geometry.PointCloud()

    for i, read in enumerate(lidar_buffer):
        message = from_proto(read)
        x_values, y_values, z_values = pySickScanCartesianPointCloudMsgToXYZ(
            message, start_time
        )
        # TODO: Use z/timestamp instead of scaled index.
        xyz_points = np.array(
            [[x, y, i / 100] for x, y, z in zip(x_values, y_values, z_values)]
        )
        pcd.points.extend(o3d.utility.Vector3dVector(xyz_points))

    filename = f'/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/lidar_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}.ply'
    o3d.io.write_point_cloud(filename, pcd)
    print(filename, flush=True)


# Convert a SickScanCartesianPointCloudMsg to points
