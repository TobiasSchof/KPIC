#inherent python libraries
from configparser import ConfigParser
from time import sleep
from subprocess import Popen
import sys, os

#nfiuserver libraries
from KPIC_shmlib import Shm
from dev_Exceptions import *

RELDIR = os.environ.get("RELDIR")
if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

class FEU_TTM_cmds:
    """Class for controlling the tip tilt mirror via shared memory.
    
    method list:
    Queries:
        is_Active
        is_Connected
        get_error
        get_pos
        get_target
    Commands:
        connect
        disconnect
        set_pos
        activate_Control_Script
        load_presets
    Internal methods:
        _checkAlive
        _checkOnAndAlive
        _handleShms
    """
    
    def __init__(self):
        """Constructor for FEU_TTM_cmds"""
        
        #the config file has all the info needed to connect to shared memory
        config = ConfigParser()
        config.read(RELDIR+"/data/FEU_TTM.ini")

        #Stat_D will give us info on device and script status
        self.Stat_D = config.get("Shm_Info", "Stat_D").split(",")[0]
        self.Pos_D = config.get("Shm_Info", "Pos_D").split(",")[0]
        self.Error = config.get("Shm_Info", "Error").split(",")[0]
        self.Pos_P = config.get("Shm_Info", "Pos_P").split(",")[0]
        self.Stat_P = config.get("Shm_Info", "Stat_P").split(",")[0]

        self.presets = []
        # load presets in
        self.load_presets()

        #for examples on how to use semaphores, see FEU_TTM_draw or _Control 
        self._handleShms()

    def is_Active(self) -> bool:
        """Checks whether control script is active

        Returns:
            bool = True if control script is active, False otherwise
        """

        #If Stat_D isn't loaded, load shms
        if type(self.Stat_D) is str: self._handleShms()

        if type(self.Stat_D) is str or self.Stat_D.get_data()[0] in [-1, -2]:
            return False
        else: return True

    def is_Connected(self) -> bool:
        """Checks whether device is connected

        Returns:
            bool = True if device is connected, False otherwise
        """

        self._checkAlive()

        if type(self.Stat_D) is str: 
            raise ShmError("No Stat_D shm. Please restart control script.")

        #otherwise return based on Stat_D
        return (self.Stat_D.get_data()[0] & 2)

    def get_error(self) -> int:
        """Returns the error currently stored in the shared memory.

        Returns:
            int = the error message. See FEU_TTM.ini for translation
            str = if there's a conex error, returns the letter errror (see
                  user manual for translation)
        """

        self._checkOnAndAlive()

        #if self.Error is a string, this will throw an AttributeError
        try: err = self.Error.get_data()[0]
        except AttributeError:
            raise ShmError("Shm states out of sync. Restart control script.")
        
        if err >= 0:
            return err
        else:
            return chr(-1*err+64)

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
            #this will throw an Attribute error if Stat_P is a string
            try: self.Stat_P.set_data(self.Stat_P.get_data())
            except AttributeError:
                raise ShmError("Shm states out of sync. Restart control script.")
        #otherwise, we just need Pos_D
        elif type(self.Pos_D) is str: self._handleShms()

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

        #if shm isn't loaded, Pos_P won't have get_data attribute
        try: return list(self.Pos_P.get_data())
        except AttributeError:
            raise ShmError("Shm states out of sync. Restart control script.")

    def connect(self):
        """Connects to the device."""

        self._checkAlive()

        stat = self.Stat_P.get_data()
        stat[0] = stat[0] | 2
        self.Stat_P.set_data(stat)

    def disconnect(self):
        """Disconnects from the device"""

        self._checkAlive()

        stat = self.Stat_P.get_data()
        stat[0] = stat[0] & ~2
        self.Stat_P.set_data(stat)

    def set_pos(self, target, block:bool = False):
        """Sets a new target position

        Args:
            target = float: the position for the device to move to
                    or
                     str:  the name of the preset position to move to
            block  = whether program execution should be blocked until Pos_D is updated
        """

        self._checkOnAndAlive()

        if not self.is_Homed(): raise LoopOpen("Please home device.")

        # get current counter for Pos_D so we know when it updates
        p_cnt = self.Pos_D.get_counter()
        # wait no more than 10 seconds
        cnt = 0


        # if a preset was given, translate it to a position
        if type(target) is str:
            try: target = self.presets[target]
            except KeyError: msg = target; raise MissingPreset(msg)

        # take Pos_P so that we don't need to remake the numpy array
        pos = self.Pos_P.get_data()
        pos[0] = target
        self.Pos_P.set_data(pos)

        # if we don't block, return
        if not block: return

        # if we are blocking, wait until Pos_D is updated
        while cnt < 20 and p_cnt == self.Pos_D.get_counter(): sleep(.5); cnt += 1

        if p_cnt == self.Pos_D.get_counter():
            raise MovementTimeout("Movement is taking too long. Check for blocks.")

        # for translation of error codes, see config file
        error = self.get_error()
        if error == 0: return list(pos)
        elif error == 1: raise MovementRange("Requested move outside limits.")
        elif error == 2: raise LoopOpen("Open loop movement not supported.") 
        elif error == 3: raise StageOff("Turn on device and try again.")
        
    def activate_Control_Script(self):
        """Activates the control script if it's not already active."""

        if self.is_Active(): 
            msg = "Cannot have two control scripts running at once."
            raise ScriptAlreadActive(msg)

        config = ConfigParser()
        config.read("FEU_TTM.ini")

        #in config file, tmux creation command is separated from kpython3
        #   command via a '|' character so first split by that
        command = config.get("Environment", "start_command").split("|")
        #the tmux command should be split up by spaces
        Popen(command[0].split(" ")+[command[-1]])

    def load_presets(self):
        """Loads the preset positions from the config file

        Any presets from self.presets defined in the config file will be overwritten
        """

        config = ConfigParser()
        config.read(RELDIR+"/data/FEU_TTM.ini")

        for name in config.options("Presets"):
            self.presets[name] = config.getfloat("Presets", name)

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
                raise ShmMissing(msg)

        if type(self.Error) is str:
            try: self.Error = Shm(self.Error)
            except: 
                msg = "Shm state out of sync. Please restart control script."
                raise ShmMissing(msg)

        #the following shared memories will only exist if control is active
        if self.is_Active():
            if type(self.Pos_P) is str:
                try: self.Pos_P = Shm(self.Pos_P)
                except: 
                    msg="Shm state out of sync. Please restart control script."
                    raise ShmMissing(msg)
            if type(self.Stat_P) is str:
                try: self.Stat_P = Shm(self.Stat_P)
                except: 
                    msg="Shm state out of sync. Please restart control script."
                    raise ShmMissing(msg)
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