"""Data structures for command sequencing and execution.

Ths module provides LinkedList and Node classes to manage sequential 
command exeucution for tripple robot coordination (two robots in MultiMove and one robot in Cobot)
"""

import struct
import time
import zmq
from typing import Optional

from config.settings import Config
from config.constants import StateSequence_MM, StateSequence_CB, PathDict

class Node:
    """Node in a linked list representing a robot command."""
    def __init__(self, new_data_server_1:str, new_data_server_2:str, 
                 this_head_1_tail_3: int, next_node=None):
        """
        Initialize a command node.

        Args:
            new_data_server_1 (str): Command for serve 1 (MultiMove)
            new_data_server_2 (str): Command for serve 2 (Cobot)
            this_head_1_tail_3 (int): Header flag (1= head, 2=middle, 3=tail)
            next_node: Net node in the list
        """

        self.data_1 = new_data_server_1
        self.data_2 = new_data_server_2
        self.checkLineExec = this_head_1_tail_3
        self.next = next_node

        def __str__(self):
            return f"({self.data_1}, {self.data_2})"
        
        def get_server_1(self) -> str:
            """Get the command for server 1 (MultiMove)."""
            return str(self.data_1)
        
        def get_server_2(self) -> str:
            """Get the command for server 2 (Cobot)."""
            return str(self.data_2)
        
