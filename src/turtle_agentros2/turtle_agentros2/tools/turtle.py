#  Copyright (c) 2024. Jet Propulsion Laboratory. All rights reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from math import cos, sin, sqrt
from typing import List

#import rospy
import rclpy
#from rclpy.exceptions import ROSInterruptionsException
from rclpy.client import Client

from geometry_msgs.msg import Twist
from langchain.agents import tool
from std_srvs.srv import Empty
from turtlesim.msg import Pose
from turtlesim.srv import Spawn, TeleportAbsolute, TeleportRelative, Kill, SetPen
from rclpy.node import Node
from std_msgs.msg import String
from rclpy.publisher import Publisher

cmd_vel_pubs = {}

def add_cmd_vel_pub(name: str, publisher: Publisher):
    global cmd_vel_pubs
    cmd_vel_pubs[name] = publisher

def remove_cmd_vel_pub(name: str):
    global cmd_vel_pubs
    cmd_vel_pubs.pop(name, None)


# Add the default turtle1 publisher on startup
rclpy.init()
node = rclpy.create_node('turtle_cmd_vel')
add_cmd_vel_pub("turtle1", node.create_publisher(msg_type=Twist, topic=f"turtle1/cmd_vel", qos_profile=10))
#cmd_vel_pub = Node.create_publisher(Twist, '/turtle1/cmd_vel', Pose, 10)

def within_bounds(x: float, y: float) -> tuple:
    """
    Check if the given x, y coordinates are within the bounds of the turtlesim environment.

    :param x: The x-coordinate.
    :param y: The y-coordinate.
    """
    if 0 <= x <= 11 and 0 <= y <= 11:
        return True, "Coordinates are within bounds."
    else:
        return False, f"({x}, {y}) will be out of bounds. Range is [0, 11] for each."


def will_be_within_bounds(
    name: str, velocity: float, lateral: float, angle: float, duration: float = 1.0
) -> tuple:
    """Check if the turtle will be within bounds after publishing a twist command."""
    # Get the current pose of the turtle
    pose = get_turtle_pose.invoke({"names": [name]})
    current_x = pose[name].x
    current_y = pose[name].y
    current_theta = pose[name].theta

    # Calculate the new position and orientation
    if abs(angle) < 1e-6:  # Straight line motion
        new_x = (
            current_x
            + (velocity * cos(current_theta) - lateral * sin(current_theta)) * duration
        )
        new_y = (
            current_y
            + (velocity * sin(current_theta) + lateral * cos(current_theta)) * duration
        )
    else:  # Circular motion
        radius = sqrt(velocity**2 + lateral**2) / abs(angle)
        center_x = current_x - radius * sin(current_theta)
        center_y = current_y + radius * cos(current_theta)
        angle_traveled = angle * duration
        new_x = center_x + radius * sin(current_theta + angle_traveled)
        new_y = center_y - radius * cos(current_theta + angle_traveled)

        # Check if any point on the circle is out of bounds
        for t in range(int(duration) + 1):
            angle_t = current_theta + angle * t
            x_t = center_x + radius * sin(angle_t)
            y_t = center_y - radius * cos(angle_t)
            in_bounds, _ = within_bounds(x_t, y_t)
            if not in_bounds:
                return (
                    False,
                    f"The circular path will go out of bounds at ({x_t:.2f}, {y_t:.2f}).",
                )

    # Check if the final x, y coordinates are within bounds
    in_bounds, message = within_bounds(new_x, new_y)
    if not in_bounds:
        return (
            False,
            f"This command will move the turtle out of bounds to ({new_x:.2f}, {new_y:.2f}).",
        )

    return True, f"The turtle will remain within bounds at ({new_x:.2f}, {new_y:.2f})."


@tool
def spawn_turtle(name: str, x: float, y: float, theta: float) -> str:
    """
    Spawn a turtle at the given x, y, and theta coordinates.

    :param name: name of the turtle.
    :param x: x-coordinate.
    :param y: y-coordinate.
    :param theta: angle.
    """
    in_bounds, message = within_bounds(x, y)
    if not in_bounds:
        return message

    # Remove any forward slashes from the name
    name = name.replace("/", "")

    # Wait for the service to become available
    spawn_service = create_client(Spawn, '/spawn')

    # Wait until the service is ready or times out
    while not spawn_service.wait_for_service(timeout_sec=5.0):
        if not rclpy.ok():
            return f"Failed to spawn {name}: service not available."
        get_logger().warn("Waiting for spawn service to be available...")

   # try:
    #    rospy.wait_for_service("/spawn", timeout=5)
   # except rospy.ROSException:
   #     return f"Failed to spawn {name}: service not available."

    # Call the service to spawn the turtle
    request = Spawn.Request()
    request.x = x
    request.y = y
    request.theta = theta
    request.name = name

    try:
        future = spawn_service.call_async(request)
        rclpy.spin_until_future_complete(future)

        if future.result() is not None:
            #Create a publisher for the cmd_vel topic for this turtle
            cmd_vel_pubs[name] = create_publisher(Twist, f'/{name}/cmd_vel', 10)
            return f"{name} spawned at x: {x}, y: {y}, theta: {theta}."
        else:
            return f"Failed to spawn {name}: Service call failed."
    except ROSInterruptionException as e:
        return f"Failed to spawn {name}: {e}"

   # try:
   #     spawn = rospy.ServiceProxy("/spawn", Spawn)
   #     spawn(x=x, y=y, theta=theta, name=name)

   #     global cmd_vel_pubs
   #     cmd_vel_pubs[name] = rospy.Publisher(f"/{name}/cmd_vel", Twist, queue_size=10)

   #     return f"{name} spawned at x: {x}, y: {y}, theta: {theta}."
   # except Exception as e:
   #     return f"Failed to spawn {name}: {e}"


