import zmq
import struct
import time
import sys
from src.communication.socket_manager import ExtSocketServer
from src import state_machines
from config.constants import pathDict, stateSequence_Cobot
from config.lookupTables import retrieve_motion_settings as retrieve_motion_settings_Cobot
import csv

tempClientState = state_machine.CB_Home()

context = zmq.Context()
socket_ext_Cobot = None

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
def send_command_to_external_socket(userPathSelection: int, userSequenceSelection: int, tempClientState: state_machines, socket_ext_Cobot: ExtSocketServer)->list[int]:
    global temporary_sequence

    userPathSelection = str(list(pathDict)[userPathSelection-1])
    print(f"User path selection: {userPathSelection}")
    userSequenceSelection = str(stateSequence_Cobot[userSequenceSelection-1])
    print(f"User sequence selection: {userSequenceSelection}")

    tempClientState = retrieveMotionSettings(tempClientState, userPathSelection, userSequenceSelection)

    # Inherit the state machine class and create an instance of the selected sequence
    match userSequenceSelection:
        case "Standby":
            data_list = list(tempClientState.grab_data_CB('1'))
        case "Standby_R1":
            data_list = list(tempClientState.grab_data_CB('2'))

        case "Approach":
            data_list = list(tempClientState.grab_data_CB('1'))
        case "Approach_R1":
            data_list = list(tempClientState.grab_data_CB('2'))

    # send command to external sockt and receive the response
    socket_ext_Cobot.send_data(data_list, 'd;')
    print(f'Data sent to external socket: {data_list}   with length: {len(data_list)}  ')

    # not looping if we don't complete the motion
    done_Cobot = False
    while not done_Cobot:
        complete_flag_CB = socket_ext_Cobot.receive_data()
        print(f"Response received from external socket: {complete_flag_CB}")
        if not complete_flag_CB is None and len(complete_flag_CB) == 6 :
            if complete_flag_CB[0] == 9:
                print("Motion completed successfully.")
                done_Cobot = True   
            
    return data_list

def main()->None:
    global internal_socket_only, previous_sequence, wasPreviousExecutionSuccessful, fmt_elen, PACKET_OFFSET, MAX_PACKET_SIZE


    # socket to talk to client
    print("Initializing external CB socket server...")
    soceketClient_receive = context.socket(zmq.PULL)
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
        message  = soceketClient_receive.recv(MAX_PACKET_SIZE)
        if not message is None:
            # Ensure the specific buffer size
            if len(message) >= struct.calcsize(fmt_elen):
                elen = struct.unpack(fmt_elen, message)[0]
                fmt_data = "!" + "d" * elen
                # Ensure the buffer is large enough to contain the expected data
                if len(message) == struct.calcsize(fmt_elen) + PACKET_OFFSET:
                    data = struct.unpack(fmt_data, message, PACKET_OFFSET)
                    if data == (2, 2, 2): # Real Controller, RC
                        print("Connected to Real Controller.")
                        socket_ext_Cobot: ExtSocketServer = ExtSocketServer("192.168.0.100", 5024).create_socket()

                    elif data == (1, 1, 1): # Virtual Controller, VC
                        print("Connected to Virtual Controller.")
                        socket_ext_Cobot: ExtSocketServer = ExtSocketServer("127.0.0.1", 5024).create_socket()
                        socket_ext_Cobot.send_data([0,0,0], 'I;') # send array with I data type
                        acknowledgeFromServer = False
                        while not acknowledgeFromServer:
                            complete_flag_CB = socket_ext_Cobot.receive_data()
                            if not complete_flag_CB is None and len(complete_flag_CB) == 6 :
                                if complete_flag_CB[0] == 1:
                                    print("Acknowledgement received from virtual controller, Cobot")
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
                message  = soceketClient_receive.recv(MAX_PACKET_SIZE)
                if not message is None:
                    # Ensure the specific buffer size
                    if len(message) >= struct.calcsize(fmt_elen):
                        elen = struct.unpack(fmt_elen, message)[0]
                        fmt_data = "!" + "d" * elen
                        # Ensure the buffer is large enough to contain the expected data
                        if len(message) == struct.calcsize(fmt_elen) + PACKET_OFFSET:
                            data = struct.unpack(fmt_data, message, PACKET_OFFSET)
                            if data == (0, 0, 0): # termination command from client
                                print("Termination command received from client. Exiting...")

                                if not internal_socket_only:
                                    # send out the "close socket command"
                                    socket_ext_Cobot.send_data([0,0,0], 'T;') 
                                    socket_ext_Cobot.close_socket()
                                    soceketClient_receive.close()
                                    soceketClient_send.close()
                                    sys.exit()
                            
                            else:
                                # forever loop begins here:
                                if not internal_socket_only:
                                    if not previous_sequence == data[1]: # if we're running two consecutive identical sequnces, then skip it
                                        send_command_to_external_socket(int(data[0]), int(data[1]), tempClientState, socket_ext_Cobot)
                                        previous_sequence = data[1]
                                        wasPreviousExecutionSuccessful = True

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
                raise  # re-raise the exception if it's not EAGAIN

if __name__ == "__main__":
    main()
    