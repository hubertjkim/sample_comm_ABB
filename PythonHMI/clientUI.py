import socket
import zmq
import subprocess
import time
import struct
import sys
from typing import Optional
from src.communication.data_structure import LinedList
from config.constatns import (
    object_group_1,
    object_group_2,
)
import csv


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
                    userInput_execution = input("Do you want to continue executing the program? (y/n): ")

                    if userInput_execution.lower() == 'y':
                        userPathSelection = input ("Input desired path for the robot to execute (1 or 2):  ")

                        stateExeList = LinedList()
                        if userPathSelection in object_group_1:
                            for state in object_group_1[userPathSelection]:
                                stateExeList.append(state)
                                stateExeList.append("Home", "CB_Home", 1)
                                stateExeList.append("Standby", "CB_Standby", 2)
                                stateExeList.append("Home", "CB_Standby", 2)
                                stateExeList.append("Home", "CB_Home", 3)
                        else:
                            print(f'wrong path selected')

                        stateExeList.travers_and_execute(stateExeList.head, userPathSelection,
                                                         socket_int_multiMove_send, socket_int_multiMove_recv,
                                                         socket_int_cobot_send, socket_int_cobot_recv)
                    
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
