#inherent python libraries
from configparser import ConfigParser
from subprocess import Popen
from time import sleep
import os

#installs
import numpy as np

#nfiuserver libraries
from KPIC_shmlib import Shm
from dev_Exceptions import *

RELDIR = os.environ.get("RELDIR")
if RELDIR[-1] == "/": RELDIR=RELDIR[:-1]

class Mode_Change_cmds:
    """Class for controlling the linear conex stage that switches
        between viewing modes

    method list:
    Queries:
        is_active
        get_pos
        get_named_pos
    Commands:
        set_pos
        load_presets
        activate_control_script
    Internal methods:
        _checkAlive
        _handleShms
    """

    def __init__(self):
        """Constructor for Mode_Change_cmds"""

        config = ConfigParser()
        config.read(RELDIR+"/data/Mode_Change.ini")

        # load shm info
        self.Pos_D = Shm(config.get("Shm_Info", "Pos_D").split(",")[0])
        self.Error = Shm(config.get("Shm_Info", "Error").split(",")[0])
        self.Stat  = Shm(config.get("Shm_Info", "Stat_D").split(",")[0])

        # load info for tmux session
        self.tmux_ses  = config.get("Environment", "session")
        self.tmux_win  = config.get("Environment", "window")
        self.tmux_ctrl = config.get("Environment", "ctrl_s")

        # load preset positions
        self.presets = {}
        self.load_presets()

        self._handleShms()

    def is_active(self):
        """Checks whether a control script is active

        Returns:
            bool = True if control script is active, False otherwise
        """

        # If stat isn't loaded, load shms
        if type(self.Stat) is str: self._handleShms

        # if shm still isn't loaded, control script is off
        if type(self.Stat) is str: return False
        else: return bool(self.Stat.get_data()[0] & 1)

    def get_pos(self):
        """Returns the current position of the stage
        
        Returns:
            int = position of stage (negative for preset)
        """

        self._checkAlive()

        return self.Pos_D.get_data()[0]

    def get_named_pos(self):
        """Returns the named position of the stage, or 'custom'

        Returns:
            str = one of 'pupil', 'focal', 'zernike', or 'custom'
        """

        pos = self.get_pos()

        if abs(pos - self.presets["pupil"]) < .1:
            return "pupil"
        elif abs(pos - self.presets["focal"]) < .1:
            return "focal"
        elif abs(pos - self.presets["zernike"]) < .1:
            return "zernike"
        else:
            return "custom"

    def set_pos(self, pos):
        """Commands the stage to the given position

        Args:
            pos = a float for a custom position or one of the keys
                of self.presets
        """

        self._checkAlive()

        # validate input
        try: pos = float(pos)
        except:
            try: pos = self.presets[pos.lower()]
            except:
                raise ValueError("pos must be a float or defined preset.")

    def load_presets(self):
        """Loads the presets that are currently written into the config file"""

        config = ConfigParser()
        config.read(RELDIR+"/data/Mode_Change.ini")

        for name in config.options("Presets"):
            self.presets[name.lower()] = config.getfloat("Presets", name) 

    def activate_control_script(self):
        """Starts control script"""

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

        # Start Control script
        out = Popen(["tmux", "send-keys", "-t", "{}:{}".format(self.tmux_ses, self.tmux_win),
            "'{}'".format(self.tmux_ctrl), "Enter"], stdout=PIPE, stderr=PIPE).communicate()
        # check if there was an error
        if out[1] != b'':
            msg = "TMUX error: {}".format(str(out[1]))
            raise TMUXError(msg)

    def _check_alive(self):
        """A method to raise an error if the control script is not active"""

        if not self.is_active():
            raise ScriptOff("No active control script. Use activate_control_script().")

    def _handle_shms(self): 
        """A method to connect to shms where appropriate"""

        if type(self.Pos_D) is str:
            if os.path.isfile(self.Pos_D): self.Pos_D = Shm(self.Pos_D)
        elif not os.path.isfile(self.Pos_D.fname):
            self.Pos_D = self.Pos_D.fname
        if type(self.Error) is str:
            if os.path.isfile(self.Error): self.Error = Shm(self.Error)
        elif not os.path.isfile(self.Error.fname):
            self.Error = self.Error.fname
        if type(self.Stat) is str:
            if os.path.isfile(self.Stat): self.Stat = Shm(self.Stat)
        elif not os.path.isfile(self.Stat.fname):
            self.Stat = self.Stat.fname