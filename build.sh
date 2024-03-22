#!/bin/bash -x

# create virtual environment for the backend
python3 -m venv venv
source venv/bin/activate

# TODO: update pip and setuptools first.

# install dependencies
pip install -r requirements.txt

# build the frontend
cd ts/
npm install
npm run build


#TODO: install all prerequisites (e.g. ffmpeg libsm6 libxext6 on the brain) also.