@tool
def kill_turtle(names: List[str]):
    """
    Removes a turtle from the turtlesim environment.

    :param names: List of names of the turtles to remove (do not include the forward slash).
    """

    # Remove any forward slashes from the names
    names = [name.replace("/", "") for name in names]
    response = ""
    
    global cmd_vel_pubs

    for name in names:
        # Create a service client for the kill service
        kill_service = self.create_client(Kill, f'/{name}/kill')
        # Wait for the kill service to become available

        while not kill_service.wait_for_service(timeout_sec=5.0):
            if not rclpy.ok():
                response += f"Failed to kill {name}: /{name}/kill service not available.\n"
                break
            get_logger().warn(f"Waiting for kill service for {name}...")

        if not rclpy.ok():
            continue

            # Call the kill service
            try: 
                request = Kill.Request()
                future = kill_service.call_async(request)
                rclpy.spin_until_future_complete(future)

                if future.result() is not None:
                    # Remove the cmd_vel publisher for this turtle
                    if name in cmd_vel_pubs:
                        cmd_vel_pubs.pop(name, None)

                    response += f"Successfully killed {name}.\n"
                else:
                    response += f"Failed to kill {name}: Service call failed.\n"
            except Exception as e:
                response += f"Failed to kill {name}: {e}\n"

    return response

   # for name in names:
   #     try:
   #         rospy.wait_for_service(f"/{name}/kill", timeout=5)
   #     except rospy.ROSException:
   #         response += f"Failed to kill {name}: /{name}/kill service not available.\n"
   #         continue
   #     try:
   #         kill = rospy.ServiceProxy(f"/{name}/kill", Kill)
   #         kill()

   # return response


@tool
def clear_turtlesim():
    """Clears the turtlesim background and sets the color to the value of the background parameters."""
    #Create the service Client for the '/clear' service
    clear_service = create_client(Empty, '/clear')

    # wait for the service to become available
    while not clear_service.wait_for_service(timeout_sec=5.0):
        if not rclpy.ok():
            return "Failed to clear the turtlesim background: /clear service not available..."
        get_logger().warn("Waiting for /clear service to be available...")

    # Make the service call
    try:
        request = Empty.Request()
        future = clear_service.call_async(request)
        rclpy.spin_until_future_complete(future)

        if future.result() is not None:
            return "Successfull cleared the turtlesim background."
        else:
            return "Failed to clear the turtlesim background: Service call failed."

    except ROSInterruptException as e:
        return f"Failed to clear the turtlesim background: {e}"

   # try:
   #     rospy.wait_for_service("/clear", timeout=5)
   # except rospy.ROSException:
   #     return "Failed to clear the turtlesim background: /clear service not available."
   # try:
   #     clear = rospy.ServiceProxy("/clear", Empty)
   #     clear()
   #     return "Successfully cleared the turtlesim background."
   # except rospy.ServiceException as e:
   #     return f"Failed to clear the turtlesim background: {e}"

@tool
def pose_callback(msg: Pose, name: str):
    """
    Callback to store the post of the turtle
    This is needed since ROS 2 does not have a direct equivalent to rospy.wait_for_message
    get_turtle_pose will use asynchrnous subscriptions and process the messages in this callback
    """
    poses[name] = msg

