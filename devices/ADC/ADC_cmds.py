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

class ADC_cmds:
    """Class for controlling the ADC via shared memory

    method list:
    Queries:
        is_Active
        is_Connected
        is_Homed
        get_error
        get_pos
        get_target
        is_loop_closed
        is_loop_accurate
    Commands
        connect
        disconnect
        home
        loop_closed
        loop_accurate
        set_pos
        activate_Control_Script
        load_presets
    Internal methods:
        _checkAlive
        _checkOnAndAlive
        _handleShms
    """

    def __init__(self):
        """Constructor for ADC_cmds"""

        # the config file has all the info needed to connect to shared memory
        config = ConfigParser()
        config.read(RELDIR+"/data/ADC.ini")

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
            bool = whether the ADC control script is active
        """

        if type(self.Stat_D) is str: self._handleShms()

        # check if first Stat_D bit is 1
        try: return bool(self.Stat_D.get_data()[0] & 1)
        # if Stat_D is a still a string, it means there is not shm file
        except AttributeError: return False

    def is_Connected(self) -> bool:
        """Returns true if device is connected

        Checks Stat_D for on status

        Returns:
            bool = whether the ADC is on
        """

        self._checkAlive()

        return bool(self.Stat_D.get_data()[0] & 2)

    def is_Homed(self) -> bool:
        """Returns true if device is homed

        Returns:
            bool = whether the ADC is in a referenced state
        """

        self._checkOnAndAlive()

        return bool(self.Stat_D.get_data()[0] & 16)

    def get_error(self) -> str:
        """Returns the error stored in shared memory

        Returns:
            str = the error (Letter if a conex code, number otherwise)
        """

        self._checkAlive()

        return self.Error.get_data()[0]

    def get_pos(self, update:bool=True, time:bool=False) -> list:
        """Return the current position of the ADC

        Args:
            update = whether an update to the position should be requested
            time   = whether the time the shm was last updated should be included
        Returns:
            list = ADC position
            or
            (list, float) = (position, time) if time == True
        """

        if update: 
            # if we want to update, device has to be on
            self._checkOnAndAlive()

            # update position counter
            p_cnt = self.Pos_D.get_counter()
            # wait for no longer than 10 seconds
            cnt = 0
            # touch Stat_P so that D shms get updated
            self.Stat_P.set_data(self.Stat_D.get_data())
            # wait until Pos_D is updated
            while cnt < 10 and p_cnt == self.Pos_D.get_counter(): sleep(1); cnt+=1
        # otherwise we just need to check if the control script is alive
        else: self._checkAlive()

        if time: return list(self.Pos_D.get_data()), self.Pos_D.get_time()
        else: return list(self.Pos_D.get_data())

    def get_target(self) -> float:
        """Returns the target position from the shm

        Returns:
            float = the target position
        """

        # getting target position doesn't make sense unless device is on
        self._checkOnAndAlive()

        return list(self.Pos_P.get_data())

    def is_loop_closed(self) -> bool:
        """Returns whether this stage is closed loop

        Returns:
            bool = True if loop is closed, False if loop is open
        """

        self._checkOnAndAlive()

        return self.Stat_D.get_data()[0] & 4

    def is_loop_accurate(self) -> bool:
        """Returns whether this stage is using an accurate loop method or a clean one

        Returns:
            bool = True if loop is accurate, False if loop is clean
        """

        self._checkOnAndAlive()

        return self.Stat_D.get_data()[0] & 8

    def connect(self):
        """Connects to device

        This is done by setting Stat_P, not through the NPS
        """

        self._checkAlive()

        stat = self.Stat_P.get_data()
        # If Stat_P reflects that the device is on, do nothing
        if stat[0] & 2: return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] += 2
            self.Stat_P.set_data(stat)

    def disconnect(self):
        """Disconnects from the device

        This is done by setting Stat_P, not through the NPS
        """

        self._checkAlive()

        stat = self.Stat_P.get_data()
        # If Stat_P reflects that the device is on, do nothing
        if not stat[0] & 2: return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] -= 2
            self.Stat_P.set_data(stat)

    def home(self):
        """Homes the device"""

        self._checkOnAndAlive()

        stat = self.Stat_P.get_data()
        # If Stat_P reflects that the device is on, do nothing
        if stat[0] & 16: return
        # Otherwise, flip the device bit in Stat_P
        else:
            stat[0] += 16
            self.Stat_P.set_data(stat)

    def loop_closed(self, closed:bool = True):
        """Opens/closes the loop on the device
        
        Args:
            closed = if True, closes loop, if False opens it
        """

        self._checkOnAndAlive()

        stat = self.Stat_D.get_data()
        if closed:
            # If Stat_D reflects that the device is closed loop, do nothing
            if stat[0] & 4: return
            # Otherwise, flip the device bit in Stat_P
            else:
                stat[0] += 4
                self.Stat_P.set_data(stat)
        else:
            # If Stat_D reflects that the device is open loop, do nothing
            if not stat[0] & 4: return
            # Otherwise, flip the device bit in Stat_P
            else:
                stat[0] -= 4
                self.Stat_P.set_data(stat)
            
    def loop_accurate(self, accurate:bool = True):
        """Puts the loop into clean/accurate mode
        
        Args:
            accurate = if True, puts loop into accurate mode, otherwise into clean mode
        """

        self._checkOnAndAlive()

        stat = self.Stat_D.get_data()
        if accurate:
            # If Stat_D reflects that the device is closed loop, do nothing
            if stat[0] & 8: return
            # Otherwise, flip the device bit in Stat_P
            else:
                stat[0] += 8
                self.Stat_P.set_data(stat)
        else:
            # If Stat_D reflects that the device is open loop, do nothing
            if not stat[0] & 8: return
            # Otherwise, flip the device bit in Stat_P
            else:
                stat[0] -= 8
                self.Stat_P.set_data(stat)

    def set_pos(self, target, block:bool=False):
        """Sets a new target position

        Args:
            target = list: the position for the device to move to
                    or
                     str:  the name of the preset position to move to
            block  = whether program execution should be blocked until Pos_D is updated
        """

        self._checkOnAndAlive()

        if not self.is_Homed(): raise UnreferencedAxis("Please home device.")
        if not self.is_loop_closed(): raise LoopOpen("Please close loop")

        if type(target) is list and type(target[0]) is str:
            if len(target) > 1: raise ValuError("Only one preset accepted")
            else: target = target[0]
        # if a preset was given, translate it to a position
        if type(target) is str:
            try: target = self.presets[target]
            except KeyError: msg = target; raise MissingPreset(msg)

        if type(target) is not list or len(target) != 2: 
            raise ValueError("Target should be a two element list")

        # if blocking, update counter on Pos_D
        if block:
            d_cnt = self.Pos_D.get_counter()

        # take Pos_P so that we don't need to remake the numpy array
        pos = self.Pos_P.get_data()
        pos[0] = target[0]
        pos[1] = target[1]
        self.Pos_P.set_data(pos)

        # if we don't block, return
        if not block: return

        # create a counter to wait no more than 10 seconds
        cnt = 0

        # if we are blocking, wait until Pos_D is updated
        while cnt < 20 and  d_cnt == self.Pos_D.get_counter(): sleep(.5); cnt += 1

        # check to see if we timed out
        if d_cnt == self.Pos_D.get_counter():
            raise MovementTimeout("Movement is taking too long. Check for blocks.")
        # raise an error if there is an error
        err = self.Error.get_data()[0]
        if err != 0: 
            msg = "Error {}.".format(err)
            raise ShmError(msg)

    def activate_Control_Script(self, append = None):
        """Activates the control script if it's not already active."""

        if self.is_Active(): 
            msg = "Cannot have two control scripts running at once."
            raise ScriptAlreadActive(msg)

        config = ConfigParser()
        config.read(RELDIR+"/data/ADC.ini")

        #in config file, tmux creation command is separated from kpython3
        #   command via a '|' character so first split by that
        command = config.get("Environment", "start_command").split("|")

        # add append to end of start command
        if not append is None:
            append = " " + append.strip()
            # the command to start the control script will be the last set of quotes
            idx = command[-1].rfind("\"")
            if idx == -1: raise Exception("Cannot find where to append")
            command[-1] = command[-1][:idx] + append + command[-1][idx:]

        #the tmux command should be split up by spaces
        for cmd in command: 
            to_send = []
            # parse anything inside quotes as one element
            tmp = cmd.split("\"")
            # odd indexes will be elements between quotes
            for idx, word in enumerate(tmp):
                if idx % 2 == 0:
                    to_send += word.split(" ")
                else:
                    to_send.append(word)

            Popen(to_send)
            # we add a slight sleep so that if there are no tmux sessions,
            #    the server has time to initialize
            sleep(.1)

    def load_presets(self):
        """Loads the preset positions from the config file

        Any presets from self.presets defined in the config file will be overwritten
        """

        config = ConfigParser()
        config.read(RELDIR+"/data/ADC.ini")

        for name in config.options("Presets"):
            self.presets[name] = [float(val) for val in config.get("Presets", name).split(",")]

    def _checkAlive(self):
        """Raises a ScriptOff error if the control script is not alive"""

        if not self.is_Active():
            raise ScriptOff("Control script off. Please use activate_Control_Script() method.")

        # if shms haven't been loaded, load them
        if type(self.Pos_P) is str: self._handleShms()

    def _checkOnAndAlive(self):
        """Raises a StageOff error if the device is off"""

        # first make sure control script is alive
        self._checkAlive()

        # then check if device is on
        if not self.is_Connected(): raise StageOff("Stage is off. Please use on() method.")

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