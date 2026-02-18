import zmq
import subprocess
import time
import struct
import sys
from typing import Optional
from src.communication.data_structures import LinkedList
from src.communication.protocol import pack_data, unpack_data
from config.constants import (
    object_group_1,
    object_group_2,
    STREAMING_STATE_NAME,
)
from config.settings import Config
import math


socket_int_multiMove_send: Optional[zmq.Socket] = None
socket_int_multiMove_recv: Optional[zmq.Socket] = None
socket_int_cobot_send: Optional[zmq.Socket] = None
socket_int_cobot_recv: Optional[zmq.Socket] = None

PATH_OF_THIS_ENV = r"C:\Users\Administrator\anaconda3\envs\multiMoveEnv\python.exe"
PATH_TO_MULTIMOVE = r"PythonHMI/server_multiMove.py"
PATH_TO_COBOT = r"PythonHMI/server_cobot.py"

is_this_simulation = True
MAX_PACKET_SIZE = 1024
fmt_elen = '!I'  # Format
PACKET_OFFSET = 4  # Number of bytes used to store the length of the packet. 4 Is the size of an unsigned int (4 bytes)


def interactive_streaming_handler(socket_send: zmq.Socket, socket_recv: zmq.Socket,
                                  max_points: int = 0) -> None:
    """Interactive streaming handler for PHASE 2 testing.

    Provides a sub-menu for manual joint input, sine-wave test, or 'q' to exit.
    Used both from the top-level 's' menu and as a callback for Stream nodes
    in traverse_and_execute.

    Args:
        socket_send: ZMQ PUSH socket to the MultiMove server
        socket_recv: ZMQ PULL socket from the MultiMove server
        max_points: 0 = open-ended (only 'q' exits), >0 = auto-terminate after N points.
                    Operator can always type 'q' to exit early.
    """
    print("--- Streaming mode ---")
    print("Enter 6 comma-separated joint values (e.g., 0,0,0,0,0,0)")
    print("  'test' - Run 20-point sine wave test on J1 (+/- 5 deg)")
    print("  'q'    - Return to state mode")
    if max_points > 0:
        print(f"  Auto-exit after {max_points} points")

    points_sent = 0
    streaming = True
    while streaming:
        # Auto-terminate check
        if max_points > 0 and points_sent >= max_points:
            print(f"Reached {max_points} points. Exiting streaming mode.")
            break

        remaining = f" ({max_points - points_sent} remaining)" if max_points > 0 else ""
        stream_input = input(f"Stream{remaining}> ")

        if stream_input.lower() == 'q':
            streaming = False
        elif stream_input.lower() == 'test':
            # 20-point sine wave on J1, safe amplitude
            base_joints = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            t = 0
            test_count = 20
            # If max_points is set, cap the test to remaining points
            if max_points > 0:
                test_count = min(test_count, max_points - points_sent)
            print(f"Running {test_count}-point sine wave test...")
            for i in range(test_count):
                joints = base_joints.copy()
                joints[0] = 5.0 * math.sin(t)
                dataPkg = pack_data(joints)
                socket_send.send(dataPkg)
                print(f"  Point {i+1}/{test_count}: J1={joints[0]:.2f}")
                try:
                    ack = socket_recv.recv(MAX_PACKET_SIZE)
                    print(f"  ACK received")
                except zmq.Again:
                    print(f"  ACK timeout")
                t += 0.3
                points_sent += 1
                time.sleep(0.5)
            print("Streaming test completed.")
        else:
            try:
                joints = [float(x.strip()) for x in stream_input.split(',')]
                if len(joints) == 6:
                    dataPkg = pack_data(joints)
                    socket_send.send(dataPkg)
                    print(f"Sent: {joints}")
                    try:
                        ack = socket_recv.recv(MAX_PACKET_SIZE)
                        print("ACK received")
                    except zmq.Again:
                        print("ACK timeout")
                    points_sent += 1
                else:
                    print(f"Need 6 values, got {len(joints)}")
            except ValueError:
                print("Invalid input. Use comma-separated numbers.")

    print("--- Exited streaming mode ---")


