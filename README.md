# amiga-fastapi

## Application Overview
This repository was created from the Amiga React/FastAPI template, following the guide [here](https://amiga.farm-ng.com/docs/brain/brain-apps/).

This prototype application is designed to run on the Amiga Brain, following farm_ng's best practices, and connect to (one in the first instance, but later two) SICK LMS 4000 LiDAR scanners to measure crops.

Per the instructions on [brain apps manifest](https://amiga.farm-ng.com/docs/brain/brain-apps-manifest), an application for the Brain can be packaged as multiple services and apps. The design for this application includes both the `lidar-service` and the `lidar-app` which are defined in the `manifest.json` file. This file details the run commands, include arguments.

### lidar-service
The LiDAR service is based heavily on the [example code available with the SICK API](https://github.com/SICKAG/sick_scan_xd/blob/develop/examples/python/minimum_sick_scan_api_client.py), merged into the [example service available](https://amiga.farm-ng.com/docs/examples/service_counter/) from farm-ng. The code is in `lidar_service.py`.

The general approach was to implement the `EventServiceGrpc` class, and use the protocol buffer message defined `lidar.proto` and "publish" the encoded LiDAR message and have the app "subscribe" to the service.

_Note: the original implementation of this service was converting to XYZ coordinates before publishing the data but this is too computationally intensive, so the `to_proto()` and `from_proto()` functions were defined. It is not yet clear if these functions are still too slow for the LiDAR to operate at 600 Hz._

__Notes/TODO:__
* The service is defined to start running and publishing data when the amiga boots up. We might not want to implement it this way. It might be better to define start and stop methods for the LiDAR scanner itself.

### lidar-app
The template upon which this app is based assumes ReactJS expertise, which I do not have. For the purposes of demoing the LiDAR connectivity, we are simply returning an HTML/Javascript file directly from FastAPI which creates a Plotly graph of the streaming data. The code is in `main.py`.

__Notes/TODO:__
* When you start the scanning a buffer is created in the `lidar-app` which keeps track of the lidar messages. ~1/100 of them are processed for display and sent to the frontend over a websocket but most are just kept in memory and processed and written to a pointcloud (.ply file) when the stop button is pressed. It might be better to write these messages to disk, rather than keep them in memory.
* The data is converted to a list of (x,y,z) points with either a timer or counter being inserted as the z-value because the LiDAR does not have a world-coordinate representation of its movement. For post-processing, it is likely that the best approach will be to not convert to a pointcloud on the Brain itself, but instead keep a log of the messages, which include a timestamp, so that they can be matched to the GPS RTK data and the LiDAR can be georectified.


## Local Development
For local development, a Dockerfile and docker-compose file are available. This splits the `lidar-app` and `lidar-service` into two separate containers which provides some utility for debugging, but does add some complexity with regards to networking/addressing the services.

The advantage of using this approach is that it can run on any system (e.g. I did the development on MacOS despite the SICK API not being supported on MacOS by installing it in the Container).

There is a WIP implementation of using a LiDAR simulation based on the documentation from SICK [here](https://github.com/SICKAG/sick_scan_xd/blob/develop/USAGE.md#simulation), but it is not yet functioning.

## Amiga/Brain deployment

Following the instructions for installing the app [here](https://amiga.farm-ng.com/docs/brain/brain-apps/), I was able to install the app which effectively links the `manifest.json` to their service manager. The instructions seem to omit that it is necessary to build the app first, by running `./build.sh` in the installed directory. The troubleshooting guides [here](https://amiga.farm-ng.com/docs/brain/app-ownership/) helped solve that problem.

When it comes to deploying the app, there are currently many hard-coded paths including my farm-ng username which will need to be modified. I intend to change the build/install scripts to handle this, but I haven't yet.

Similarly, the SICK API is a prerequisite to the `lidar-service`. I have not yet included the installation of that in the `build.sh` or `install.sh` script, but the `RUN` statements in the `Dockerfile` are a good starting point. Further to that, when I installed the app on the `crimson-cherry` brain unit, I encountered [this issue](https://github.com/SICKAG/sick_scan_xd/issues/276) described in GitHub. The proposed workaround resolved it.


---
