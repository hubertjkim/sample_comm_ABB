"""Lookup table for the HMI configuration, including path, tool, speed, and state sequence mappings"""

import src.state_machines as client_state_machines
from .constants import lookup_tool_cb, lookup_tool_mm

def retrieve_motion_settings(temp_client_state, user_path_selection:str, user_sequence_selection:str = "Home"):
    """Retrieve the motion settings based on a given path and sequence selection.
    Args:
        temp_client_state: The current client state object
        user_path_selection: The path selected by the user, e.g., "1A", "1B", "2A", "2B"
        user_sequence_selection: The sequence selected by the user, e.g., "Home", "Standby"
    Returns:
        A tuple containing the path, tool, speed, and state number for both multimove and cobot control
    """
    match user_sequence_selection:
        case "Home":
            user_tool_selection_mm = lookup_tool_mm(user_path_selection)
            user_speed_selection_mm = "speed0"
            temp_client_state = client_state_machines.MM_Home(user_path_selection, user_tool_selection_mm, None, user_speed_selection_mm, None)

        case "Standby":
            user_tool_selection_mm = lookup_tool_mm(user_path_selection)
            user_speed_selection_mm = "speed1"
            temp_client_state = client_state_machines.MM_Standby(user_path_selection, user_tool_selection_mm, None, user_speed_selection_mm, None)

        case "Home_CB":
            user_tool_selection_cb = lookup_tool_cb(user_path_selection)
            user_speed_selection_cb = "speed0"
            temp_client_state = client_state_machines.CB_Home(user_path_selection, None, user_tool_selection_cb, None, user_speed_selection_cb) 

        case "Standby_CB":
            user_tool_selection_cb = lookup_tool_cb(user_path_selection)
            user_speed_selection_cb = "speed1"
            temp_client_state = client_state_machines.CB_Standby(user_path_selection, None, user_tool_selection_cb, None, user_speed_selection_cb)

        case _:
            raise ValueError(f"Invalid sequence selection: {user_sequence_selection}")
        
    return temp_client_state