@tool
def get_turtle_pose(names: List[str]) -> dict:
    """
    Get the pose of one or more turtles.

    :param names: List of names of the turtles to get the pose of.
    """

    # Remove any forward slashes from the names
    names = [name.replace("/", "") for name in names]
    poses = {}

    for name in names:
        #Create a subscription for each turtle's pose topic
        create_subscription(Pose, f'/{name}/pose', lambda msg, name=name: pose_callback(msg, name), 10)

    # Spin the node to process messages
    rclpy.spin_once(timeout_sec=5.0)

    # Return the poses we have collected
    for name in names:
        if name in poses:
            poses[name] = poses[name]
        else:
            poses[name] = {"Error": f"Failed to get pose for {name}: /{name}/pose not available"}

    return poses

    # Get the pose of each turtle
    #for name in names:
    #    try:
    #        msg = rospy.wait_for_message(f"/{name}/pose", Pose, timeout=5)
    #        poses[name] = msg
    #    except rospy.ROSException:
    #        return {
    #            "Error": f"Failed to get pose for {name}: /{name}/pose not available."
    #        }
    #return poses

@tool
def teleport_absolute(name: str, x: float, y: float, theta: float, hide_pen: bool = True):
    """
    Teleport a turtle to the given x, y, and theta coordinates.

    :param name: name of the turtle
    :param x: The x-coordinate, range: [0, 11]
    :param y: The y-coordinate, range: [0, 11]
    :param theta: angle
    :param hide_pen: True to hide the pen (do not show movement trace on screen), False to show the pen
    """
    in_bounds, message = within_bounds(x, y)
    if not in_bounds:
        return message

    # Wait for the service to be available

    teleport_service_name = f"/{name}/teleport_absolute"
    set_pen_service_name = f"/{name}/set_pen"
    try:
        get_logger().info(f"Waiting for service {teleport_service_name}")
        client_teleport = create_client(TeleportAbsolute, teleport_service_name)
        client_set_pen = create_client(SetPen, set_pen_service_name)
        while not client_teleport.wait_for_service(timeout_sec=5.0):
            get_logger().warn(f"Service {teleport_service_name} not available, waiting...")
    except Exception as e:
        return f"Failed to connect to teleport service: {e}"


    #Hide pen
    if hide_pen:
        request = SetPen.Request()
        request.r = 0
        request.g = 0
        request.b = 0
        request.width = 1
        request.off = 1
        client_set_pen.call(request)


    # Teleport the turtle
    try:
        request = TeleportAbsolute.Request()
        request.x = x
        request.y = y
        request.theta = theta
        client_teleport.call(request)

        # Restore the pen if needed
        if hide_pen:
            request.r = 30
            request.g = 30
            request.b = 255
            request.off = 0
            client_set_pen.call(request)

        #Get Current pose of the turtle
        current_pose = get_turtle_pose(name)
        return f"{name} new pose: ({current_pose.x}, {current_pose.y}) at {current_pose.theta} radians."
    except Exception as e:
        return f"Failed to teleport the turtle: {e}"
    
    #try:
    #    rospy.wait_for_service(f"/{name}/teleport_absolute", timeout=5)
    #except rospy.ROSException:
    #    return f"Failed to teleport the {name}: /{name}/teleport_absolute service not available."

    #try:
    #    teleport = rospy.ServiceProxy(f"/{name}/teleport_absolute", TeleportAbsolute)
    #    if hide_pen:
    #        set_pen.invoke({"name": name, "r": 0, "g": 0, "b": 0, "width": 1, "off": 1})
    #    teleport(x=x, y=y, theta=theta)
    #    if hide_pen:
    #        set_pen.invoke(
    #            {"name": name, "r": 30, "g": 30, "b": 255, "width": 1, "off": 0}
    #        )
    #    current_pose = get_turtle_pose.invoke({"names": [name]})

    #    return f"{name} new pose: ({current_pose[name].x}, {current_pose[name].y}) at {current_pose[name].theta} radians."
    #except rospy.ServiceException as e:
    #    return f"Failed to teleport the turtle: {e}"

@tool
def teleport_relative(name: str, linear: float, angular: float):
    """
    Teleport a turtle relative to its current position.

    :param name: name of the turtle
    :param linear: linear distance
    :param angular: angular distance
    """
    in_bounds, message = will_be_within_bounds(name, linear, 0.0, angular)
    if not in_bounds:
        return message

    # Wait for the service to be available
    teleport_service_name = f"/{name}/teleport_relative"
    try:
        get_logger().info(f"Waiting for service {teleport_service_name}")
        client_teleport = create_client(TeleportRelative, teleport_service_name)
        while not client_teleport.wait_for_service(timeout_sec=5.0):
            get_logger().warn(f"Service {teleport_service_name} not available, waiting...")
    except Exception as e:
        return f"Failed to connect to teleport service: {e}"

    # Call the teleport relative service
    try:
        request = TeleportRelative.Request()
        request.linear = linear
        request.angular = angular
        client_teleport.call(request)

        #Get Current pose of the turtle
        current_pose = get_turtle_pose(name)
        return f"{name} new pose: ({curent_pose.x}, {current_pose.y}) at {current_pose.theta} radians."
    except Exception as e:
        return f"Failed to teleport the turtle: {e}"

    #try:
    #    rospy.wait_for_service(f"/{name}/teleport_relative", timeout=5)
    #except rospy.ROSException:
    #    return f"Failed to teleport the {name}: /{name}/teleport_relative service not available."
    #try:
    #    teleport = rospy.ServiceProxy(f"/{name}/teleport_relative", TeleportRelative)
    #    teleport(linear=linear, angular=angular)
    #    current_pose = get_turtle_pose.invoke({"names": [name]})
    #    return f"{name} new pose: ({current_pose[name].x}, {current_pose[name].y}) at {current_pose[name].theta} radians."
    #except rospy.ServiceException as e:
    #    return f"Failed to teleport the turtle: {e}"

