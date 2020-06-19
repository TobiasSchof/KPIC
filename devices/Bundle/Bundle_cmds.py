#inherent python libraries
from configparser import ConfigParser
from time import sleep
from subprocess import Popen
import sys, os

#nfiuserver libraries
from shmlib import Shm
#various exceptions, file can be found in $RELDIR/devices/support
from dev_Exceptions import *

RELDIR = os.environ.get("RELDIR")
if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

class FIU_TTM_cmds:
    """Class for controlling the tip tilt mirror via shared memory.
    
    method list:
    Queries:
        is_Active
        is_On
        get_error
        is_AS_on
        is_AB_on
        get_pos
        get_target
    Commands:
        on
        off
        set_AS
        set_AB
        home
        set_pos
        center
        activate_Control_Script
    Internal methods:
        _checkAlive
        _checkOnAndAlive
        _handleShms
        _getData
        _setStatus
    """
    
    def __init__(self):
        """Constructor for FIU_TTM_cmds"""
        
        #the config file has all the info needed to connect to shared memory
        config = ConfigParser()
        config.read(RELDIR+"/data/FIU_TTM.ini")

        #Stat_D will give us info on device and script status
        self.Stat_D = config.get("Shm_Info", "Stat_D").split(",")[0]
        self.Pos_D = config.get("Shm_Info", "Pos_D").split(",")[0]
        self.Error = config.get("Shm_Info", "Error").split(",")[0]
        self.Pos_P = config.get("Shm_Info", "Pos_P").split(",")[0]
        self.Stat_P = config.get("Shm_Info", "Stat_P").split(",")[0]
        self.Svos = config.get("Shm_Info", "Svos").split(",")[0]

        #NOTE: center is loaded here. If this changes, class will have to
        #   be reinitialized.
        self.mid_1=config.getfloat("TTM_Limits", "min_1") +\
            config.getfloat("TTM_Limits", "max_1")/2
        self.mid_2=config.getfloat("TTM_Limits", "min_2") +\
            config.getfloat("TTM_Limits", "max_2")/2

        #for examples on how to use semaphores, see FIU_TTM_draw or _Control 
        self._handleShms()

    def is_Active(self) -> bool:
        """Checks whether control script is active

        Returns:
            bool = True if control script is active, False otherwise
        """

        #if Stat_D isn't loaded, load it
        if type(self.Stat_D) is str: self._handleShms()

        try: stat = format(self.Stat_D.get_data[0], "08b")
        except:
            raise ShmError("No Stat_D shm. Please restart control script.")

        return stat[-1] == "1"

    def is_On(self) -> bool:
        """Checks whether device is on

        Returns:
            bool = True if device is on, False otherwise
        """

        #if Stat_D isn't loaded, load it
        if type(self.Stat_D) is str: self._handleShms()

        try: stat = format(self.Stat_D.get_data[0], "08b")
        except:
            raise ShmError("No Stat_D shm. Please restart control script.")

        return stat[-2] == "1"

    def get_error(self) -> int:
        """Returns the error currently stored in the shared memory.

        Returns:
            int = the error message. See FIU_TTM.ini for translation
        """

        self._checkAlive()
        if type(Error) is str: self._handleShms()

        # if self.Error is a string, this will throw an AttributeError
        try: return self.Error.get_data()[0]
        except AttributeError:
            raise ShmError("Shm states out of sync. Restart control script.")

    def is_AS_on(self) -> bool:
        """Checks whether Anti-Sticktion is on

        Returns:
            bool = True if AS is on, False otherwise
        """

        self._checkOnAndAlive()
        if type(Stat_D) is str: self._handleShms()
        
        try: stat = format(self.Stat_D.get_data()[0], "08b")
        except AttributeError:
            raise ShmError("Shm states out of sync. Restart control script.")

        return stat[-4] == "1"

    def is_AB_on(self) -> bool:
        """Checks whether Anti-Backlash is on

        Returns:
            bool = True if AB is on, False otherwise
        """
        
        self._checkOnAndAlive()
        if type(Stat_D) is str: self._handleShms()
        
        try: stat = format(self.Stat_D.get_data()[0], "08b")
        except AttributeError:
            raise ShmError("Shm states out of sync. Restart control script.")

        return stat[-3] == "1"
        
    def get_pos(self, time:bool=True, push:bool=True):
        """Returns the current position in the device's shared memory.

        Inputs:
            time = whether the time of the last update should be returned also.
            push = whether shared memory should be updated first (takes longer)
        Returns:
            if time == False: list, else: list, float

            list = indices: [axis 1, axis 2], values: float - the position
            float = the time in UNIX epoch time that the position was recorded
        """

        #if push is required, we need control script.
        if push:
            self._checkOnAndAlive()
            if type(Stat_P) is str: self._handleShms()

            #this will throw an Attribute error if Stat_P is a string
            try: self.Stat_P.set_data(self.Stat_P.get_data())
            except AttributeError:
                raise ShmError("Shm states out of sync. Restart control script.")

        # Check that Pos_D is set up correctly
        if type(Pos_D) is str: self._handleShms()

        #in case there's no file backing, self.Pos_D won't have get_data()
        try:
            if time: return list(self.Pos_D.get_data()), self.Pos_D.get_time()
            else: return list(self.Pos_D.get_data())
        except AttributeError:
            raise ShmError("Shm states out of sync. Restart control script.")

    def get_target(self) -> list:
        """Returns the control script's current target

        Returns:
            list = indices: [axis 1, axis 2]. values: float - the position
        """

        self._checkOnAndAlive()
        if type(self.Pos_P) is str: self._handleShms()

        #if shm isn't loaded, Pos_P won't have get_data attribute
        try: return list(self.Pos_P.get_data())
        except AttributeError:
            raise ShmError("Shm states out of sync. Restart control script.")

    def on(self, block:bool=False):
        """Turns the device on.
        
        Inputs:
            block = if True, blocks program until device is on
        """

        self._setStatus(1, True)

        if block:
            while not self.is_On(): sleep(1)

    def off(self):
        """Turns the device off."""

        self._setStatus(1, False)

    def set_AS(self, set_v:bool):
        """Turns Anti-Sticktion on or off

        Inputs:
            set_v = True to turn AS on, False to turn if off
        """
        
        self._setStatus(3, set_v)

    def set_AB(self, set_v:bool):
        """Turns Anti-Backlash on or off

        Inputs:
            set_v = True to turn AB on, False to turn if off
        """

        self._setStatus(2, set_v)

    def home(self):
        """Homes the device"""

        self._setStatus(4, True)

    def set_pos(self, ax1:float, ax2:float, ax3:float) -> list:
        """Sets target position to [ax1, ax2]

        Throws errors if they any are posted by the control script
        Inputs:
            ax1 = the value for the x axis 
            ax2 = the value for the y axis
            ax2 = the value for the f axis
        Returns:
            list = indices: [x, y, f]. values: the requested positions
        """

        self._checkOnAndAlive()
        if type(self.Pos_P) is str: self._handleShms()

        try: pos = self.Pos_P.get_data()
        except AttributeError:
            raise ShmError("Shm states out of sync. Restart control script.")

        #it's easier to modify returns rather than format a numpy array
        pos[0] = ax1
        pos[1] = ax2
        pos[2] = ax3

        self.Pos_P.set_data(pos)

        #for translation of error codes, see config file
        error = self.get_error()
        if error == 0: return list(pos)
        elif error == 20: raise MovementRange("Requested move outside limits.")
        elif error == 3: raise HomingError("Device is not homed.") 
        
    def center(self):
        """Moves the TTM to the center of its range"""
        
        self.set_pos(ax1=self.mid_1, ax2=self.mid_2)

    def activate_Control_Script(self):
        """Activates the control script if it's not already active."""

        if self.is_Active(): 
            msg = "Cannot have two control scripts running at once."
            raise ScriptAlreadActive(msg)

        config = ConfigParser()
        config.read("FIU_TTM.ini")

        #in config file, tmux creation command is separated from kpython3
        #   command via a '|' character so first split by that
        command = config.get("Environment", "start_command").split("|")
        #the tmux command should be split up by spaces
        Popen(command[0].split(" ")+[command[-1]])

    def _checkAlive(self):
        """Raises an exception if the control script is not active."""

        #is_Active will handle shm creation if they aren't already created
        if not self.is_Active():
            raise ScriptOff("Control script off. Please turn on.") 

        #if one of the P shms is a string, shms probably have to be loaded.
        if type(self.Pos_P) is str: self._handleShms()

    def _checkOnAndAlive(self):
        """Raises an exception if the control script or device is off.
        
        Additionally, load shared memories if they're not already loaded."""

        #first check if script is alive
        self._checkAlive()

        #then check if device is on
        if not self.is_On():
            raise StageOff("Stage is off. Please turn on.")
            
    def _handleShms(self):
        """Loads shms that need to be loaded, closes ones that need to be
        closed."""

        #if we haven't connected to Stat_D yet, self.Stat_D will be a string
        if type(self.Stat_D) is str:
            #the shm constructor throws an error if no data is provided, no
            #   semaphore is requested, and no file backing exists.
            try: self.Stat_D = Shm(self.Stat_D)
            except: return

        #the following two shms should exist if Stat_D does
        if type(self.Pos_D) is str:
            try: self.Pos_D = Shm(self.Pos_D)
            #if there's no file backing but the control script is alive, states
            #   somehow fell out of sync, so the system should be restarted
            except:
                msg = "Shm state out of sync. Please restart control script."
                raise ShmError(msg)

        if type(self.Error) is str:
            try: self.Error = Shm(self.Error)
            except: 
                msg = "Shm state out of sync. Please restart control script."
                raise ShmError(msg)

        #the following shared memories will only exist if control is active
        if self.is_Active():
            if type(self.Pos_P) is str:
                try: self.Pos_P = Shm(self.Pos_P)
                except: 
                    msg="Shm state out of sync. Please restart control script."
                    raise ShmError(msg)
            if type(self.Stat_P) is str:
                try: self.Stat_P = Shm(self.Stat_P)
                except: 
                    msg="Shm state out of sync. Please restart control script."
                    raise ShmError(msg)
        else:
            #if a P shm is alive, extract the file name and close it
            if not type(self.Pos_P) is str:
                name = self.Pos_P.fname
                self.Pos_P.close()
                self.Pos_P = name
            if not type(self.Stat_P) is str:
                name = self.Stat_P.fname
                self.Stat_P.close()
                self.Stat_P = name

    def _setStatus(self, bit:int, set_v:bool):
        """Tries to set bit <bit> to value <set_v>

        Inputs:
            bit   = which bit to set (0 = LSB)
            set_v = the value to set the bit to 
        """

        try:
            assert type(bit) is int
            assert bit in range(0, 8)
        except AssertionError:
            raise ValueError("Bit must be an int between 0 and 7")

        self._checkOnAndAlive()
        if type(self.Stat_P) is str: self._handleShms()

        try: stat = self.Stat_P.get_data()
        except AttributeError: 
            raise ShmError("Shm states out of sync. Restart control script.")

        val = format(stat, "08b")
        set_v = str(int(set_v))
        # if the desired bit doesn't reflect the desired state, change it
        if val[-1 - bit] != set_v:
            val[-1 - bit] = set_v
            stat[0] = int(val, 2)
            self.Stat_P.set_data(stat)