class LinkedList:
    """Linked list to manage a sequence of robot commands."""
    def __init__(self):
        """Initialize an empty linked list."""
        self.head: Optional[Node] = None

    def append(self, new_data_server_1:str, new_data_server_2:str, this_head_1_tail_3: int) -> None:
        """Append a new command node to the end of the list.

        Args:
            new_data_server_1 (str): Command for server 1 (MultiMove)
            new_data_server_2 (str): Command for server 2 (Cobot)
            this_head_1_tail_3 (int): Header flag (1= head, 2=middle, 3=tail)
        """
        new_node = Node(new_data_server_1, new_data_server_2, this_head_1_tail_3)

        if not self.head:
            self.head = new_node
        else:
            current = self.head
            while current.next:
                current = current.next
            current.next = new_node

    def print_list_recursive(self, node: Optional[Node]) -> None:
        """Recursively print all the nodes. (for debugging)"""
        if node is not None:
            return
        print(node)
        self.print_list_recursive(node.next)

    def print_each_list_recursive(self, node: Optional[Node]) -> None:
        """Print each node in the linked list recursively. (for debugging)"""
        if node is not None:
            return
        print(f'Server 1: {StateSequence_MM[node.get_server_1()]}', end='')
        print(f'Server 2: {StateSequence_CB[node.get_server_2()]}')
        self.print_each_list_recursive(node.next)

    def search_recursive(self, node: Optional[Node], value:str) -> Optional[Node]:
        """Recursively search for a node with a specific command.

        Args:
            node: Current node in the recursion
            value: Command to search for

        Returns:
            The node containing the command, or None if not found.
        """
        if node is None:
            return None
        if node.data_1 == value or node.data_2 == value:
            return node
        return self.search_recursive(node.next, value)
    
    def traverse_and_execute(self, node: Optional[Node], user_path_selection:str,
                             socket_int_multimove_send: zmq.Socket, 
                             socket_int_multimove_recv: zmq.Socket, 
                                socket_int_cobot_send: zmq.Socket,
                                socket_int_cobot_recv: zmq.Socket) -> None:
        """Traverse the linked list and execute commands sequentially.
        Args:
            node: Current node in the recursion
            user_path_selection: Selected path identifier
            socket_int_multimove_send: ZMQ socket for sending commands to MultiMove
            socket_int_multimove_recv: ZMQ socket for receiving responses from MultiMove
            socket_int_cobot_send: ZMQ socket for sending commands to Cobot
            socket_int_cobot_recv: ZMQ socket for receiving responses from Cobot
        """
        # if the node is empty, stop
        if node is None:
            return
        
        # if the line is ready to run
        toggle_listening_from_client_MM = False
        toggle_listening_from_client_CB = False

        if (node.headerCHK == 1) or node.checkLineExec:
            # For MM, send cmd (async version-- non-blocking for fire-and-forget)
            path_int = PathDict[user_path_selection]
            state_machine_keyword_mm = [
                path_int,
                StateSequence_MM[node.get_server_1()]
                node.headerCHK
            ]
            data_pkg_to_int_sock_mm = struct.pack(
                "!I" + "d" * len(state_machine_keyword_mm),
                len(state_machine_keyword_mm),
                *state_machine_keyword_mm
            )
            socket_int_multimove_send.send(data_pkg_to_int_sock_mm, zmq.NOBLOCK)
            print(f'command sent to MM server: {node.get_server_1()}')

            # For CB, send cmd (async version-- non-blocking for fire-and-forget)
            state_machine_keyword_cb = [
                path_int,
                StateSequence_CB[node.get_server_2()]
                node.headerCHK
            ]
            data_pkg_to_int_sock_cb = struct.pack(
                "!I" + "d" * len(state_machine_keyword_cb),
                len(state_machine_keyword_cb),
                *state_machine_keyword_cb
            )
            socket_int_cobot_send.send(data_pkg_to_int_sock_cb, zmq.NOBLOCK)
            print(f'command sent to CB server: {node.get_server_2()}')

        # Acknowledge from servers, before next line of execution
        acknowledge_code_from_server = Config.ACK_MOTION_COMPLETE

        while not toggle_listening_from_client_MM or not toggle_listening_from_client_CB:
            # Listen for MM response
            if not toggle_listening_from_client_MM:
                try:
                    data_from_server_mm = socket_int_multimove_recv.recv(Config.MAX_BUFFER_SIZE)
                    if data_from_server_mm is not None:
                        # Ensure the specific buffer size is received
                        if len(data_from_server_mm) >= struct.calcsize(Config.PACKET_FORMAT_ELEN):
                            elen = struct.unpack_from(Config.PACKET_FORMAT_ELEN, data_from_server_mm)[0]
                            fmt_data = "!" + "d" * elen
                            # Ensure the buffer is large enough
                            if len(data_from_server_mm) == struct.calcsize(fmt_data) + Config.PACKET_OFFSET:
                                data = struct.unpack_from(fmt_data, data_from_server_mm, Config.PACKET_OFFSET)
                                if data ==  acknowledge_code_from_server:
                                    print(f'Acknowledgment received from MM server for command')
                                    toggle_listening_from_client_MM = True
                                else:
                                    print(f' debugging buffer size-1: {struct.calcsize(fmt_data) + Config.PACKET_OFFSET}')
                except zmq.Again:
                    time.sleep(Config.SOCKET_RETRY_DELAY)

            if not toggle_listening_from_client_CB:
                try:
                    data_from_server_cb = socket_int_cobot_recv.recv(Config.MAX_BUFFER_SIZE)
                    if data_from_server_cb is not None:
                        # Ensure the specific buffer size is received
                        if len(data_from_server_cb) >= struct.calcsize(Config.PACKET_FORMAT_ELEN):
                            elen = struct.unpack_from(Config.PACKET_FORMAT_ELEN, data_from_server_cb)[0]
                            fmt_data = "!" + "d" * elen
                            # Ensure the buffer is large enough
                            if len(data_from_server_cb) == struct.calcsize(fmt_data) + Config.PACKET_OFFSET:
                                data = struct.unpack_from(fmt_data, data_from_server_cb, Config.PACKET_OFFSET)
                                if data ==  acknowledge_code_from_server:
                                    print(f'Acknowledgment received from CB server for command')
                                    toggle_listening_from_client_CB = True
                                else:
                                    print(f' debugging buffer size-2: {struct.calcsize(fmt_data) + Config.PACKET_OFFSET}')
                except zmq.Again:
                    time.sleep(Config.SOCKET_RETRY_DELAY)

        # Allow next line command only if the current line is done
        if node.next is not None:
            node.next.checkLineExec =  True

        # Loop at configured frequency
        time.sleep(Config.EXECUTION_LOOP_FREQ)
        self.traverse_and_execute(
            node.next, user_path_selection, 
            socket_int_multimove_send, socket_int_multimove_recv,
            socket_int_cobot_send, socket_int_cobot_recv
        )

    