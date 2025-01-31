#!/usr/bin/env bash
# Copyright (c) 2024. Jet Propulsion Laboratory. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This script launches the ROSA demo in Docker
# Usage: ./demo.sh [ros1|ros2]

# Check if the correct number of arguments are passed (Needs one argument either ros1 or ros2)
if [ "$#" -ne 1 ]; then
    echo "Usage: ./demo.sh [ros1|ros2]"
    exit 1
fi

# Check if the first argument is either ros1 or ros2
if [ "$1" != "ros1" ] && [ "$1" != "ros2" ]; then
    echo "Usage: ./demo.sh [ros1|ros2]"
    exit 1
fi

# Check if User has Docker installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker and try again."
    exit 1
fi

# Check if the user has docker-compose installed
if ! command -v docker-compose &> /dev/null; then
    echo "Docker-compose is not installed. Please install docker-compose and try again."
    exit 1
fi

# Check if the user has xhost is installed
if ! command -v xhost &> /dev/null; then
    echo "xhost-xserver-utils is not installed. Please install xhost-xserver-utils and try again."
    exit 1
fi


# Set default headless mode
HEADLESS=${HEADLESS:-false}
DEVELOPMENT=${DEVELOPMENT:-false}

# Enable X11 forwarding based on OS
case "$(uname)" in
    Linux*|Darwin*)
        echo "Enabling X11 forwarding..."
        # If running under WSL, use :0 for DISPLAY
        if grep -q "WSL" /proc/version; then
            export DISPLAY=:0
        else
            export DISPLAY=host.docker.internal:0
        fi
        xhost +
        ;;
    MINGW*|CYGWIN*|MSYS*)
        echo "Enabling X11 forwarding for Windows..."
        export DISPLAY=host.docker.internal:0
        ;;
    *)
        echo "Error: Unsupported operating system."
        exit 1
        ;;
esac

# Check if X11 forwarding is working
if ! xset q &>/dev/null; then
    echo "Error: X11 forwarding is not working. Please check your X11 server and try again."
    exit 1
fi

# Parse the argument for helping choose docker file based on ros version
ros_version=$1

# Set the ros distro specific dockerfile
if [ "$ros_version" == "ros1" ]; then
    dockerfile="DockerfileROS1" 
else
    dockerfile="DockerfileROS2"
fi

# Build the docker image/container
CONTAINER_NAME="rosa-turtlesim-demo"
echo "Building the $CONTAINER_NAME Docker image..."
docker build --build-arg DEVELOPMENT=$DEVELOPMENT -t $CONTAINER_NAME -f $dockerfile . || { echo "Error: Docker build failed"; exit 1; }

#Run the Docker Container
echo "Running the Docker container..."          
docker run -it --rm --name $CONTAINER_NAME \
    -e DISPLAY=$DISPLAY \
    -e HEADLESS=$HEADLESS \
    -e DEVELOPMENT=$DEVELOPMENT \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v "$PWD/src":/app/src \
    -v "$PWD/tests":/app/tests \
    --network host \
    $CONTAINER_NAME

# Disable X11 forwarding
#xhost -

exit 0
