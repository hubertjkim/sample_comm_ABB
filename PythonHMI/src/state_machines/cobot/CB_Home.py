from unicodedata import category
from ..Base import Base
from config.constants import PathDict, ToolDict_MM, ToolDict_CB, SpeedDict

class CB_Home(Base):
    def __init__(self, path:str = "1A", tool_MM:str = "tool0", 
                    tool_CB:str = "tool0", speed_MM:str = "speed0", speed_CB:str = "speed0"):
        print(f'Home state, default')
        super().__init__(path=path, tool_MM=tool_MM, tool_CB=tool_CB, speed_MM=speed_MM, speed_CB=speed_CB)

    def prep_data_CB(self) -> None:
        path_int = PathDict[self._path]
        tool_int = ToolDict_CB[self._tool_CB]
        speed_int = SpeedDict[self._speed_CB]
        self._state_Setting = [path_int, tool_int, speed_int, 1] # 1 is the unique state number of home state in cobot state machine