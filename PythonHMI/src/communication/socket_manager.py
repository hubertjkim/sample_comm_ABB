"""
Docstring for PythonHMI.src.communication.socket_manager

External socket server for TCP/IP communication with MultiMove and Cobot servers.

This module provides the ExtSocketServer class for managing external socket connctions to ABB robot controllers

"""

import socket
import struct
from typing import List, Optional
from config.settings import Config

class ExtSocketServer:
    """External socket server for TCP/IP communication with robot controllers."""
    def __init__(self, ip_addr:str, port_no:int) -> None:
        """Initialize the external socket server.

        Args:
            ip_addr (str): IP address to bind the server
            port_no (int): Port number to listen on
        """
        self.ip_addr = ip_addr
        self.port_no = port_no
        self.server_socket: Optional[socket.socket] = None

    def create_socket(self) -> 'ExtSocketServer':
        """Create and bind the server socket to the robot controller.

        Returns:
            self for method chaining
        """
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setblocking(False)
        try:
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.connect((self.ip_addr, self.port_no))
        except BlockingIOError:
            pass  # Non-blocking connect will raise this error, which is expected
        return self
    
    def receive_data(self) -> List[float]:
        """Receive data from the robot controller.

        Returns:
            List of float values representing robot position, or empty list if no data received
        """
        try:
            rec_data = self.server_socket.recv(Config.MAX_PACKET_SIZE)
            decoded_str = rcv_data.decode('utf-8')

            if decoded_str[:11] != "IP Accepted":
                decoded_str_splitted = decoded_str.split(",")
                if len(decoded_str_splitted) != 6:
                    return []
                
                robot_pos = []
                for str_data in decoded_str_splitted:
                    robot_pos.append(float(str_data))
                return robot_pos
            else:
                print(f"IP({self.ip_addr}) re-accepted at the server")
                decoded_str_splitted = decoded_str.split(",")
                if len(decoded_str_splitted) != 6:
                    return []
                
                robot_pos = []
                for str_data in decoded_str_splitted:
                    robot_pos.append(float(str_data))
                return robot_pos
            
        except BlockingIOError:
            return []  # No data received, return empty list
        
    def send_data(self, data: List[int], write_data_formatted: str) -> None:
        """Send data to the robot controller.

        Args:
            data: List of command integer values to send
            write_data_formatted: ID header letter for the command
        """
        for i in range(len(data)):
            write_data_formatted += str(data[i])
            if i + 1 < len(data):
                write_data_formatted += ";"

        try:
            self.server_socket.send(bytes(write_data_formatted, 'utf-8'))
        except BlockingIOError:
            print("Failed to send data: Socket is not ready for sending.")
            pass
    
    def close_socket(self) -> None:
        """Close the server socket."""
        if self.server_socket:
            self.server_socket.close()
            