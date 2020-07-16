#inherent python libraries
from time import sleep
from configparser import ConfigParser
from subprocess import Popen
import os

#nfiuserver libraries
from KPIC_shmlib import Shm
from dev_Exceptions import *

RELDIR = os.environ.get("RELDIR")
if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

class FIU_TTM_cmds:
    """Class for controlling the tip tilt mirror via shared memory.
    
    method list:
    Queries:
        is_Active
        is_On
        is_loop_closed
        get_error
        get_pos
        get_target
    Commands:
        on
        off
        close_loop
        open_loop
        set_pos
        activate_Control_Script
        load_presets
    Internal methods:
        _checkAlive
        _checkOnAndAlive
        _handleShms
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

        self.presets = {}
        # load_presets()
        self.load_presets()

        self._handleShms()

    def is_Active(self) -> bool:
        """Checks whether control script is active

        Returns:
            bool = True if control script is active, False otherwise
        """

        #If Stat_D isn't loaded, load shms
        if type(self.Stat_D) is str: self._handleShms()

        if type(self.Stat_D) is str:
            return False
        else:
            return bool(self.Stat_D.get_data()[0] & 1)

    def is_On(self) -> bool:
        """Checks whether device is on

        Returns:
            bool = True if device is on, False otherwise
        """

        self._checkAlive()

        return bool(self.Stat_D.get_data()[0] & 2)

    def is_loop_closed(self) -> bool:
        """Returns on status of servos.

        Returns:
            bool = whether the servo is on (True) or off (False)
        """

        self._checkOnAndAlive()

        return bool(self.Stat_D.get_data()[0] & 8)

    def get_error(self) -> int:
        """Returns the error currently stored in the shared memory.

        Returns:
            int = the error message. See FIU_TTM.ini for translation
        """

        self._checkOnAndAlive()

        return self.Error.get_data()[0]

    def get_pos(self, update:bool=True, time:bool=False):
        """Returns the current position in the device's shared memory.

        Args:
            update = whether shared memory should be updated first (takes longer)
            time = whether the time of the last update should be returned also.
        Returns:
            list = [x pos, y pos]
            or
            (list, float) = ([x pos, y pos], time) if time == True
        """

        #if push is required, we need control script.
        if update:
            self._checkOnAndAlive()
            self.Pos_D.get_counter()
            # this will throw an Attribute error if Stat_P is a string
            self.Stat_P.set_data(self.Stat_P.get_data())
            # wait for TTM position to update
            while self.Pos_D.mtdata["cnt0"] == self.Pos_D.get_counter(): sleep(.5)
        #otherwise, we just need Pos_D
        elif type(self.Pos_D) is str: 
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
        stat = self.Stat_P.get_data()
        stat[0] = stat[0] | 2
        self.Stat_P.set_data(stat)

        if not block: return

        while not self.is_On(): sleep(.5)

    def off(self, block:bool = False):
        """Turns the device off.
        
        Args:
            block = if True, blocks program until device is off
        """

        self._checkAlive()

        # change the device power bit to '0'
        stat = self.Stat_P.get_data()
        stat[0] = stat[0] & ~2
        self.Stat_P.set_data(stat)

        if not block: return

        while not self.is_On(): sleep(.5)

    def open_loop(self):
        """Opens the loop"""

        self._checkOnAndAlive()

        stat = self.Stat_P.get_data()
        #change servo bit to '0'
        stat[0] = stat[0] & ~8
        self.Stat_P.set_data(stat)

    def close_loop(self):
        """Closes the loop"""

        self._checkOnAndAlive()

        stat = self.Stat_P.get_data()
        #change servo bit to '1'
        stat[0] = stat[0] | 8
        self.Stat_P.set_data(stat)

    def set_pos(self, target, block:bool=False) -> list:
        """Sets target position to [ax1, ax2]

        Throws errors if any are posted by the control script
        Args:
            target = a key of presets or a list of floats with an x and 
                    a y position.
            block  = if True, blocks until FIU_TTM is done moving
        Returns:
            list = indices: [axis 1, axis 2]. values: the requested positions
        """

        self._checkOnAndAlive()

        if type(target) is str:
            try: target = self.presets[target]
            except KeyError: raise MissingPreset(target)
        elif type(target) is list:
            if len(target) != 2:
                raise ValueError("List should have two elements, x and y.")
            for axis in target:
                if type(axis) is not float:
                    raise ValueError("list elements should be floats.")

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

        if not block: return

        while self.Stat_D.get_data()[0] & 4: sleep(.5)
        
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

    def load_presets(self):
        """Loads the preset positions from the config file

        Any presets from self.presets defined in the config file will be overwritten
        """

        config = ConfigParser()
        config.read(RELDIR + "/data/FIU_TTM.ini")

        for name in config.options("Presets"):
            pos = config.get("Presets", name).split(",")
            pos = [float(item.strip()) for item in pos]
            self.presets[name] = pos
        
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