# standard library
from subprocess import Popen
from configparser import ConfigParser
from time import sleep
import os

# nfiuserver libraries
from KPIC_shmlib import Shm
from dev_Exceptions import *

class NPS_cmds:
    """Class for controlling the Eaton NPS through shared memory
    
    method list:
    Queries:
        get_status
        is_active
    Commands:
        turn_on
        turn_off
        activate_control_script
    Internal methods:
        _change_stats
        _validate_ports
        _check_alive
        _handle_shms
    """

    def __init__(self):
        """Constructor for NPS_cmds class"""

        RELDIR = os.environ.get("RELDIR")
        if RELDIR == "": raise Exception("$RELDIR not found")
        if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

        self.config = ConfigParser()
        self.config.read(RELDIR + "/data/NPS.ini")

        # populate with information on which device is on which port
        self.devices = {self.config.get("Port Info", opt).split(",")[0]:int(opt)\
                        for opt in self.config.options("Port Info")}
        # populate with information on which port has which device
        self.ports = {int(opt):self.config.get("Port Info", opt).split(",")[0]\
                        for opt in self.config.options("Port Info")}

        # get file paths for shms
        self.Shm_P = self.config.get("Shm Info", "P_Shm").split(",")[0]
        self.Shm_D = self.config.get("Shm Info", "D_Shm").split(",")[0]

    def get_status(self, ports = "all", update = True):
        """Gets updates for the given ports

        Args:
            ports = a list of integer ports, a single integer port, or 'all'
            update = if True, requests an update of port status
        Returns:
            dict = keys as ports, values as True/False for on/off
        """

        # validate ports
        ports = self._validate_ports(ports)

        # get control script to update Shm D if update was passed
        if update:
            # check the control script is active
            self._check_alive()

            # set Shm P to Shm D to have control script update Shm D without changing
            #   any ports
            self.Shm_P.set_data(self.Shm_D.get_data())
            # wait for Shm D to be updated
            while self.Shm_D.mtdata["cnt0"] == self.Shm_D.get_counter(): sleep(.1)
        # otherwise, check that Shm D exists
        else:
            if type(self.Shm_D) is str: self._handle_shms()
            if type(self.Shm_D) is str:
                raise ShmError("No status. Please start NPS control script (try NPS.activate_Control_Script).")
        
        # get Shm D
        stat = self.Shm_D.get_data()
        # format data
        return {p:bool((1 << (p-1)) & stat) for p in range(1, 9)}

    def is_active(self):
        """Checks whether there is a Control script running

        NOTE: this is done by checking whether there is currently a P Shm file. If
            a control script was ended without being able to clean up, this may result
            in a ghost, where it looks like a script is active but none is. If this is
            the case, you can just delete the P Shm file.
        
        Returns:
            bool = True/False for script active/not active
        """

        p_fname = self.Shm_P if type(self.Shm_P) is str else self.Shm_P.fname

        return os.path.isfile(p_fname)

    def turn_on(self, ports):
        """Turns on the given ports

        Args:
            ports = an int, a list of ints, or 'all'
        Returns:
            None
        """

        # validate ports
        ports = self._validate_ports(ports)

        # turn on ports
        self._change_stats({p:True for p in ports})

    def turn_off(self, ports):
        """Turns off the given ports

        Args:
            ports = an int, a list of ints, or 'all'
        Returns:
            None
        """

        # validate ports
        ports = self._validate_ports(ports)

        # turn off ports
        self._change_stats({p:False for p in ports})

    def _change_stats(self, req:dict):
        """Sets P Shm bits to on/off depending on req

        Args:
            req = keys as ports, values as True/False for on/off 
        Returns:
            None
        """

        self._check_alive()

        # validate req
        if type(req) is not dict:
            raise ValueError("req should be a dictionary with keys as ports, values as bools.")
        else:
            if not all([p in self.ports for p in req.keys()]):
                raise ValueError("Valid ports are keys from self.port.")

        # start from current Shm D to avoid changing ports that haven't been requested
        stat = self.Shm_D.get_data()
        for p in req:
            if req[p]: stat[0] = stat[0] | 1 << (p - 1)
            else: stat[0] = stat[0] & ~(1 << (p - 1))

        # set new status
        self.Shm_P.set_data(stat)

    def _validate_ports(self, ports):
        """Checks that the given ports are valid and formats them.

        Valid ports are an int, a list of ints, or 'all' where ints are keys in self.ports

        Args:
            ports = the input to validate
        Returns:
            list = formatted list of ports if no error was thrown
        """

        # validate ports
        if type(ports) is list:
            if all([type(p) is int and p in self.ports for p in ports]):
                pass
            elif 'all' in ports:
                ports = list(self.ports.keys())
            else:
                try:
                    ports = [int(p) for p in ports]
                    assert all([p in self.ports for p in ports])
                except:
                    raise ValueError("List must be populated with ports from self.ports or contain 'all'.")
        elif type(ports) is int:
            ports = [ports]
        elif type(ports) is str:
            if ports == "all":
                ports = list(self.ports.keys())
            else:
                try: ports = [int(ports)]
                except:
                    raise ValueError("ports must be an int, 'all', or a list of ints.")
        else:
            raise ValueError("ports must be an int, 'all', or a list of ints.")

        return ports

    def _check_alive(self):
        if not self.is_active():
            raise ScriptOff("No active control script. Please use 'NPS.activate_control_scipt()'.")

        if type(self.Shm_P) is str or type(self.Shm_D) is str:
            self._handle_shms()
    
    def _handle_shms(self):
        """Tries to connect to shm files"""

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

    def activate_control_script(self=None):
        """Activates the NPS control script"""

        RELDIR = os.environ.get("RELDIR")
        if RELDIR == "": raise Exception("$RELDIR not found")
        if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

        config = ConfigParser()
        config.read(RELDIR+"/data/NPS.ini")

        # check to see if a control script is already running
        if os.path.isfile(config.get("Shm Info", "P_Shm").split(",")[0]):
            return

        command = config.get("Environment", "start_command").split("|")
        # provide a sleep time so tmux session has chance to start before 
        #   next command is sent
        for cmd in command: Popen(cmd.split(" ")); sleep(.1)