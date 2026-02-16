"""
Docstring for PythonHMI.src.communication.protocol

Protocol handling for ZMQ socket communication.

This module provides functions for packing and unpacking data and managing 
ZMQ sockets for internal communication between client and server processes.
"""

import struct
import zmq
from typing import List, Tuple, Optional
from config.settings import Config

class SocketManager:
    """Manages ZMQ sockets PUSH/PULL socket pairs"""
    def __init__(self, send_port: int, recv_port: int):
        """Initialize socket manager with send and receive ports.
        Args:
            send_port (int): Port for sending data (PUSH socket)
            recv_port (int): Port for receiving data (PULL socket)
        """
        self.context = zmq.Context()
        self.send_socket = send_port
        self.recv_socket = recv_port
        self.send_socket: Optional[zmq.Socket] = None
        self.recv_socket: Optional[zmq.Socket] = None

    def create_sockets(self) -> Tuple[zmq.Socket, zmq.Socket]:
        """Create and bind ZMQ PUSH and PULL sockets Pair.
        Returns:
            Tuple[zmq.Socket, zmq.Socket]: The created send and receive sockets.
        """
        self.socket_send = self.context.socket(zmq.PUSH)
        self.socket_send.setsockopt(zmq.RCVTIMEO, Config.ZMQ_RECV_TIMEOUT)
        self.socket_send.bind(f"tcp://*:{self.send_socket}")

        self.socket_recv = self.context.socket(zmq.PULL)
        self.socket_recv.setsockopt(zmq.RCVTIMEO, Config.ZMQ_RECV_TIMEOUT)
        self.socket_recv.bind(f"tcp://*:{self.recv_socket}")
    
        return self.socket_send, self.socket_recv
    
    def close_sockets(self) -> None:
        """Close the ZMQ sockets."""
        if self.socket_send:
            self.socket_send.close()
        if self.socket_recv:
            self.socket_recv.close()
        
def pack_data(data: List[str]) -> bytes:
    """
    Pack data into binary format for transmission.

    Args:
        data: List of float values to pack

    Returns:
        Packed binary data
    """
    return struct.pack(
        Config.PACKET_FORMAT_ELEN +"d"*len(data),
        len(data),
        *data
    )

def unpack_data(message: bytes) -> Optional[Tuple[float,...]]:
    """
    Unpack binary data received from a socket.
    Args:
        message: The binary message to unpack
    Returns:
        A tuple of unpacked float values, or None if unpacking fails
    """
    try:
        # Ensure the specific buffer size for element count
        if len(message) < struct.calcsize(Config.PACKET_FORMAT_ELEN):
            return None
        
        elen = struct.unpack_from(Config.PACKET_FORMAT_ELEN, message)[0]
        fmt_data = "!" + "d" * elen

        # Ensure the buffer is large enough for the expected data
        expected_size = struct.calcsize(fmt_data) + Config.PACKET_OFFSET
        if len(message) != expected_size:
            print(f"Received message size {len(message)} does not match expected size {expected_size}")
            return None
        
        data = struct.unpack_from(fmt_data, message, Config.PACKET_OFFSET)
        return data
    
    except struct.error as e:
        print(f"Error unpacking data: {e}")
        return None