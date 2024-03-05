FROM ubuntu:22.04


ARG DEBIAN_FRONTEND=noninteractive
ARG TZ=Etc/UTC


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
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p ./sick_scan_ws
RUN cd ./sick_scan_ws
RUN git clone https://github.com/SICKAG/sick_scan_xd.git

RUN cd sick_scan_xd
RUN mkdir -p ./build
RUN cd ./build
#RUN rm -rf ./*
RUN export ROS_VERSION=0
RUN cmake -DROS_VERSION=0 -DLDMRS=0 -DSCANSEGMENT_XD=0 -G "Unix Makefiles" ../sick_scan_xd
RUN make -j4
RUN make -j4 install
RUN cd ..

ENV PYTHONPATH "${PYTHONPATH}:/sick_scan_xd/python/api"
ENV LD_LIBRARY_PATH "${LD_LIBRARY_PATH}:/sick_scan_ws/build"

RUN pip install --upgrade pip
RUN pip install --upgrade setuptools

COPY requirements.txt /requirements.txt

RUN pip install -r /requirements.txt

ENV NVM_DIR /usr/local/nvm
RUN mkdir -p $NVM_DIR
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.1/install.sh | bash
ENV NODE_VERSION v20.11.1
RUN /bin/bash -c "source $NVM_DIR/nvm.sh && nvm install $NODE_VERSION && nvm use --delete-prefix $NODE_VERSION"

ENV NODE_PATH $NVM_DIR/versions/node/$NODE_VERSION/lib/node_modules
ENV PATH      $NVM_DIR/versions/node/$NODE_VERSION/bin:$PATH

COPY /ts /app/ts
WORKDIR /app/ts
RUN npm install
RUN npm run build  # build the frontend

WORKDIR /app
COPY . /app

# Full LIDAR Test
#CMD python3 /sick_scan_xd/test/python/sick_scan_xd_api/sick_scan_xd_api_test.py /sick_scan_xd/launch/sick_lms_4xxx.launch hostname:=192.168.0.1

#CMD python3 /app/main.py --config /opt/farmng/config.json
#CMD python3 /app/main.py --debug


