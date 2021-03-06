# inherent python libraries
from time import sleep
from configparser import ConfigParser
from subprocess import Popen, PIPE
import os

# nfiuserver libraries
from KPIC_shmlib import Shm
from dev_Exceptions import *

RELDIR = os.environ.get("RELDIR")
if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

class Mode_Change_cmds:
    """Class for controlling the light source translator via shared memory

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
        reset
        set_pos
        activate_control_script
        load_presets
    Internal methods:
        _checkAlive
        _checkConnectedAndAlive
        _handleShms
    """

    def __init__(self):
        """Constructor for Mode_Change_cmds"""

        # the config file has all the info needed to connect to shared memory
        config = ConfigParser()
        config.read(RELDIR+"/data/Mode_Change.ini")

        # get paths to shms
        self.Stat_D = config.get("Shm Info", "Stat_D").split(",")[0]
        self.Pos_D = config.get("Shm Info", "Pos_D").split(",")[0] 
        self.Stat_P = config.get("Shm Info", "Stat_P").split(",")[0] 
        self.Pos_P = config.get("Shm Info", "Pos_P").split(",")[0] 
        self.Error = config.get("Shm Info", "Error").split(",")[0]

        self.presets = {}
        # load preset positions.
        self.load_presets()

        # load info for tmux session
        self.tmux_ses  = config.get("Environment", "session")
        self.tmux_win  = config.get("Environment", "window")
        self.tmux_ctrl = config.get("Environment", "ctrl_s")

        self._handleShms()

    def is_active(self) -> bool:
        """Returns true if control script is active

        Returns:
            bool = whether the Mode_Change control script is active
        """

        if type(self.Stat_D) is str: self._handleShms()

        # check if first Stat_D bit is 1
        try: return self.Stat_D.get_data()[0] & 1
        # if Stat_D is a still a string, it means there is not shm file
        except AttributeError: return False

    def is_connected(self) -> bool:
        """Returns true if device is active

        Returns:
            bool = whether the Mode_Change is active
        """

        self._checkAlive()

        return self.Stat_D.get_data()[0] & 2

    def is_homed(self) -> bool:
        """Returns true if device is homed

        Returns:
            bool = whether the Mode_Change is in a referenced state
        """

        self._checkConnectedAndAlive()

        return self.Stat_D.get_data()[0] & 4

    def get_error(self) -> str:
        """Returns the error stored in shared memory

        If the error is negative, indicating a Conex error, the letter error code will be returned.

        Returns:
            str = the error (Letter if a conex code, number otherwise)
        """

        self._checkAlive()

        err = self.Error.get_data()[0]

        if err < 0: return chr(-1*err + 64)
        else: return err

    def get_pos(self, update:bool=True, time:bool=False) -> float:
        """Return the current position of the Mode_Change

        Args:
            update = whether an update to the position should be requested
            time   = whether the time the shm was last updated should be included
        Returns:
            float = the position
            or
            (float, float) = (the position, the time) if time == True
        """

        if update: 
            # if we want to update, device has to be on
            self._checkConnectedAndAlive()

            # update position counter
            d_cnt = self.Pos_D.get_counter()
            # touch Stat_P so that D shms get updated
            self.Stat_P.set_data(self.Stat_D.get_data())
            # wait until Pos_D is updated
            while d_cnt == self.Pos_D.get_counter(): sleep(1)
        # otherwise we just need to check if the control script is alive
        else: self._checkAlive()

        if time: return self.Pos_D.get_data()[0], self.Pos_D.get_time()
        else: return self.Pos_D.get_data()[0]

    def get_named_pos(self, update=False, time=False):
        """Returns the named position of the stage, or 'custom'

        Args:
            update = if True, will request update from control script
            time = if True, will return the time of the last update
        Returns:
            str = one of 'pupil', 'focal', 'zernike', or 'custom'
                (if time = False)
            or
            str, float = the position as above, the (unix epoch) time
                of last update (if time = True)
        """

        pos, a_time = self.get_pos(update = update, time = True)

        if abs(pos - self.presets["pupil"]) < .1:
            if time: return "pupil", a_time
            else: return "pupil"
        elif abs(pos - self.presets["focal"]) < .1:
            if time: return "focal", a_time
            else: return "focal"
        else:
            if time: return "custom", a_time
            else: return "custom"

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
        # If Stat_D reflects that the device is connected, do nothing
        if stat[0] & 2: return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] += 2
            self.Stat_P.set_data(stat)

    def disconnect(self):
        """Disconnects from the device"""

        self._checkAlive()

        stat = self.Stat_D.get_data()
        # If Stat_D reflects that the device is not connected, do nothing
        if not stat[0] & 2: return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] -= 2
            self.Stat_P.set_data(stat)

    def home(self):
        """Homes the Mode_Change"""

        self._checkConnectedAndAlive()

        stat = self.Stat_D.get_data()
        # If Stat_D reflects that the device is on, do nothing
        if stat[0] & 4: return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] += 4
            self.Stat_P.set_data(stat)

    def reset(self):
        """Resets the device (puts it into an unreferenced state)"""

        self._checkConnectedAndAlive()

        stat = self.Stat_D.get_data()
        # If Stat_D reflects that the device is on, do nothing
        if not stat[0] & 4: return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] -= 4
            self.Stat_P.set_data(stat)

    def set_pos(self, target, block:bool=False):
        """Sets a new target position

        Args:
            target = float: the position for the Mode_Change to move to
                    or
                     str:   the name of the preset position to move to
            block  = whether program execution should be blocked until Pos_D is updated
        """

        self._checkConnectedAndAlive()

        if not self.is_homed(): raise LoopOpen("Please home device.")

        preset = False
        # if a preset was given, translate it to a position
        if type(target) is str:
            try: 
                target = self.presets[target]
                preset = True
            except KeyError: msg = target; raise MissingPreset(msg)

        # get current counter for Pos_D so we know when it updates
        d_cnt = self.Pos_D.get_counter()

        # take Pos_P so that we don't need to remake the numpy array
        pos = self.Pos_P.get_data()
        pos[0] = target
        self.Pos_P.set_data(pos)

        # if we don't block, return
        if not block: return

        # if we are blocking, wait until Pos_D is updated
        while d_cnt == self.Pos_D.get_counter(): sleep(2)

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
            raise ScriptAlreadyActive("Visualizer Processing script already active.")

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
        config.read(RELDIR+"/data/Mode_Change.ini")

        for name in config.options("Presets"):
            self.presets[name.lower()] = config.getfloat("Presets", name)

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
        if not self.is_connected():
            raise StageOff("Stage is disconnected. Please use connect() method.")

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