class Base:
    def __init__(self, **kwargs):
        self._path = kwargs["path"]
        self._tool_MM = kwargs["tool_MM"]
        self._tool_CB = kwargs["tool_CB"]
        self._speed_MM = kwargs["speed_MM"]
        self._speed_CB = kwargs["speed_CB"]
        self._state_Setting = []

    def grab_data_MM (self,*args) -> list[int]:
        self.prep_data_MM()
        return self._state_Setting
    
    def grab_data_CB (self,*args) -> list[int]:
        self.prep_data_CB()
        return self._state_Setting
    
    def print_current_state(self):
        print(f"Current State: {self._state_Setting}")

        