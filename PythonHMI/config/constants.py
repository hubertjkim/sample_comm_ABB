"""Constants and lookup tables 

This module containts all the path, tool, state, and group definitions

"""

from enum import Enum
from typing import Set


class OperationMode (Enum):
    """Defines the operation mode of the HMI, either for multimove or cobot control"""
    VIRTUAL_CONTROLLER = 1
    REAL_CONTROLLER = 2
    INTERNAL_SOCKET_ONLY = 3

PathDict = {
    "1A": 1,
    "1B": 2,
    "2A": 3,
    "2B": 4,}

ToolDict_MM = {
    "tool0": 1,
    "tool1": 2,}

ToolDict_CB = {
    "tool0": 1,
    "tool1": 2,}

SpeedDict = {
    "speed0": 1,
    "speed1": 2,}

StateSequence_MM = {
    "Home": 1,
    "Standby": 2,
}

StateSequence_CB = {
    "Home": 1,
    "Standby": 2,
}

object_group_1: Set[str] = {"object1", "object2", "object3"}
object_group_2: Set[str] = {"object4", "object5", "object6"}
object_group_3: Set[str] = {"object7", "object8", "object9"}

def lookup_tool_mm(selected_path: str) -> str:
    """Lookup the tool for multimove based on the selected path"""
    match selected_path:
        case "1A" | "1B":
            return "tool0"
        case "2A" | "2B":
            return "tool1"
        case _:
            raise ValueError(f"Invalid path: {selected_path}")
        
def lookup_tool_cb(selected_path: str) -> str:
    """Lookup the tool for cobot based on the selected path"""
    match selected_path:
        case "1A" | "1B":
            return "tool0"
        case "2A" | "2B":
            return "tool1"
        case _:
            raise ValueError(f"Invalid path: {selected_path}")
        
        
