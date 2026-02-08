# Handshake Platform for ROS2 - RobotStudio
**The process made of tree stages:**
1. Pre-requisite #1: Interrupt-driven feedback for the ROBOT
2. Pre-requisite #2: Enable Streaming feature.(pyton)
3. Enable ROS2 (wsl2) to replace python

## Background
I have a python code for handshaking two ABB robots via tcp/ip socket communication. 
There are four key components here. First, the client
The python user Interface provides a package of data for each via ethernet, and RAPID script inside the robot controller execute pre-programmed motion states according to the package information. Inside the robot controller, there exists a dedicated communication script refreshing on the background. 
I want to add two features here: 
- The FIRST FEATURE is, using the TRAP function from RAPID, I want to build an interrupt DI signal that exits the current motion as soon as the signal is detected. The entire structure remains the same, such that still robot controller and RAPID takes the incoming motion state information, but while execution, it exits the current motion upon the interrupt is trigger. THE SECOND FEATURE, I want to have a different mode for each robot for individual switch from pre-define state motion to streaming mode. During the streaming mode, it only takes the 6 joint motions as input. For this modification, I am thinking of switching the current python interface to ros2 running in my container. The previous features remain the same, but during the streaming mode, ros2 controls the robot motion with external cameras, providing the 6 dofs to RAPID. Can you evaluate these fratures and provide some tips?

