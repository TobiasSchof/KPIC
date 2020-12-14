# inherent python libraries
from configparser import ConfigParser
from subprocess import Popen
from time import sleep
import os

# nfiuserver libraries
from KPIC_shmlib import Shm
from dev_Exceptions import *

def activate_Control_Script():
    """Activates the NPS control script"""

    RELDIR = os.environ.get("RELDIR")
    if RELDIR == "": raise Exception("$RELDIR not found")
    if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

    config = ConfigParser()
    config.read(RELDIR+"/data/NPS.ini")

    command = config.get("Environment", "start_command").split("|")
    for cmd in command: Popen(cmd.split(" "))

class NPS_cmds:
    """Class for controlling the pulizzi NPS through shared memory"""

    def __init__(self, follow = None):
        """Constructor for NPS_cmds class"""

        RELDIR = os.environ.get("RELDIR")
        if RELDIR == "": raise Exception("$RELDIR not found")
        if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

        self.config = ConfigParser()
        self.config.read(RELDIR + "/data/NPS.ini")

        # populate with information on which device is on which port
        self.devices = {self.config.get("Ports", opt).split(",")[0]:int(opt)\
                        for opt in self.config.options("Ports")}
        # populate with information on which port has which device
        self.ports = {int(opt):self.config.get("Ports", opt).split(",") for\
                      opt in self.config.options("Ports")}

        # get file paths for shms
        self.Shm_P = self.config.get("Shm Info", "P_Shm").split(",")[0]
        self.Shm_D = self.config.get("Shm Info", "D_Shm").split(",")[0]

        # a list that can be populated for getStatus(), on() and off()
        self.follow = []

        # populate follow list if something was provided
        try:
            if follow is not None:
                # format follow as a list if it's only one element
                if type(follow) is not list: follow = [follow]
                for elem in follow:
                    # if a port is given
                    if type(elem) is int or (type(elem) is str and elem.isdigit()):
                        elem = int(elem)
                        assert elem in range(1, 9) 
                        self.follow.append(elem)
                    elif type(elem) is str:
                        assert elem in self.devices.keys()
                        self.follow.append(self.devices[elem])
        # if follow is anything but an int from 1 to 8 or a key in self.devices, raise an error
        except AssertionError:
            msg = "Valid options to follow are ints or strings from 1 to 8 and " +\
                  ("{}, "*len(self.devices.keys())).format(*self.devices.keys())
            raise Exception(msg[:-2])

    def getStatusAll(self, update = True) -> dict:
        """Gets updates for all ports
        
        Returns:
            dict = keys as ports, values as booleans 
        """

        # if an update was requested, get an update
        if update:
            self._checkAlive()

            # get most recent Shm D counter
            self.Shm_D.get_counter()

            # touch Shm_P to request update 
            self.Shm_P.set_data(self.Shm_P.get_data())

            # wait for Shm D counter to increment
            while self.Shm_D.mtdata["cnt0"] == self.Shm_D.get_counter(): sleep(.5)
        # otherwise, make sure we're attached to shm
        else:
            # attach to shm if we haven't yet
            if type(self.Shm_D) is str:
                if os.path.isfile(self.Shm_D): self._handleShms()
                # if there is no file, raise an error
                else: raise ScriptOff("No shared memory. Please use activate_Control_Script().")

        # get status
        stat = self.Shm_D.get_data()[0]

        # convert status to dictionary
        return {8-idx:val == "1" for idx, val in enumerate(format(stat, "08b"))}

    def getStatus(self, ports = None, update = True):
        """Gets updates for the given ports

        Args:
            ports = a list of integer ports or a single integer port.
                    (if ports is None, self.follow is used)
        Returns:
            dict = keys as ports, values as booleans if more than one port is given
            bool = True for on, False for off, if only one port is given
        """

        # use self.follow if no ports are given
        if ports is None: ports = self.follow
        # convert ports to a list to iterate
        if type(ports) is not list: ports = [ports]

        # get status of all ports (NPS doesn't support individual port query)
        stat = self.getStatusAll(update)

        # extract the desired ports
        if len(ports) == 1: return stat[ports[0]]
        else: return {port:stat[port] for port in ports}

    def getPrintableStatusAll(self, update = True) -> str:
        """Returns a human-readable string with port status

        Updates all shared memories first.

        Returns:
            str = a human readable string with the most recent status
        """

        stats = self.getStatusAll(update)

        ret = "NPS status:\n\n"
        for port in self.ports:
            # message template
            msg = "{name:<20} -- Port {port}: {stat}\n"
            # get a description of the port from the config file
            name = self.ports[port][0]
            # get the status
            stat = stats[port]
            if stat: stat = "On"
            else: stat = "Off"

            # add formatted msg to the return string
            ret += msg.format(name = name, port = port, stat = stat)

        return ret

    def turnOn(self, outlets = None):
        """Turns on the outlets provided, given that there is a shm associated

        Args:
            outlets = an int or list of ints to represent the outlet (1 - 8)
                      (if outlets isn't provided, self.follow is used)
        """

        if outlets is None: outlets = self.follow

        self._changeStats(outlets, "1")

    def turnOff(self, outlets = None):
        """Turns off the outlets provided, given that there is a shm associated

        Args:
            outlets = an int or list of ints to represent the outlet (1 - 8)
                      (if outlets isn't provided, self.follow is used)
        """

        if outlets is None: outlets = self.follow

        self._changeStats(outlets, "0")

    def _changeStats(self, outlets, bit):
        """Turns all ports in outlets on or off depending on bit

        Args:
            outlets = an int or list of ints to represent the outlet (1 - 8)
            bit     = what to set as bit (1 = on, 0 = off)
        """

        self._checkAlive()

        # do nothing if no outlets are provided
        if type(outlets) is list and len(outlets) == 0: return

        # if a single int was given, put it in a list
        if type(outlets) is int: outlets = [outlets]
        # if bit was given as an int, make it a str
        if type(bit) is int: bit = str(bit)

        stat = self.Shm_P.get_data()
        stat_bits = format(stat[0], "08b")
        # set new status to bit if in outlets, otherwise to the value currently in Shm P
        new = ("{}"*8).format(*[bit if idx in outlets else stat_bits[8-idx] for idx in range(8, 0, -1)])
        stat[0] = int(new, 2)
        self.Shm_P.set_data(stat)

    def is_Active(self) -> bool:
        """Returns True if an NPS control script is active"""

        p_fname = self.Shm_P if type(self.Shm_P) is str else self.Shm_P.fname

        return os.path.isfile(p_fname)

    def activate_Control_Script(self=None):
        """A method to activate the control script."""

        activate_Control_Script()

    def _handleShms(self):
        """Loads shared memories"""

        # if Shm_P isn't connected but file exists, connect
        if type(self.Shm_P) is str:
            if os.path.isfile(self.Shm_P): self.Shm_P = Shm(self.Shm_P)
        # if Shm_P is connected but file doesn't exist, disconnect
        else:
            if not os.path.isfile(self.Shm_P.fname): self.Shm_P = self.Shm_P.fname
        # if Shm_D isn't connected but file exists, connect
        if type(self.Shm_D) is str:
            if os.path.isfile(self.Shm_D): self.Shm_D = Shm(self.Shm_D)
        # if Shm_D is connected but file doesn't exist, disconnect
        else:
            if not os.path.isfile(self.Shm_D.fname): self.Shm_D = self.Shm_D.fname

    def _checkAlive(self):
        """Checks whether an active control script for the NPS is alive.

        Throws a ScriptOff error if no active control script exists,
        makes sure that shms are loaded if an active script does exist.
        """

        if not self.is_Active():
            raise ScriptOff("No active control script. Please use activate_Control_Script().")

        if type(self.Shm_P) is str: self._handleShms()