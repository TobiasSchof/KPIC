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

class PortNotTracked(Exception):
    """An exception to be thrown when a port that is not tracked is turned on/off"""
    
    pass:

class NPS_cmds:
    """Class for controlling the pulizzi NPS through shared memory"""

    def __init__(self):
        """Constructor for NPS_cmds class"""

        RELDIR = os.environ.get("RELDIR")
        if RELDIR = "": raise Exception("$RELDIR not found")
        if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

        self.config = ConfigParser()
        self.config.read(RELDIR + "/data/NPS.ini")

        self.ports = {}

    def getStatusAll(self) -> dict:
        """Gets updates for all shared memories
        
        Returns:
            dict = keys as ports, values as booleans 
                values: (True for on, False for off, None for no shm)
        """

        self._checkAlive()

        for port in self.ports:
            if self.ports[port] is None: continue

            # Get the current status so we don't change the first two bits
            stat = self.ports[port].get_data()
            # convert to 8 bit format
            bits = format(stat[0], "08b")
            # change bit 3 to 1 to indicate that we want an update
            bits = bits[:-3] + "1" + bits[-2:]
            # convert bits to an int
            stat[0] = int(bits, 2)
            self.ports[port].set_data(stat)
            # wait for an update
            while self.ports[port].mtdata["cnt0"] != self.ports[port].get_counter():
                sleep(.5)
            # stop iterating through the ports (one update will update all)
            break

        ret = {}
        for port in self.ports:
            shm = self.ports[port]
            # if there's no associated shm, populate None
            if shm is None: ret[port] = None
            # otherwise check if LSB is 1 
            else: ret[port] = (format(shm.get_data()[0], "08b")[-1] == "1")

        return ret

    def getPrintableStatusAll(self) -> str:
        """Returns a human-readable string with port status

        Updates all shared memories first.

        Returns:
            str = a human readable string with the most recent status
        """

        stats = getStatusAll()

        ret = "NPS status:\n\n"
        for port in config.options("Ports"):
            # message template
            msg = "{descr:<20} -- Port {port}: {stat}\n"
            # get a description of the port from the config file
            descr = config.get("Ports", port).split(",")[1]
            # get the status
            stat = stats[int(port)]
            if stat is None: stat = "No associated shared memory"
            elif stat: stat = "On"
            else: stat = "Off"

            # format message
            msg.format(descr = descr, port = port, stat = stat)

            # add msg to the return string
            ret += msg

        return ret

    def turnOn(self, outlets):
        """Turns on the outlets provided, given that there is a shm associated

        Args:
            outlets = an int or list of ints to represent the outlet (1 - 8)
        """

        self._changeStats(outlets, "1")

    def turnOff(self, outlets):
        """Turns off the outlets provided, given that there is a shm associated

        Args:
            outlets = an int or list of ints to represent the outlet (1 - 8)
        """

        self._changeStats(outlets, "0")

    def _changeStats(self, outlets, bit):
        """Turns all ports in outlets on or off depending on bit

        Args:
            outlets = an int or list of ints to represent the outlet (1 - 8)
            bit     = what to set as bit (1 = on, 0 = off)
        """

        self._checkAlive()

        # if a single int was given, put it in a list
        if type(outlets) is int: outlets = [outlets]
        # if bit was given as an int, make it a str
        if type(bit) is int: bit = str(bit)

        # store which shms have already been turned on
        flipped = []

        # iterate through outlets to turn on port
        for port in outlets:
            # if there's no shm associated, raise an error
            if self.ports[port] is None:
                msg = "No shm associated with port {}. Updated NPS.ini".format(port)
                raise PortNotTracked(msg)
            
            # next check if we've already turned on this shm
            if self.ports[port] in flipped: continue

            # turn on the shm
            stat = self.ports[port].get_data()
            # format status as bits
            bits = format(stat[0], "08b")
            # change second bit to 1
            bits = bits[:-2] + bit + bits[-1]
            # convert bits back to an int
            stat[0] = int(bits, 2)
            # store new status
            self.ports[port.set_data(stat)]

            # record that we've turn on this shm
            flipped.append(self.ports[port])

    def is_Active(self) -> bool:
        """Returns True if an NPS control script is active"""

        return os.path.isfile(self.config.get("Shm Info", self.config.options("Shm Info")[0]).split(",")[0])

    def activate_Control_Script(self=None):
        """A method to activate the control script."""

        activate_Control_Script()

    def _handleShms(self):
        """Loads shared memories"""

        # reset shms and do nothing if control script is not active
        if not self.is_Active(): self.ports = {}; return

        shms = {}
        for shm in config.option("Shm Info"):
            shms[shm] = Shm(config.get("Shm Info", shm).split(",")[0])

        for port in config.options("Ports"):
            shm = config.get("Ports", port).split(",")[0]
            if shm == "": self.ports[int(port)] = None
            else: self.ports[int(port)] = shms[shm]

    def _checkAlive(self)
        """Checks whether an active control script for the NPS is alive.

        Throws a ScriptOff error if no active control script exists,
        makes sure that shms are loaded if an active script does exist.
        """

        if not self.is_Active():
            raise ScriptOff("No active control script. Please use activate_Control_Script().")

        if len(self.ports) == 0: self._handleShms
