FROM ubuntu:22.04

WORKDIR /mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi

ARG DEBIAN_FRONTEND=noninteractive
ARG TZ=Etc/UTC

# Install correct python version and build utilities for SICK
RUN apt update
RUN apt install -y software-properties-common
RUN add-apt-repository ppa:deadsnakes/ppa -y
RUN apt update
RUN apt-get -y install \
    tzdata \
    git \
    cmake \
    gcc \
    g++ \
    curl \
    python3.8 \
    python3.8-dev \
    python3.8-distutils \
    python3-pip \
    python3-venv \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

RUN apt update

RUN apt-get install -y libjsonrpccpp-dev libjsonrpccpp-tools


# Clone and build SICKAPI.
RUN mkdir -p ./sick_scan_ws
RUN git clone https://github.com/SICKAG/sick_scan_xd.git ./sick_scan_ws/sick_scan_xd
RUN mkdir -p ./sick_scan_ws/build
RUN export ROS_VERSION=0
RUN cmake -B ./sick_scan_ws/build -DROS_VERSION=0 -DLDMRS=0 -DSCANSEGMENT_XD=0 -DCMAKE_ENABLE_EMULATOR=1 -G "Unix Makefiles" ./sick_scan_ws/sick_scan_xd
RUN make -j4 -C ./sick_scan_ws/build
RUN make -j4 -C ./sick_scan_ws/build install

#ENV PYTHONPATH "${PYTHONPATH}:/sick_scan_xd/python/api"
#ENV LD_LIBRARY_PATH "${LD_LIBRARY_PATH}:/sick_scan_ws/build"

# Install npm to build React frontend.
ENV NVM_DIR /usr/local/nvm
RUN mkdir -p $NVM_DIR
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.1/install.sh | bash
ENV NODE_VERSION v20.11.1
RUN /bin/bash -c "source $NVM_DIR/nvm.sh && nvm install $NODE_VERSION && nvm use --delete-prefix $NODE_VERSION"
ENV NODE_PATH $NVM_DIR/versions/node/$NODE_VERSION/lib/node_modules
ENV PATH      $NVM_DIR/versions/node/$NODE_VERSION/bin:$PATH

RUN pip install --upgrade pip
RUN pip install --upgrade setuptools

COPY requirements.txt .

# create virtual environment for the backend
RUN python3 -m venv venv
RUN /bin/bash -c "source venv/bin/activate"

# install dependencies
RUN venv/bin/pip install -r requirements.txt

COPY ts /mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/ts

WORKDIR /mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi/ts


# build the frontend
RUN npm install
RUN npm run build

WORKDIR /mnt/managed_home/farm-ng-user-gsainsbury/amiga-fastapi

COPY templates .
COPY *.py .
COPY *.json .
COPY *.sh .