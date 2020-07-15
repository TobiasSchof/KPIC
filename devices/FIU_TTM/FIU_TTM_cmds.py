#inherent python libraries
from configparser import ConfigParser
from time import sleep
from subprocess import Popen
import sys, os

#nfiuserver libraries
from KPIC_shmlib import Shm
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
        is_svo_on
        get_pos
        get_target
    Commands:
        on
        off
        set_svo
        set_pos
        center
        activate_Control_Script
    Internal methods:
        _checkAlive
        _checkOnAndAlive
        _handleShms
        _getData
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

        #If Stat_D isn't loaded, load shms
        if type(self.Stat_D) is str: self._handleShms()

        if type(self.Stat_D) is str or not (self.Stat_D.get_data()[0] & 1):
            return False
        else: return True

    def is_On(self) -> bool:
        """Checks whether device is on

        Returns:
            bool = True if device is on, False otherwise
        """

        self._checkAlive()

        return (self.Stat_D.get_data()[0] & 2)

    def get_error(self) -> int:
        """Returns the error currently stored in the shared memory.

        Returns:
            int = the error message. See FIU_TTM.ini for translation
        """

        self._checkOnAndAlive()

        return self.Error.get_data()[0]

    def is_svo_on(self) -> bool:
        """Returns on status of servos.

        Returns:
            bool = whether the servo is on (True) or off (False)
        """

        self._checkOnAndAlive()

        return self.Stat_D.get_data()[0] & 8

    def get_pos(self, time:bool=True, push:bool=True):
        """Returns the current position in the device's shared memory.

        Args:
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
            #this will throw an Attribute error if Stat_P is a string
            self.Stat_P.set_data(self.Stat_P.get_data())
        #otherwise, we just need Pos_D
        elif type(Pos_D) is str: 
            self._handleShms()
            # if Pos_D is still a string, the control script needs to be started
            if type(Pos_D) is str:
                raise ScriptOff("No Shm file. Please start control script.") 

        if time: return list(self.Pos_D.get_data()), self.Pos_D.get_time()
        else: return list(self.Pos_D.get_data())

    def get_target(self) -> list:
        """Returns the control script's current target

        Returns:
            list = indices: [axis 1, axis 2]. values: float - the position
        """

        self._checkOnAndAlive()

        #if shm isn't loaded, Pos_P won't have get_data attribute
        return list(self.Pos_P.get_data())

    def on(self, block:bool = False):
        """Turns the device on.
        
        Inputs:
            block = if True, blocks program until device is on
        """

        self._checkAlive()

        # change the device power bit to '1'
        stat = Stat_P.get_data()
        stat[0] = stat[0] | 2
        Stat_P.set_data(stat)

        if not block: return

        while not self.is_On(): sleep(.5)

    def off(self, block:bool = False):
        """Turns the device off.
        
        Args:
            block = if True, blocks program until device is off
        """

        self._checkAlive()

        # change the device power bit to '0'
        stat = Stat_P.get_data()
        stat[0] = stat[0] & ~2
        Stat_P.set_data(stat)

        if not block: return

        while not self.is_On(): sleep(.5)

    def set_svo(self, state:bool):
        """Sets servo values in the shared memory

        Args:
            state = if False, turns servos off, if True, turns them on
        """

        self._checkOnAndAlive()

        stat = Stat_P.get_data()

        # if state, change servo bit to '1'
        if state: stat[0] = stat[0] | 8
        # otherwise, change servo bit to '0'
        else: stat[0] = stat[0] & ~8

        Stat_P.set_data(stat)

    def set_pos(self, ax1:float, ax2:float) -> list:
        """Sets target position to [ax1, ax2]

        Throws errors if they any are posted by the control script
        Inputs:
            ax1 = the value for axis 1
            ax2 = the value for axis 2
        Returns:
            list = indices: [axis 1, axis 2]. values: the requested positions
        """

        self._checkOnAndAlive()

        pos = self.Pos_P.get_data()

        #it's easier to modify returns rather than format a numpy array
        pos[0] = ax1
        pos[1] = ax2

        self.Pos_P.set_data(pos)

        #for translation of error codes, see config file
        error = self.get_error()
        if error == 0: return list(pos)
        elif error == 1: raise MovementRange("Requested move outside limits.")
        elif error == 2: raise LoopOpen("Open loop movement not supported.") 
        elif error == 3: raise StageOff("Turn on device and try again.")
        
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
        for cmd in command:
            Popen(cmd.split(" "))
        
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