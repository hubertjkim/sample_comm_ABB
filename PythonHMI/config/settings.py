""" Centeral configuration settings for the application. """

from enum import Enum


class OperationMode(Enum):
    """Operation modes for robot controllers"""
    VIRTUAL_CONTROLLER = 1
    REAL_CONTROLLER = 2
    INTERNAL_SOCKET_ONLY = 3

class Config:
    """Central Configuration class for all system settings."""

    # === Network Configuration ===
    # ZMQ Socket Configuration
    ZMQ_RECV_TIMEOUT = 500 # milliseconds
    MAX_PACKET_SIZE = 1024 # bytes
    PACKET_FORMAT_ELEN = "!I" # 4-byte unsigned int for packet length. 
    PACKET_OFFSET = 4 # bytes to skip for packet length header. 4 byte is equivalent to "I" in struct format.

    # Multimove socket ports
    MM_SEND_PORT =8080
    MM_RECV_PORT =8081

    # Cobot socket ports
    CB_SEND_PORT =8082
    CB_RECV_PORT =8083

    # === Execution Configuration ===
    IS_LAB_COMPUTER = True # Set to False if running on a non-lab computer 

    # === Loop frequencies === 
    EXECUTION_LOOP_FREQ = 0.2 # 5 Hz
    MAIN_LOOP_FREQ = 0.1 # 10 Hz
    SOCKET_RETRY_DELAY = 0.1 # 100 ms

    # === Acknowledgment Configuration ===
    ACK_SERVER_INIT = (99, 99, 99)
    ACK_MOTION_COMPLETE = (99, 99, 0)
    TERMINATION_CODE = [0, 0, 0]

    @classmethod
    def get_operation_mode(cls, mode_str: str) -> tuple:
        """Get the operation mode based on a string input.
        Args:
            mode_str (str): user mode selection ("1", "2", or "3")

        Returns:
            tuple: (OperationMode, str) - The selected operation mode for multimove and cobot.
            
        """
        mode_mapping = {
            "1": (OperationMode.REAL_CONTROLLER, OperationMode.INTERNAL_SOCKET_ONLY), # Multimove in real controller mode, Cobot in internal socket only mode
            "2": (OperationMode.VIRTUAL_CONTROLLER, OperationMode.INTERNAL_SOCKET_ONLY), # Multimove in virtual controller mode, Cobot in internal socket only mode
            "3": (OperationMode.INTERNAL_SOCKET_ONLY, OperationMode.VIRTUAL_CONTROLLER) # Multimove in internal socket only mode, Cobot in virtual controller mode
        }
        return mode_mapping.get(mode_str, (OperationMode.INTERNAL_SOCKET_ONLY, OperationMode.INTERNAL_SOCKET_ONLY))
