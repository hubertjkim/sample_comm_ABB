from unicodedata import category
from ..Base import Base
from config.constants import PathDict, ToolDict_MM, ToolDict_CB, SpeedDict

class MM_Standby(Base):
    def __init__(self, path:str = "1A", tool_MM:str = "tool0", 
                    tool_CB:str = "tool0", speed_MM:str = "speed0", speed_CB:str = "speed0"):
        self.path = path
        super().__init__(path=path, tool_MM=tool_MM, tool_CB=tool_CB, speed_MM=speed_MM, speed_CB=speed_CB)

    def prep_data_MM(self, *args) -> None:
        path_int = PathDict[self._path]
        tool_int = ToolDict_MM[self._tool_MM]
        speed_int = SpeedDict[self._speed_MM]
        self._state_Setting = [path_int, tool_int, speed_int, int(args[0][0]+1)] # 2,3 qre the unique state numbers of two different standby state in multimove state machine


    # polymorphism: since I need to have two sub-steps for this steate 
    def grab_data_MM(self, *args) -> list[int]:
        self.prep_data_MM(args)
        return self._state_Setting
    
        