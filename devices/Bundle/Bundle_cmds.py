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

class Bundle_cmds:
    """Class for controlling the tip tilt mirror via shared memory.
    
    method list:
    Queries:
        is_Active
        is_Connected
        is_Homed
        get_error
        is_AS_on
        is_AB_on
        get_pos
        get_target
    Commands:
        connect
        disconnect
        set_AS
        set_AB
        home
        set_pos
        activate_Control_Script
        load_presets
    Internal methods:
        _checkAlive
        _checkConnectedAndAlive
        _handleShms
    """
    
    def __init__(self):
        """Constructor for Bundle_cmds"""
        
        #the config file has all the info needed to connect to shared memory
        config = ConfigParser()
        config.read(RELDIR+"/data/Bundle.ini")

        #Stat_D will give us info on device and script status
        self.Stat_D = config.get("Shm_Info", "Stat_D").split(",")[0]
        self.Pos_D = config.get("Shm_Info", "Pos_D").split(",")[0]
        self.Error = config.get("Shm_Info", "Error").split(",")[0]
        self.Pos_P = config.get("Shm_Info", "Pos_P").split(",")[0]
        self.Stat_P = config.get("Shm_Info", "Stat_P").split(",")[0]

        self.presets = {}
        # load preset positions
        self.load_presets()

        #for examples on how to use semaphores, see Bundle_draw or _Control 
        self._handleShms()

    def is_Active(self) -> bool:
        """Checks whether control script is active

        Returns:
            bool = True if control script is active, False otherwise
        """

        #if Stat_D isn't loaded, load it
        if type(self.Stat_D) is str: self._handleShms()

        # check if first Stat_D bit is 1
        try: return bool(self.Stat_D.get_data()[0] & 1)
        except AttributeError: return False

    def is_Connected(self) -> bool:
        """Checks whether device is connected

        Returns:
            bool = True if device is connected, False otherwise
        """

        self._checkAlive()

        return bool(self.Stat_D.get_data()[0] & 1 << 1)

    def is_Homed(self) -> bool:
        """Returns true if device is homed

        Returns:
            bool = whether the device is in a referenced state
        """

        self._checkConnectedAndAlive()

        return bool(self.Stat_D.get_data()[0] & 1 << 4)

    def get_error(self) -> int:
        """Returns the error currently stored in the shared memory.

        Returns:
            int = the error message. See Bundle.ini for translation
        """

        self._checkAlive()

        return self.Error.get_data()[0]

    def is_AS_on(self) -> bool:
        """Checks whether Anti-Sticktion is on

        Returns:
            bool = True if AS is on, False otherwise
        """

        self._checkConnectedAndAlive()

        return bool(self.Stat_D.get_data()[0] & 1 << 3)

    def is_AB_on(self) -> bool:
        """Checks whether Anti-Backlash is on

        Returns:
            bool = True if AB is on, False otherwise
        """
        
        self._checkConnectedAndAlive()

        return bool(self.Stat_D.get_data()[0] & 1 << 2)
        
    def get_pos(self, update:bool=True, time:bool=False) -> list:
        """Return the current position of the device

        Args:
            update = whether an update to the position should be requested
            time   = whether the time the shm was last updated should be included
        Returns:
            list = position
            or
            (list, float) = (position, time) if time == True
        """

        if update: 
            # if we want to update, device has to be on
            self._checkConnectedAndAlive()

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

    def get_target(self) -> list:
        """Returns the control script's current target

        Returns:
            list = indices: [axis 1, axis 2]. values: float - the position
        """

        # getting target position doesn't make sense unless device is on
        self._checkConnectedAndAlive()

        return list(self.Pos_P.get_data())

    def connect(self, block:bool=False):
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

    def set_AS(self, set_v:bool):
        """Turns Anti-Sticktion on or off

        Inputs:
            set_v = True to turn AS on, False to turn if off
        """

        self._checkConnectedAndAlive()

        stat = self.Stat_D.get_data()
        if set_v and not stat & 1 << 3:
            stat[0] = stat[0] | 1 << 3
            self.Stat_P.set_data(stat)
        elif not set_v and stat & 1 << 3:
            stat[0] = stat[0] & ~(1 << 3)
            self.Stat_P.set_data(stat)

    def set_AB(self, set_v:bool):
        """Turns Anti-Backlash on or off

        Inputs:
            set_v = True to turn AB on, False to turn if off
        """

        self._checkConnectedAndAlive()

        stat = self.Stat_D.get_data()
        if set_v and not stat & 1 << 2:
            stat[0] = stat[0] | 1 << 2
            self.Stat_P.set_data(stat)
        elif not set_v and stat & 1 << 2:
            stat[0] = stat[0] & ~(1 << 2)
            self.Stat_P.set_data(stat)

    def home(self):
        """Homes the device"""

        self._checkConnectedAndAlive()

        stat = self.Stat_D.get_data()
        if not stat & 1 << 4:
            stat[0] = stat[0] | 1 << 4
            self.Stat_P.set_data(stat)

    def set_pos(self, target, block):
        """Sets target position to [ax1, ax2]

        Throws errors if they any are posted by the control script
        Inputs:
            target = list: the position for the device to move to
                    or
                     str:  the name of the preset position to move to
            block  = whether program execution should be blocked until Pos_D is updated
        """

        self._checkConnectedAndAlive()

        if not self.is_Homed(): raise UnreferencedAxis("Please home device.")

        if type(target) is list and type(target[0]) is str:
            if len(target) > 1: raise ValuError("Only one preset accepted")
            else: target = target[0]
        # if a preset was given, translate it to a position
        if type(target) is str:
            try: target = self.presets[target]
            except KeyError: msg = target; raise MissingPreset(msg)

        if type(target) is not list or len(target) != 3: 
            raise ValueError("Target should be a three element list")

        # if blocking, update counter on Pos_D
        if block:
            d_cnt = self.Pos_D.get_counter()

        # take Pos_P so that we don't need to remake the numpy array
        pos = self.Pos_P.get_data()
        pos[0] = target[0]
        pos[1] = target[1]
        pos[2] = target[2]
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
        config.read(RELDIR+"/data/Bundle.ini")

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
        config.read(RELDIR+"/data/Bundle.ini")

        for name in config.options("Presets"):
            self.presets[name] = [float(val) for val in config.get("Presets", name).split(",")]

    def _checkAlive(self):
        """Raises an exception if the control script is not active."""

        #is_Active will handle shm creation if they aren't already created
        if not self.is_Active():
            raise ScriptOff("Control script off. Please turn on.") 

        #if one of the P shms is a string, shms probably have to be loaded.
        if type(self.Pos_P) is str: self._handleShms()

    def _checkConnectedAndAlive(self):
        """Raises an exception if the control script or device is off.
        
        Additionally, load shared memories if they're not already loaded."""

        #first check if script is alive
        self._checkAlive()

        # then check if device is on
        if not self.is_Connected(): raise StageOff("Stage is off. Please use on() method.")
            
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