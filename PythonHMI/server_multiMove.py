import zmq
import struct
import time
import sys
import math
from src.communication.socket_manager import ExtSocketServer
from src import state_machines
from config.constants import pathDict, stateSequence_MultiMove
from config.lookupTables import retrieve_motion_settings as retrieve_motion_settings_MultiMove
import csv

tempClientState = state_machine.MM_Home()

context = zmq.Context()
socket_ext_Multimove = None

internal_socket_only = False
previous_sequence = 99 # if we're running two consecutive identical sequnces, then skip it
temporary_sequence = 00 # temporarily save the current sequence for the next loop to compare with previous sequence, if they are identical, then skip it
wasPreviousExecutionSuccessful = False # to check sudden termination of the execution.

MAX_PACKET_SIZE = 1024
fmt_elen = "!I"  # unsigned int (4 bytes)
PACKET_OFFSET = 4 # the first 4 bytes are used to indicate the length of the data packet, so the actual data starts from byte 5 (index 4)

# Function to traverse and print the linked list
# starting from the head node, recursively
# return the array for debugging purpose
def send_command_to_external_socket(userPathSelection: int, userSequenceSelection: int, tempClientState: state_machines, socket_ext_Multimove: ExtSocketServer)->list[int]:
    global temporary_sequence

    userPathSelection = str(list(pathDict)[userPathSelection-1])
    print(f"User path selection: {userPathSelection}")
    userSequenceSelection = str(stateSequence_MultiMove[userSequenceSelection-1])
    print(f"User sequence selection: {userSequenceSelection}")

    tempClientState = retrieveMotionSettings(tempClientState, userPathSelection, userSequenceSelection)

    # Inherit the state machine class and create an instance of the selected sequence
    match userSequenceSelection:
        case "Standby":
            data_list = list(tempClientState.grab_data_MM('1'))
        case "Standby_R1":
            data_list = list(tempClientState.grab_data_MM('2'))

        case "Approach":
            data_list = list(tempClientState.grab_data_MM('1'))
        case "Approach_R1":
            data_list = list(tempClientState.grab_data_MM('2'))

    # send command to external sockt and receive the response
    socket_ext_Multimove.send_data(data_list, 'd;')
    print(f'Data sent to external socket: {data_list}   with length: {len(data_list)}  ')

    # not looping if we don't complete the motion
    done_Multimove = False
    while not done_Multimove:
        complete_flag_MM = socket_ext_Multimove.receive_data()
        print(f"Response received from external socket: {complete_flag_MM}")
        if not complete_flag_MM is None and len(complete_flag_MM) == 6 :
            if complete_flag_MM[0] == 9:
                print("Motion completed successfully.")
                done_Multimove = True   
            
    return data_list

def send_joint_stream(joint_values: list[float], socket_ext: ExtSocketServer) -> bool:
    """Send a single joint streaming packet to the robot controller.

    Args:
        joint_values: List of 6 float values [j1, j2, j3, j4, j5, j6] in degrees
        socket_ext: The external socket connection to the robot controller

    Returns:
        True if motion completed successfully
    """
    socket_ext.send_data(joint_values, 'j;')
    print(f'Joint stream sent: {joint_values}')

    # Wait for acknowledgment
    done = False
    while not done:
        response = socket_ext.receive_data()
        if response is not None and len(response) == 6:
            if response[0] == 9:
                print("Joint stream motion completed.")
                done = True
    return True

def run_streaming_test(socket_ext: ExtSocketServer):
    """Test joint streaming with a simple sine wave motion pattern.

    Sends 20 joint target points with a small oscillation on J1.
    Safe for testing - only moves +/- 5 degrees on joint 1.
    """
    print("Starting joint streaming test...")
    t = 0
    frequency = 2.0  # 2 Hz for safety during testing
    period = 1.0 / frequency

    # Base joint position (safe starting position - adjust for your robot)
    base_joints = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    try:
        for i in range(20):  # 20 points for testing
            start_time = time.time()

            # Small oscillation on joint 1 only (safe test)
            joints = base_joints.copy()
            joints[0] = base_joints[0] + 5.0 * math.sin(t)  # +/- 5 degrees on J1

            send_joint_stream(joints, socket_ext)
            t += 0.3

            elapsed = time.time() - start_time
            sleep_time = period - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("Streaming test stopped by user.")

    print("Joint streaming test completed.")

