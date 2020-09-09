# inherent python libraries
from time import sleep
from configparser import ConfigParser
from subprocess import Popen
import os

# nfiuserver libraries
from KPIC_shmlib import Shm
from dev_Exceptions import *

RELDIR = os.environ.get("RELDIR")
if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

class Fiber_MP_cmds:
    """Class for controlling the Fiber multiport via shared memory

    method list:
    Queries:
        is_Active
        is_Connected
        is_Homed
        get_error
        get_pos
        get_target
    Commands
        connect
        disconnect
        home
        open_loop
        set_pos
        activate_Control_Script
        load_presets
    Internal methods:
        _checkAlive
        _checkConnectedAndAlive
        _handleShms
    """

    def __init__(self):
        """Constructor for Fiber_MP_cmds"""

        # the config file has all the info needed to connect to shared memory
        config = ConfigParser()
        config.read(RELDIR+"/data/Fiber_MP.ini")

        # get paths to shms
        self.Stat_D = config.get("Shm Info", "Stat_D").split(",")[0]
        self.Pos_D = config.get("Shm Info", "Pos_D").split(",")[0] 
        self.Stat_P = config.get("Shm Info", "Stat_P").split(",")[0] 
        self.Pos_P = config.get("Shm Info", "Pos_P").split(",")[0] 
        self.Error = config.get("Shm Info", "Error").split(",")[0]

        self.presets = {}
        # load preset positions.
        self.load_presets()

        self._handleShms()

    def is_Active(self) -> bool:
        """Returns true if control script is active

        Returns:
            bool = whether the Fiber_MP control script is active
        """

        if type(self.Stat_D) is str: self._handleShms()

        # check if first Stat_D bit is 1
        try: return bool(self.Stat_D.get_data()[0] & 1)
        # if Stat_D is a still a string, it means there is not shm file
        except AttributeError: return False

    def is_Connected(self) -> bool:
        """Returns true if device is connected

        Returns:
            bool = whether the Fiber_MP is connected
        """

        self._checkAlive()

        return bool(self.Stat_D.get_data()[0] & 2)

    def is_Homed(self) -> bool:
        """Returns true if device is homed

        Returns:
            bool = whether the Fiber_MP is in a referenced state
        """

        self._checkConnectedAndAlive()

        return bool(self.Stat_D.get_data()[0] & 4)

    def get_error(self) -> str:
        """Returns the error stored in shared memory

        Returns:
            str = the error (Letter if a conex code, number otherwise)
        """

        self._checkAlive()

        return self.Error.get_data()[0]

    def get_pos(self, update:bool=True, time:bool=False) -> float:
        """Return the current position of the Fiber_MP

        Args:
            update = whether an update to the position should be requested
            time   = whether the time the shm was last updated should be included
        Returns:
            float = Fiber_MP position
            or
            (float, float) = (position, time) if time == True
        """

        if update: 
            # if we want to update, device has to be on
            self._checkConnectedAndAlive()

            # update position counter
            p_cnt = self.Pos_D.get_counter()
            # touch Stat_P so that D shms get updated
            self.Stat_P.set_data(self.Stat_D.get_data())
            # wait until Pos_D is updated
            while p_cnt == self.Pos_D.get_counter(): sleep(1)
        # otherwise we just need to check if the control script is alive
        else: self._checkAlive()

        if time: return self.Pos_D.get_data()[0], self.Pos_D.get_time()
        else: return self.Pos_D.get_data()[0]

    def get_target(self) -> float:
        """Returns the target position from the shm

        Returns:
            float = the target position
        """

        # getting target position doesn't make sense unless device is on
        self._checkConnectedAndAlive()

        return self.Pos_P.get_data()[0]

    def connect(self):
        """Connects to the device"""

        self._checkAlive()

        stat = self.Stat_D.get_data()
        # If Stat_D reflects that the device is on, do nothing
        if stat[0] & 2: return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] = stat[0] | 2
            self.Stat_P.set_data(stat)

    def disconnect(self):
        """Disconnects from device"""

        self._checkAlive()

        stat = self.Stat_D.get_data()
        # If Stat_D reflects that the device is off, do nothing
        if not (stat[0] & 2): return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] = stat[0] & ~2
            self.Stat_P.set_data(stat)

    def home(self):
        """Homes the device"""

        self._checkConnectedAndAlive()

        stat = self.Stat_D.get_data()
        # If Stat_D reflects that the device is homed, do nothing
        if stat[0] & 4: return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] = stat[0] | 4
            self.Stat_P.set_data(stat)

    def open_loop(self):
        """Opens the loop on the device"""

        self._checkConnectedAndAlive()

        stat = self.Stat_D.get_data()
        # If Stat_D reflects that the device is in open loop, do nothing
        if not (stat[0] & 4): return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] = stat[0] & ~4
            self.Stat_P.set_data(stat)

    def set_pos(self, target, block:bool=False):
        """Sets a new target position

        Args:
            target = float: the position for the device to move to
                    or
                     str:  the name of the preset position to move to
            block  = whether program execution should be blocked until Pos_D is updated
        """

        self._checkConnectedAndAlive()

        if not self.is_Homed(): raise LoopOpen("Please home device.")

        # get current counter for Pos_D so we know when it updates
        p_cnt = self.Pos_D.get_counter()

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
        while and p_cnt == self.Pos_D.get_counter(): sleep(.5)

        # raise an error if there is an error
        err = self.Error.get_data()[0]
        if err < 0: 
            msg = "Error {}.".format(chr(-1*err + 64))
            raise ShmError(msg)
        elif err > 0: 
            msg = "Error {}.".format(err)
            raise ShmError(msg)

    def activate_Control_Script(self, append = None):
        """Activates the control script if it's not already active."""

        if self.is_Active(): 
            msg = "Cannot have two control scripts running at once."
            raise ScriptAlreadActive(msg)

        config = ConfigParser()
        config.read(RELDIR+"/data/Fiber_MP.ini")

        #in config file, tmux creation command is separated from kpython3
        #   command via a '|' character so first split by that
        command = config.get("Environment", "start_command").split("|")

        # add append to the end of the start command
        if not append is None:
            # the command to start the control script will be the last set of quotes
            idx = command.rfind("")
            if idx == -1: raise Exception("Cannot find where to append")
            command = command[:idx] + append + command[idx:]

        #the tmux command should be split up by spaces
        for cmd in command: Popen(cmd.split(" ")); sleep(.1)

    def load_presets(self):
        """Loads the preset positions from the config file

        Any presets from self.presets defined in the config file will be overwritten
        """

        config = ConfigParser()
        config.read(RELDIR+"/data/Fiber_MP.ini")

        for name in config.options("Presets"):
            self.presets[name] = config.getfloat("Presets", name)

    def _checkAlive(self):
        """Raises a ScriptOff error if the control script is not alive"""

        if not self.is_Active():
            raise ScriptOff("Control script off. Please use activate_Control_Script() method.")

        # if shms haven't been loaded, load them
        if type(self.Pos_P) is str: self._handleShms()

    def _checkConnectedAndAlive(self):
        """Raises a StageOff error if the device is off"""

        # first make sure control script is alive
        self._checkAlive()

        # then check if device is on
        if not self.is_On(): raise StageOff("Stage is off. Please use on() method.")

    def _handleShms(self):
        """Loads any shms that need to be loaded, closes any that need to be closed."""

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