# inherent python libraries
from configparser import ConfigParser
from subprocess import Popen
from time import sleep
import os

# nfiuserver libraries
from KPIC_shmlib import Shm
from dev_exceptions import *

def activate_Control_Script():
    """Activates the NPS control script"""

    RELDIR = os.environ.get("RELDIR")
    if RELDIR = "": raise Exception("$RELDIR not found")
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
        if RELDIR = "": raise Exception("$RELDIR not found")
        if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

        self.config = ConfigParser()
        self.config.read(RELDIR + "/data/NPS.ini")

        # populate with information on which device is on which port
        self.devices = {config.get("Ports", opt).split(",")[0]:int(opt) for opt in config.options("Ports")}
        # populate with information on which port has which device
        self.ports = {int(opt):config.get("Ports", opt).split(",") for opt in config.options("Ports")}

        # get file paths for shms
        self.Shm_P = config.get("Shm Info", "Shm_P").split(",")[0]
        self.Shm_D = config.get("Shm Info", "Shm_D").split(",")[0]

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

    def getStatusAll(self) -> dict:
        """Gets updates for all ports
        
        Returns:
            dict = keys as ports, values as booleans 
        """

        self._checkAlive()

        # get most recent Shm D counter
        Shm_D.get_counter()

        # touch Shm_P to request update 
        Shm_P.set_data(Shm_P.get_data())

        # wait for Shm D counter to increment
        while Shm_D.mtdata["cnt0"] == Shm_D.get_counter(): sleep(.5)

        # get updated status
        stat = Shm_D.get_data()

        # convert status to dictionary
        return {idx+1:val == "1" for idx, val in enumerate(format(stat, "08b"))}

    def getStatus(self, ports = None):
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
        if type(ports) is not list: ports = list(ports)

        # get status of all ports (NPS doesn't support individual port query)
        stat = self.getStatusAll()

        # extract the desired ports
        if len(ports) == 1: return stat[ports[0]]
        else: return {port:stat[port] for port in ports}

    def getPrintableStatusAll(self) -> str:
        """Returns a human-readable string with port status

        Updates all shared memories first.

        Returns:
            str = a human readable string with the most recent status
        """

        stats = getStatusAll()

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

            # format message
            msg.format(name = name, port = port, stat = stat)

            # add msg to the return string
            ret += msg

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
        if len(outlets) == 0: return

        # if a single int was given, put it in a list
        if type(outlets) is int: outlets = [outlets]
        # if bit was given as an int, make it a str
        if type(bit) is int: bit = str(bit)

        stat = Shm_P.get_data()
        stat_bits = format(stat, "08b")
        # set new status to bit if in outlets, otherwise to the value currently in Shm P
        new = ("{}"*8).format(*[bit if idx in outlets else stat_bits[idx] for idx in range(0,9)])
        stat[0] = int(new, 2)
        Shm_P.set_data(stat)

    def is_Active(self) -> bool:
        """Returns True if an NPS control script is active"""

        p_fname = Shm_P if type(Shm_P) is str else Shm_P.fname

        return os.path.isfile(p_fname)

    def activate_Control_Script(self=None):
        """A method to activate the control script."""

        activate_Control_Script()

    def _handleShms(self):
        """Loads shared memories"""

        # reset shms and do nothing if control script is not active
        if not self.is_Active(): 
            # get file paths for shms
            self.Shm_P = self.Shm_P.fname
            self.Shm_D = self.Shm_D.fname 
        else:
            self.Shm_P = Shm(self.Shm_P)
            self.Shm_D = Shm(self.Shm_D)

    def _checkAlive(self)
        """Checks whether an active control script for the NPS is alive.

        Throws a ScriptOff error if no active control script exists,
        makes sure that shms are loaded if an active script does exist.
        """

        if not self.is_Active():
            raise ScriptOff("No active control script. Please use activate_Control_Script().")

        if type(self.Shm_P) is str: self._handleShms()