def main()->None:
    global internal_socket_only, previous_sequence, wasPreviousExecutionSuccessful, fmt_elen, PACKET_OFFSET, MAX_PACKET_SIZE


    # socket to talk to client
    print("Initializing external MM socket server...")
    soceketClient_receive = context.socket(zmq.PULL)
    soceketClient_receive.setsockopt(zmq.RCVTIMEO, 5000)  # 5s timeout so Ctrl+C can interrupt
    soceketClient_receive.connect("tcp://localhost:8080")
    soceketClient_send = context.socket(zmq.PUSH)
    soceketClient_send.connect("tcp://localhost:8081")

    # 0. acknowledgement to client after external socket
    acknowledgeToClient = [99,99,99]
    dataPkg_to_Client = struct.pack("!I" + "d"*len(acknowledgeToClient), len(acknowledgeToClient), *acknowledgeToClient)
    soceketClient_send.send(dataPkg_to_Client)
    print("Acknowledgement sent to client.")

    # 1. Listen to the lcient & Connect to robot, see if this is VC or RC
    toggle_listeningFromClient = False
    while not toggle_listeningFromClient:
        try:
            message = soceketClient_receive.recv(MAX_PACKET_SIZE)
        except zmq.Again:
            continue
        if not message is None:
            # Ensure the specific buffer size
            if len(message) >= struct.calcsize(fmt_elen):
                elen = struct.unpack_from(fmt_elen, message)[0]
                fmt_data = "!" + "d" * elen
                # Ensure the buffer is large enough to contain the expected data
                if len(message) == struct.calcsize(fmt_data) + PACKET_OFFSET:
                    data = struct.unpack_from(fmt_data, message, PACKET_OFFSET)
                    if data == (2, 2, 2): # Real Controller, RC
                        print("Connected to Real Controller.")
                        socket_ext_Multimove: ExtSocketServer = ExtSocketServer("192.168.0.100", 5024).create_socket()

                    elif data == (1, 1, 1): # Virtual Controller, VC
                        print("Connected to Virtual Controller.")
                        socket_ext_Multimove: ExtSocketServer = ExtSocketServer("127.0.0.1", 5024).create_socket()
                        socket_ext_Multimove.send_data([0,0,0], 'I;') # send array with I data type
                        acknowledgeFromServer = False
                        while not acknowledgeFromServer:
                            complete_flag_MM = socket_ext_Multimove.receive_data()
                            if not complete_flag_MM is None and len(complete_flag_MM) == 6 :
                                if complete_flag_MM[0] == 1:
                                    print("Acknowledgement received from virtual controller, multimove")
                                    acknowledgeFromServer = True
                    elif data == (3,3,3): # internal socket
                        print("Internal socket communication only, no connection to external socket.")
                        internal_socket_only = True
                    toggle_listeningFromClient = True
                else:
                    # mitigate buffer too small
                    print(f"debugging buffer size: : {struct.calcsize(fmt_data)+PACKET_OFFSET}" )
                
    # 2. Acknowledge back the client after external socket connection is established
    dataPkg_to_Client = struct.pack("!I" + "d"*len(acknowledgeToClient), len(acknowledgeToClient), *acknowledgeToClient)
    soceketClient_send.send(dataPkg_to_Client)
    print("Acknowledgement sent to client after external socket connection is established.")

    while True:
        try:
            # 3. Always check the terminaation condition first:
            toggle_listeningFromClient = False
            while not toggle_listeningFromClient:
                try:
                    message = soceketClient_receive.recv(MAX_PACKET_SIZE)
                except zmq.Again:
                    continue
                if not message is None:
                    # Ensure the specific buffer size
                    if len(message) >= struct.calcsize(fmt_elen):
                        elen = struct.unpack_from(fmt_elen, message)[0]
                        fmt_data = "!" + "d" * elen
                        # Ensure the buffer is large enough to contain the expected data
                        if len(message) == struct.calcsize(fmt_data) + PACKET_OFFSET:
                            data = struct.unpack_from(fmt_data, message, PACKET_OFFSET)
                            if data == (0, 0, 0): # termination command from client
                                print("Termination command received from client.")
                                break  # exit to cleanup below

                            else:
                                # Dispatch based on message length (elen):
                                # elen == 3: state motion from clientUI (path, sequence, head_or_tail)
                                # elen == 6: joint streaming (j1, j2, j3, j4, j5, j6)
                                if not internal_socket_only:
                                    if elen == 6:
                                        # PHASE 2: Joint streaming mode
                                        joint_values = [float(data[i]) for i in range(6)]
                                        print(f'[Joint Stream] joints: {joint_values}')
                                        send_joint_stream(joint_values, socket_ext_Multimove)
                                    elif elen == 3:
                                        # State motion: data = (path, sequence, head-1 or tail-3)
                                        print(f'[State Motion] path: {data[0]}, sequence: {data[1]}, head/tail: {data[2]}')
                                        # Only send if sequence changed (skip consecutive identical sequences)
                                        if not previous_sequence == data[1]:
                                            send_command_to_external_socket(int(data[0]), int(data[1]), tempClientState, socket_ext_Multimove)
                                            previous_sequence = data[1]
                                            wasPreviousExecutionSuccessful = True
                                    else:
                                        print(f'[Unknown] elen={elen}, data={data}')

                                # send back the acknowledgement
                                acknowledgeToClient = [99,99,99]
                                dataPkg_to_Client = struct.pack("!I" + "d"*len(acknowledgeToClient), len(acknowledgeToClient), *acknowledgeToClient)
                                soceketClient_send.send(dataPkg_to_Client, zmq.NOBLOCK)
                                print("Acknowledgement sent to client after motion execution.")
                            toggle_listeningFromClient = True
                        else:
                            # mitigate buffer too small
                            print(f"debugging buffer size: : {struct.calcsize(fmt_data)+PACKET_OFFSET}" )
        
        except OSError as e:
            if e.errno == 11:  # EAGAIN error, no data received
                print("No data received, continuing to listen...")
                continue
            else:
                raise
        except KeyboardInterrupt:
            print("\nCtrl+C detected. Shutting down...")
            break

    # Cleanup: close all sockets regardless of how we exited the loop
    print("Cleaning up sockets...")
    try:
        if not internal_socket_only:
            socket_ext_Multimove.send_data([0,0,0], 'T;')
            socket_ext_Multimove.close_socket()
    except Exception:
        pass
    soceketClient_receive.close()
    soceketClient_send.close()
    context.term()
    print("Server shutdown complete.")

if __name__ == "__main__":
    main()
    