@tool
def publish_twist_to_cmd_vel(
    name: str,
    velocity: float,
    lateral: float,
    angle: float,
    steps: int = 1,
):
    """
    Publish a Twist message to the /{name}/cmd_vel topic to move a turtle robot.
    Use a combination of linear and angular velocities to move the turtle in the desired direction.

    :param name: name of the turtle (do not include the forward slash)
    :param velocity: linear velocity, where positive is forward and negative is backward
    :param lateral: lateral velocity, where positive is left and negative is right
    :param angle: angular velocity, where positive is counterclockwise and negative is clockwise
    :param steps: Number of times to publish the twist message
    """
    # Remove any forward slashes from the name
    name = name.replace("/", "")

    # Check if the movement will keep the turtle within bounds
    in_bounds, message = will_be_within_bounds(name, velocity, lateral, angle, duration=steps)
    if not in_bounds:
        return message

    # Prepare the Twist Message
    vel = Twist()
    vel.linear.x, vel.linear.y, vel.linear.z = velocity, lateral, 0.0
    vel.angular.x, vel.angular.y, vel.angular.z = 0.0, 0.0, angle

    # Create the publisher if it doesn't exist yet
    if name not in cmd_vel_pubs:
        pub = create_publisher(Twist, f'/{name}/cmd_vel', 10)
        cmd_vel_pubs[name] = pub
    else:
        pub = cmd_vel_pubs[name]

    # Publish the twist message for the specified number of steps 
    try:
        for _ in range(steps):
            pub.publish(vel)
            rclpy.spin_once() # Allow ROS 2 to process messages for 1 iteration
            get_logger().info(f"Published {vel} to /{name}/cmd_vel")
    except Exception as e:
        return f"Failed to publish {vel} to /{name}/cmd_vel: {e}"

    # Get current pose of the turtle 
    current_pose = get_turtle_pose(name)
    return f"New Pose ({name}): x={current_pose.x}, y={current_pose.y}, " \
           f"theta={current_pose.theta} radians, " \
           f"linear_velocity={current_pose.linear_velocity}, " \
           f"angular_velocity={current_pose.angular_velocity}."

    #try:
    #    global cmd_vel_pubs
    #    pub = cmd_vel_pubs[name]

    #    for _ in range(steps):
    #        pub.publish(vel)
    #        rospy.sleep(1)
    #except Exception as e:
    #    return f"Failed to publish {vel} to /{name}/cmd_vel: {e}"
    #finally:
    #    current_pose = get_turtle_pose.invoke({"names": [name]})
    #    return (
    #        f"New Pose ({name}): x={current_pose[name].x}, y={current_pose[name].y}, "
    #        f"theta={current_pose[name].theta} rads, "
    #        f"linear_velocity={current_pose[name].linear_velocity}, "
    #        f"angular_velocity={current_pose[name].angular_velocity}."
    #    )

@tool
def stop_turtle(name: str):
    """
    Stop a turtle by publishing a Twist message with zero linear and angular velocities.

    :param name: name of the turtle
    """
    return publish_twist_to_cmd_vel(name, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

#TODO Convert to ROS 2
@tool
def reset_turtlesim():
    """
    Resets the turtlesim, removes all turtles, clears any markings, and creates a new default turtle at the center.
    """
    try:
        # Wait for the /reset service to become available
        get_logger().info("Waiting for /reset serice...")
        reset_service_client = create_client(Empty, '/reset')

        # Wait for the service to be availanle
        while not reset_service_client.wait_for_service(timeout_sec=5.0):
            get_logger().warn('/reset service not available, waiting...')

        # Call the service to reset the turtlesim environment
        request = Empty.Request()
        reset_service_client.call(request)
        get_logger().info("Turtlesim has been reset.")

    except Exception as e:
        get_logger().error(f"Failed to reset the turtlesim environment: {e}")


    #try:
    #    rospy.wait_for_service("/reset", timeout=5)
    #except rospy.ROSException:
    #    return (
    #        "Failed to reset the turtlesim environment: /reset service not available."
    #    )
    #try:
    #    reset = rospy.ServiceProxy("/reset", Empty)
    #    reset()