def main() -> None:
    global fmt_elen, PACKET_OFFSET, MAX_PACKET_SIZE
    
    # Initialize the ZMQ context and sockets according to the given condition.
    userInput_modeExe = input("Enter '1' for simulation mode or '2' for real robot mode: ")
    if userInput_modeExe == '1':
        # 1. Establish the server, internal socket for multiMove
        socket_int_multiMove_send = zmq.Context().socket(zmq.PUSH)
        socket_int_multiMove_send.setsocketopt(zmq.RCVTIMEO, 500)  # Set a timeout of 500 milliseconds (0.5 second)
        socket_int_multiMove_send.bind("tcp://*:8080")
        socket_int_multiMove_recv = zmq.Context().socket(zmq.PULL)
        socket_int_multiMove_recv.setsocketopt(zmq.RCVTIMEO, 500)  # Set a timeout of 500 milliseconds (0.5 second)
        socket_int_multiMove_recv.bind("tcp://*:8060")
        
        # 2. Establish the client, internal socket
        if is_this_simulation:
            subprocess.Popen(['start', 'cmd', '/k', 'python', 'server_multiMove.py'], shell=True)
        else:
            subprocess.Popen(['start', 'cmd', '/k', PATH_OF_THIS_ENV, PATH_TO_MULTIMOVE], shell=True)
        time.sleep(1)  # Wait for the server to start

        # 3. Acknowledge from the server
        toggle_listeningFromServer = False
        while not toggle_listeningFromServer:
            acknowledgeFromServer = (99,99,99)
            try:
                dataFromServer_MultiMove = socket_int_multiMove_recv.recv(MAX_PACKET_SIZE)
                if not dataFromServer_MultiMove is None:
                    # Ensure the specific buffer size
                    if len(dataFromServer_MultiMove) >= struct.calcsize(fmt_elen):
                        elen = struct.unpack_from(fmt_elen, dataFromServer_MultiMove)[0]
                        fmt_data = "!" + "d" * elen
                        # Ensure the buffer is large enough for the format string and offset:
                        if len(dataFromServer_MultiMove) == struct.calcsize(fmt_data) + PACKET_OFFSET:
                            data = struct.unpack_from(fmt_data, dataFromServer_MultiMove, PACKET_OFFSET)
                            if data == acknowledgeFromServer:
                                toggle_listeningFromServer = True
                                print("Acknowledgment received from the server. Starting to listen for data...")
                        else:
                            # mitigate buffer overflow by discarding the data if it's larger than expected
                            print(f'debugging the buffer size: {struct.calcsize(fmt_data) + PACKET_OFFSET}, actual size: {len(dataFromServer_MultiMove)}') # 28 is the required buffer
            except zmq.Again:
                print("No acknowledgment received from the server. Retrying...")
                time.sleep(0.5)  # Wait before retrying

        # 4. tell the server to establish the external socket
        # tell the server if this is simulation or real robot mode
        if userInput_modeExe == '1':
            stateMachineKeyword_MM = [2,2,2] # 2 for simulation mode
        else:
            stateMachineKeyword_MM = [1,1,1] # 1 for real robot mode

        dataPkg_to_internal_socket_multiMove = struct.pack("!I" + "d" * len(stateMachineKeyword_MM), len(stateMachineKeyword_MM), *stateMachineKeyword_MM)
        socket_int_multiMove_send.send(dataPkg_to_internal_socket_multiMove)

        # 5. Listen for data from the server and print it
        toggle_listeningFromServer = False
        while not toggle_listeningFromServer:
            acknowledgeFromServer = (99,99,99)
            try:
                dataFromServer_MultiMove = socket_int_multiMove_recv.recv(MAX_PACKET_SIZE)

                if not dataFromServer_MultiMove is None:
                    # Ensure the specific buffer size
                    if len(dataFromServer_MultiMove) >= struct.calcsize(fmt_elen):
                        elen = struct.unpack_from(fmt_elen, dataFromServer_MultiMove)[0]
                        fmt_data = "!" + "d" * elen
                        # Ensure the buffer is large enough for the format string and offset:
                        if len(dataFromServer_MultiMove) == struct.calcsize(fmt_data) + PACKET_OFFSET:
                            data = struct.unpack_from(fmt_data, dataFromServer_MultiMove, PACKET_OFFSET)
                            if data == acknowledgeFromServer:
                                toggle_listeningFromServer = True
                                print("Acknowledgment received from the multimove server. External socket establisehd.")
                        else:
                            # mitigate buffer overflow by discarding the data if it's larger than expected
                            print(f'debugging the buffer size: {struct.calcsize(fmt_data) + PACKET_OFFSET}, actual size: {len(dataFromServer_MultiMove)}') # 28 is the required buffer
            except zmq.Again:
                print("No acknowledgment received from the multimove server. Retrying...")
                time.sleep(0.5)  # Wait before retrying

        # 6. Establish the server, internal socket for cobot
        socket_int_cobot_send = zmq.Context().socket(zmq.PUSH)
        socket_int_cobot_send.setsocketopt(zmq.RCVTIMEO, 500)  # Set a timeout of 500 milliseconds (0.5 second)
        socket_int_cobot_send.bind("tcp://*:5555")
        socket_int_cobot_recv = zmq.Context().socket(zmq.PULL)
        socket_int_cobot_recv.setsocketopt(zmq.RCVTIMEO, 500)  # Set a timeout of 500 milliseconds (0.5 second)
        socket_int_cobot_recv.bind("tcp://*:5556")

        # 7. Execute the internal socket for cobot
        if is_this_simulation:
            subprocess.Popen(['start', 'cmd', '/k', 'python', 'server_cobot.py'], shell=True)
        else:
            subprocess.Popen(['start', 'cmd', '/k', PATH_OF_THIS_ENV, PATH_TO_COBOT], shell=True)
 
        # 8. Acknowledge from the server cobot
        toggle_listeningFromServer = False
        while not toggle_listeningFromServer:
            acknowledgeFromServer = (99,99,99)
            try:
                dataFromServer_Cobot = socket_int_cobot_recv.recv(MAX_PACKET_SIZE)
                if not dataFromServer_Cobot is None:
                    # Ensure the specific buffer size
                    if len(dataFromServer_Cobot) >= struct.calcsize(fmt_elen):
                        elen = struct.unpack_from(fmt_elen, dataFromServer_Cobot)[0]
                        fmt_data = "!" + "d" * elen
                        # Ensure the buffer is large enough for the format string and offset:
                        if len(dataFromServer_Cobot) == struct.calcsize(fmt_data) + PACKET_OFFSET:
                            data = struct.unpack_from(fmt_data, dataFromServer_Cobot, PACKET_OFFSET)
                            if data == acknowledgeFromServer:
                                toggle_listeningFromServer = True
                                print("Acknowledgment received from the cobot server. Starting to listen for data...")
                        else:
                            # mitigate buffer overflow by discarding the data if it's larger than expected
                            print(f'debugging the buffer size: {struct.calcsize(fmt_data) + PACKET_OFFSET}, actual size: {len(dataFromServer_Cobot)}') # 28 is the required buffer
            except zmq.Again:
                print("No acknowledgment received from the cobot server. Retrying...")
                time.sleep(0.5)  # Wait before retrying

        # 9. tell the cobot server to establish the external socket
        # tell the server if this is simulation or real robot mode
        if userInput_modeExe == '1':
            stateMachineKeyword_Cobot = [2,2,2] # 2 for simulation mode
        else:
            stateMachineKeyword_Cobot = [1,1,1] # 1 for real robot mode   
        dataPkg_to_internal_socket_cobot = struct.pack("!I" + "d" * len(stateMachineKeyword_Cobot), len(stateMachineKeyword_Cobot), *stateMachineKeyword_Cobot)
        socket_int_cobot_send.send(dataPkg_to_internal_socket_cobot)

        # 10. Listen for data from the cobot server and print it
        toggle_listeningFromServer = False
        while not toggle_listeningFromServer:
            acknowledgeFromServer = (99,99,99)
            try:
                dataFromServer_Cobot = socket_int_cobot_recv.recv(MAX_PACKET_SIZE)

                if not dataFromServer_Cobot is None:
                    # Ensure the specific buffer size
                    if len(dataFromServer_Cobot) >= struct.calcsize(fmt_elen):
                        elen = struct.unpack_from(fmt_elen, dataFromServer_Cobot)[0]
                        fmt_data = "!" + "d" * elen
                        # Ensure the buffer is large enough for the format string and offset:
                        if len(dataFromServer_Cobot) == struct.calcsize(fmt_data) + PACKET_OFFSET:
                            data = struct.unpack_from(fmt_data, dataFromServer_Cobot, PACKET_OFFSET)
                            if data == acknowledgeFromServer:
                                toggle_listeningFromServer = True
                                print("Acknowledgment received from the cobot server.External socket establisehd.")
                        else:
                            # mitigate buffer overflow by discarding the data if it's larger than expected
                            print(f'debugging the buffer size: {struct.calcsize(fmt_data) + PACKET_OFFSET}, actual size: {len(dataFromServer_Cobot)}') # 28 is the required buffer
            except zmq.Again:
                print("No acknowledgment received from the cobot server. Retrying...")
                time.sleep(0.5)  # Wait before retrying

            while True:
                try:
                    userInput_execution = input("Enter 'y' for state motion, 's' for streaming, 'n' to quit: ")

                    if userInput_execution.lower() == 'y':
                        userPathSelection = input("Input desired path for the robot to execute (1A, 1B, 2A, 2B): ")

                        stateExeList = LinkedList()
                        if userPathSelection in object_group_1:
                            # Example sequence: Home -> Standby -> Stream -> Home
                            # "Stream" nodes trigger interactive_streaming_handler mid-execution
                            stateExeList.append("Home", "CB_Home", 1)
                            stateExeList.append("Standby", "CB_Standby", 2)
                            stateExeList.append(STREAMING_STATE_NAME, "CB_Home", 2)  # MM enters streaming, CB holds Home
                            stateExeList.append("Home", "CB_Home", 3)
                        elif userPathSelection in object_group_2:
                            # State-only sequence (no streaming)
                            stateExeList.append("Home", "CB_Home", 1)
                            stateExeList.append("Standby", "CB_Standby", 2)
                            stateExeList.append("Home", "CB_Home", 3)
                        else:
                            print(f'wrong path selected')

                        stateExeList.traverse_and_execute(
                            stateExeList.head, userPathSelection,
                            socket_int_multiMove_send, socket_int_multiMove_recv,
                            socket_int_cobot_send, socket_int_cobot_recv,
                            streaming_handler=interactive_streaming_handler
                        )

                    elif userInput_execution.lower() == 's':
                        # PHASE 2: Standalone streaming mode (not linked to a state sequence)
                        interactive_streaming_handler(
                            socket_int_multiMove_send, socket_int_multiMove_recv
                        )

                    else:
                        # send termination code to the connected servers before breaking the loop and terminating the program
                        stateMachineKeyword = [0,0,0] # 0 for termination
                        dataPkg_to_internal_socket = struct.pack("!I" + "d" * len(stateMachineKeyword), len(stateMachineKeyword), *stateMachineKeyword)
                        socket_int_multiMove_send.send(dataPkg_to_internal_socket)
                        socket_int_multiMove_recv.close()
                        socket_int_multiMove_send.close()
                        socket_int_cobot_send.send(dataPkg_to_internal_socket)
                        socket_int_cobot_recv.close()
                        socket_int_cobot_send.close()
                        print("Program terminated by the user.")
                        sys.exit()

                    time.sleep(0.1) # 10Hz loop for user input

                except OSError as e:
                    if e.errno == 11:  # Resource temporarily unavailable (EAGAIN)
                        print("No input received. Retrying...")
                        time.sleep(0.5)  # Wait before retrying
                    else:
                        raise  # Re-raise the exception if it's not EAGAIN

    else:
        print("Type correct connection type")
        userInput_modeExe = input("Enter '1' for simulation mode or '2' for real robot mode: ") 

if __name__ == "__main__":
    main()
