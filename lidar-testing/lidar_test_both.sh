#!/bin/bash

export PYTHONPATH=/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/sick_scan_ws/sick_scan_xd/python/api:$PYTHONPATH
export LD_LIBRARY_PATH=/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/sick_scan_ws/build:$LD_LIBRARY_PATH
python  /mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/lidar-testing/test_lidar.py /mnt/managed_home/farm-ng-user-gsainsbury/sick_scan_ws/sick_scan_xd/launch/sick_lms_4xxx.launch hostname:=10.95.76.102
# & \ python /mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/lidar-testing/test_lidar.py /mnt/managed_home/farm-ng-user-gsainsbury/sick_scan_ws/sick_scan_xd/launch/sick_lms_4xxx.launch hostname:=10.95.76.103
