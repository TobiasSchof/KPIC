
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

class TCP_cmds:
    """Class for controlling the TCP via shared memory

    method list:
    Queries:
        is_active
        is_connected
        is_homed
        get_error
        get_pos
        get_target
    Commands
        connect
        disconnect
        home
        open_loop
        set_pos
        activate_control_script
        load_presets
    Internal methods:
        _checkAlive
        _checkConnectedAndAlive
        _handleShms
    """

    def __init__(self):
        """Constructor for TCP_cmds"""

        # the config file has all the info needed to connect to shared memory
        config = ConfigParser()
        config.read(RELDIR+"/data/TCP.ini")

        # get paths to shms
        self.Stat_D = config.get("Shm Info", "Stat_D").split(",")[0]
        self.Pos_D = config.get("Shm Info", "Pos_D").split(",")[0] 
        self.Stat_P = config.get("Shm Info", "Stat_P").split(",")[0] 
        self.Pos_P = config.get("Shm Info", "Pos_P").split(",")[0] 
        self.Error = config.get("Shm Info", "Error").split(",")[0]

        self.presets = {}
        # load preset positions.
        self.load_presets()

        # load tmux info
        self.tmux_ses  = config.get("Environment", "session")
        self.tmux_win  = config.get("Environment", "window")
        self.tmux_ctrl = config.get("Environment", "ctrl_s")

        self._handleShms()

    def is_active(self) -> bool:
        """Returns true if control script is active

        Returns:
            bool = whether the TCP control script is active
        """

        if type(self.Stat_D) is str: self._handleShms()

        # check if first Stat_D bit is 1
        try: return bool(self.Stat_D.get_data()[0] & 1)
        # if Stat_D is a still a string, it means there is not shm file
        except AttributeError: return False

    def is_connected(self) -> bool:
        """Returns true if device is connected

        Returns:
            bool = whether the TCP is connected
        """

        self._checkAlive()

        return bool(self.Stat_D.get_data()[0] & 2)

    def is_Homed(self) -> bool:
        """Returns true if device is homed

        Returns:
            bool = whether the TCP is in a referenced state
        """

        self._checkConnectedAndAlive()

        return bool(self.Stat_D.get_data()[0] & 4)

    def get_error(self) -> str:
        """Returns the error stored in shared memory

        If the error is negative, indicating a Conex error, the letter error code will be returned.

        Returns:
            str = the error (Letter if a conex code, number otherwise)
        """

        self._checkAlive()

        err = self.Error.get_data()[0]

        return err

    def get_pos(self, update:bool=True, time:bool=False) -> float:
        """Return the current position of the TCP

        Args:
            update = whether an update to the position should be requested
            time   = whether the time the shm was last updated should be included
        Returns:
            float = TCP position
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
        """Connects to device"""

        self._checkAlive()

        stat = self.Stat_D.get_data()
        # If Stat_D reflects that the device is connected, do nothing
        if stat[0] & 2: return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] += 2
            self.Stat_P.set_data(stat)

    def disconnect(self):
        """Disconnects from device"""

        self._checkAlive()

        stat = self.Stat_D.get_data()
        # If Stat_D reflects that the device is on, do nothing
        if not stat[0] & 2: return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] -= 2
            self.Stat_P.set_data(stat)

    def home(self):
        """Homes the device"""

        self._checkConnectedAndAlive()

        stat = self.Stat_D.get_data()
        # If Stat_D reflects that the device is homed, do nothing
        if stat[0] & 4: return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] += 4
            self.Stat_P.set_data(stat)

    def open_loop(self):
        """Opens the loop on the device"""

        self._checkConnectedAndAlive()

        stat = self.Stat_D.get_data()
        # If Stat_D reflects that the device is open loop, do nothing
        if not stat[0] & 4: return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] -= 4
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
        while p_cnt == self.Pos_D.get_counter(): sleep(.5)

        # raise an error if there is an error
        err = self.Error.get_data()[0]
        if err < 0: 
            msg = "Error {}.".format(chr(-1*err + 64))
            raise ShmError(msg)
        elif err > 0: 
            msg = "Error {}.".format(err)
            raise ShmError(msg)

    def activate_control_script(self, append=None):
        """Starts control script
        
        Args:
            append = any tags to be appended to the start command
        """

        if self.is_active():
            raise ScriptAlreadyActive("Control script already active.")

        # check if sessions already exists
        out = Popen(["tmux", "ls", "-F", "'#S'"], stdout=PIPE, stderr=PIPE).communicate()
        # if not, make it
        if str(out[0]).find("'{}'".format(self.tmux_ses)) == -1:
            out = Popen(["tmux", "new", "-d", "-s", self.tmux_ses, "-n", self.tmux_win],
                stdout=PIPE, stderr=PIPE).communicate()
            if out[1] != b'':
                msg = "TMUX error: {}".format(str(out[1]))
                raise TMUXError(msg)

        # check if window already exists
        out = Popen(["tmux", "lsw", "-t", self.tmux_ses, "-F", "'#W'"], stdout=PIPE,
            stderr=PIPE).communicate()
        # if not, make it
        if str(out[0]).find("'{}'".format(self.tmux_win)) == -1:
            out = Popen(["tmux", "new-window", "-t", self.tmux_ses, "-n", self.tmux_win],
                stdout=PIPE, stderr=PIPE).communicate()
            if out[1] != b'':
                msg = "TMUX error: {}".format(str(out[1]))
                raise TMUXError(msg)

        # add any flags to start command
        s_cmd = self.tmux_ctrl
        if not append is None:
            s_cmd = s_cmd.strip() + " " + append.strip()

        # Start Control script
        out = Popen(["tmux", "send-keys", "-t", "{}:{}".format(self.tmux_ses, self.tmux_win),
            "'{}'".format(self.tmux_ctrl), "Enter"], stdout=PIPE, stderr=PIPE).communicate()
        # check if there was an error
        if out[1] != b'':
            msg = "TMUX error: {}".format(str(out[1]))
            raise TMUXError(msg)

    def load_presets(self):
        """Loads the preset positions from the config file

        Any presets from self.presets defined in the config file will be overwritten
        """

        config = ConfigParser()
        config.read(RELDIR+"/data/TCP.ini")

        for name in config.options("Presets"):
            self.presets[name] = config.getfloat("Presets", name)

    def _checkAlive(self):
        """Raises a ScriptOff error if the control script is not alive"""

        if not self.is_active():
            raise ScriptOff("Control script off. Please use activate_control_script() method.")

        # if shms haven't been loaded, load them
        if type(self.Pos_P) is str: self._handleShms()

    def _checkConnectedAndAlive(self):
        """Raises a StageOff error if the device is off"""

        # first make sure control script is alive
        self._checkAlive()

        # then check if device is on
        if not self.is_connected(): raise StageOff("Stage is off. Please use connect() method.")

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
        if self.is_active():
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