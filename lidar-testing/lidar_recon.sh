#!/bin/bash

export PYTHONPATH=/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/sick_scan_ws/sick_scan_xd/python/api:$PYTHONPATH
export LD_LIBRARY_PATH=/mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/sick_scan_ws/build:$LD_LIBRARY_PATH
python  /mnt/managed_home/farm-ng-user-gsainsbury/reconstruct_lidar.py
