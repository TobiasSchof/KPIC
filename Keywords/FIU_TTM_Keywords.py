# nfiuserver libraries
import DFW
from FIU_TTM_cmds import FIU_TTM_cmds

TTM = FIU_TTM_cmds()

class FIU_TTM_POS_X_KTL(DFW.Keyword.Double):
    """A class to handle the FIU TTM X Position keyword"""
    
    def __init__(self, *args, **kwargs):
        """Constructor"""

        super().__init__(*args, **kwargs)

        # set initial value to -1
        # Keyword double array are doubles separated by white space
        kwargs['initial'] = '-1'
        # update keyword every .5 seconds
        kwargs['period'] = .5

        # if TTM control script is not active, activate it
        if not TTM.is_Active():
            TTM.activate_Control_Script()

    def update(self):
        """The method that is called on the given period"""

        # try to get the current position
        try:
            pos = TTM.get_pos()
            pos = "{}".format(pos[0])
        # if stage is off, just post -1, -1 (default value)
        except StageOff:
            pos = '-1'
        # if control script is off, try to start it and return
        except ScriptOff:
            TTM.activate_Control_Script()
            return

        # set keyword
        self.set(pos)

class FIU_TTM_STAT_KTL(DFW.Keyword.Mask):
    """A class to handle the FIU TTM Status keyword"""

    def __init__(self, *args, **kwargs):
        """Constructor"""

        # set initial value to 1
        kwargs['initial'] = '1'
        # update keyword every .5 seconds
        kwargs['period'] = .5

        # if TTM control script is not active, activate it
        if not TTM.is_Active():
            TTM.activate_Control_Script()

        super().__init__(*args, **kwargs)

    def update(self):
        """The method that is called on the given period"""

        # try to get the current status using shm
        try:
            # Keyword set method requires a string
            stat = str(TTM.Stat_D.get_data()[0])
        # if stage is off, post 1
        except StageOff:
            stat = '1'
        # if control script is off, post 0
        except ScriptOff:
            stat = '0'

        # set keyword
        self.set(stat)

class FIU_TTM_ERR_KTL(DFW.Keyword.Integer):
    """A class to handle the FIU TTM error keyword"""

    def __init__(self, *args, **kwargs):
        """Constructor"""

       # set initial value to 0
        kwargs['initial'] = '0'
        # update keyword every .5 seconds
        kwargs['period'] = .5

        # if TTM control script is not active, activate it
        if not TTM.is_Active():
            TTM.activate_Control_Script()

        super().__init__(*args, **kwargs) 

    def update(self):
        """The method that is called on the given period"""

        # try to get the current status using shm
        try:
            # Keyword set method requires a string
            stat = str(TTM.Stat_D.get_error()[0])
        # if control script is off, post 0
        except ScriptOff:
            stat = '0'

        # set keyword
        self.set(stat)