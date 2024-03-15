# amiga-fastapi

This repository was created from the Amiga React/FastAPI template, following the guide [here](https://amiga.farm-ng.com/docs/brain/brain-apps/).

## Application Overview
The application includes two services, the `lidar-service` and the `lidar-app` which are defined in the `manifest.json` file.

### lidar-service
The LiDAR service is based heavily on the [example code available with the SICK API](https://github.com/SICKAG/sick_scan_xd/blob/develop/examples/python/minimum_sick_scan_api_client.py), merged into the [example service available](https://amiga.farm-ng.com/docs/examples/service_counter/) from farm-ng.

The general principle is to define this as a "publisher", extending the `EventServiceGrpc` class and have the app "subscribe" to the service.

__Notes/TODO:__
* The service is defined to start running and publishing data when the amiga boots up. We might not want to implement it this way.
* The data is converted to a list of (x,y,z) points with a timer/counter being inserted as the z-value because the LiDAR does not have a world-coordinate representation of any movement.

### lidar-app
The basis for the template assumes ReactJS expertise, which I do not have. For the purposes of demoing the LiDAR connectivity, we are simply returning a Jinja2/HTML template directly from FastAPI which has embedded Javascript to create a Plotly graph of the streaming data.

__Notes/TODO:__
* When you start the scanning a buffer is created in the `lidar-app` which keeps track of the lidar messages. ~1/100 of them are processed for display and sent to the frontend over a websocket but most are just kept in memory and processed into a pointcloud when the stop button is pressed.


## Local Development
For local development, a Dockerfile and docker-compose file are available. This splits the `lidar-app` and `lidar-service` into two separate containers which provides some utility for debugging, but does add some complexity with regards to networking/addressing the services.

The advantage of using this approach is that it can run on any system (e.g. I did the development on MacOS despite the SICK API not being supported on MacOS by installing it in the Container).

## Amiga/Brain deployment

Following the instructions for installing the app [here](https://amiga.farm-ng.com/docs/brain/brain-apps/), I was able to install the app which effectively links the `manifest.json` to their service manager. The instructions seem to omit that it is necessary to build the app first, by running `./build.sh` in the installed directory. The troubleshooting guides [here](https://amiga.farm-ng.com/docs/brain/app-ownership/) helped solve that problem.

When it comes to deploying the app, there are currently many hard-coded paths including my farm-ng username which will need to be modified. I intend to change the build/install scripts to handle this, but I haven't yet.

Similarly, the SICK API is a prerequisite to the `lidar-service` running and I have not yet included the installation of that in the automated installer. Further to that, when I installed the app on the `crimson-cherry` brain unit, I encountered [this issue](SICK install issue: https://github.com/SICKAG/sick_scan_xd/issues/276) described in github. The proposed workaround resolved it.


---
