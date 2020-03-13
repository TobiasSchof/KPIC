#!/usr/bin/env kpython3

#out of the box libraries
from configparser import ConfigParser
from subprocess import Popen as bash
from logging import info
from time import sleep
from functools import wraps
import sys, io

#installed libraries
import numpy as np

#location of command scripts
sys.path.insert(1, "/kroot/src/kss/nirspec/nsfiu/dev/lib")

from sce_shmlib import shm

sys.path.insert(1, "/tmp/TobiasTest")
from Exceptions import *

CONFIG_PATH = "/tmp/TobiasTest/"

class General_cmds():
    """Class for user control of a generic device via shared memory"""


    def __init__(self, name:str):
        """Constructor for python cmds library
        
        Inputs:
            name = the name of the device (e.g. TTM or TCP) 
        """

        self.config=ConfigParser()
        info("Reading config file")
        self.config.read(CONFIG_PATH+name+".ini")
        info("Config file read successfully.")

        #shm d is state shared memory.
        info("Connecting to state shared memory.")

        #shared memory creation is noisy so we silence it
        _ = io.StringIO()
        sys.stdout = _

        #shm data is a list so we populate a dictionary with which
        #information is at what index.
        self.str_d={}
        for name in self.config.options("Shm_D_Content"):
            self.str_d[name]=np.int(self.config.getfloat("Shm_D_Content", name))

        self.Shm_D=shm(self.config.get("Shm_path", "Shm_D"))

        #shm p is command shared memory
        info("Connecting to command shared memory.")

        self.str_p={}
        for name in self.config.options("Shm_P_Content"):
            self.str_p[name]=np.int(self.config.getfloat("Shm_P_Content", name))

        self.Shm_P=shm(self.config.get("Shm_path", "Shm_P"))

        sys.stdout = sys.__stdout__

        info("Connected to shared memories.")
        
        self._checkAlive()

    def set_status(self, status:int):
        """Sets the command shared memory status value"""

        self._checkAlive()

        info("Setting command memory status to {}.".format(status))

        data=self.Shm_P.get_data()
        data[self.str_p["status"]] = status
        self.Shm_P.set_data(data)

    def on(self):
        """Turns the TCP on via shared memory"""

        info("Requesting on status for device")

        self.set_status(1)

    def off(self):
        """Turns the TCP off via shared memory"""

        info("Requesting off status for device")

        self.set_status(0)

    def is_Active(self) -> bool:
        """Returns whether the control script is active or not"""

        info("Checking whether the device's control script is active.")

        try:
            return self.Shm_D.get_data()[self.str_d["status"]].item() in [1, 0]
        except AttributeError:
            info("No shared memory found. Try starting control script.")
            raise NoSharedMemory("No shared memory found. Try starting control script.")

    def is_On(self) -> bool:
        """Returns whether device is on or not (NPS status)."""

        info("Checking whether the device is on.")

        try:
            return self.Shm_D.get_data()[self.str_d["status"]].item() in [1, -1]
        except AttributeError:
            info("No shared memory found. Try starting control script.")
            raise NoSharedMemory("No shared memory found. Try starting control script.")


    def update(self):
        """Pushes an update to the state shared memory."""

        self._checkOnAndAlive()

        info("Pushing update to state shared memory.")
        self.Shm_P.set_data(self.Shm_P.get_data())

        info("Waiting for response")
        time=self.Shm_D.get_data()[self.str_d["cur_t"]].item()
        while time == self.Shm_D.get_data()[self.str_d["cur_t"]].item(): sleep(.01)

    def get_error(self) -> int:
        """Gets the current error from the state shared memory

        See config file for help with translating error.
        
        Outputs:
            int = the error message
        """

        info("Getting error message.")

        try:
            return self.Shm_D.get_data()[self.str_d["error"]].item()
        except AttributeError:
            info("No shared memory found. Try starting control script.")
            raise NoShareMemory("No shared memory found. Try starting control script.")

    def set_pos(self, pos:dict, block:bool=True):
        """Puts the given position in the command shared memory
        
        Inputs:
            pos = key is axis, value is position to move to
            block = whether to wait until movement finishes or an error is returned
        """

        self._checkOnAndAlive()

        info("Setting command shared memory position")

        data=self.Shm_P.get_data()
        for ax in pos:
            data[self.str_p["pos_{}".format(ax)]]=pos[ax]
        
        self.Shm_P.set_data(data)

        time=self.Shm_D.get_data()[self.str_d["cur_t"]]
        while time == self.Shm_D.get_data()[self.str_d["cur_t"]]: sleep(.01)

    def get_pos(self, push:bool=True, T:bool=False, nb_ite:int=1):
        """Returns the position in the device's state memory

        nb_ite > 1, and T == False will return a list of dicts
        nb_ite > 1, and T == True will return a list of lists ([[dict, float]]) 
        Inputs:
            push = whether shared memory should be updated first (takes longer)
            T = whether the time of the last update should be returned as well.
            nb_ite = the number of times that the position should be queried 
                    (can be used for stability analysis)
        Outputs:
            if nb_ite == 1, and T == False, dict
            if nb_ite == 1, and T == True,  dict, float
            if nb_ite > 1,  and T == False, [dict]
            if nb_ite > 1,  and T == True,  [[dict, float]]

            where the first dict is the position (keys = axis, values = pos)
                and the second, where applicable, is the time in epoch time
        """

        info("Getting current position.")

        ret=[]

        for _ in range(0, nb_ite):
            info("Doing request #{}".format(_+1))

            if push: self.update()

            try:
                data=self.Shm_D.get_data()
            except AttributeError:
                info("No shared memory found. Try starting control script.")
                raise NoSharedMemory("No shared memory found. Try starting control script.")

            pos={}
            for item in self.str_d:
                if item.find("pos") != -1: 
                    if len(item) == 3: pos["1"] = data[self.str_d[item]].item()
                    else: pos[item[4:]] = data[self.str_d[item]].item()

            if not T:
                ret.append(pos)
            else:
                ret.append([pos, data[self.str_d["cur_t"]].item()])

        if len(ret)==1:
            return ret[0]
        else:
            return ret

    def get_target(self) -> dict:
        """Returns the position that the device is being requested to move to

        Outputs:
            dict = keys are axes, values are target positions
        """

        self._checkOnAndAlive()

        info("Getting target position.")

        data=self.Shm_P.get_data()
        pos={}
        for item in str_p:
            if item.find("pos") != -1:
                if len(item) == 3: pos["1"] = data[str_p[item]].item()
                else: pos[item[4:]] = data[str_p[item]].item()

        return pos


    def is_svo_on(self) -> bool:
        """Returns the servo value in command shared memory.
        
        Outputs:
            bool = whether the servo is on
        """
        
        self._checkOnAndAlive()

        info("Getting servo value.")
        
        return self.Shm_P.get_data()[self.str_p["svos"]].item() == 1

    def set_svo(self, value:int=1):
        """Sets the servo status to the value given.

        Inputs:
            value = the value to set the servo to (True for on).
        """

        self._checkOnAndAlive()

        info("Setting servo value to {}.".format(value))

        dataP=self.Shm_P.get_data()
        dataP[self.str_p["svos"]] = value
        self.Shm_P.set_data(dataP)

    def _checkAlive(self):
        """Internal method to raise an error is the script is dead"""
         
        if not self.is_Active(): 
            info("Command was attempted when script was off.")
            raise ScriptOff("Use XXX enable")


    def _checkOnAndAlive(self):
        """Internal method to raise an error is the script is dead or device is off"""

        self._checkAlive()
        if not self.is_On():
            info("Command was attempted when device was off.")
            raise StageOff("Use XXX_cmds.on()")

    def getOldPos(name:str, T=False):
        """Static method to get the position when the script is off
        
        Inputs:
            name = the name of this device (the xyz in xyz.ini)
            T = whether to include the time in the output
        Outputs:
        if T = False:
            dict = keys are the axis as a string, values the position
        if T = True:
            dict, float = dict as above, the time (in epoch time)
        """

        info("Getting old position information")

        config=ConfigParser()
        config.read(CONFIG_PATH+name+".ini")

        #shm data is a list so we populate a dictionary with which
        #information is at what index.
        str_d={}
        for name in config.options("Shm_D_Content"):
            str_d[name]=np.int(config.getfloat("Shm_D_Content", name))

        try:
            _ = io.StringIO()
            sys.stdout = _
            data=shm(config.get("Shm_path", "Shm_D")).get_data()
            sys.stdout = sys.__stdout__
        except AttributeError:
            sys.stdout = sys.__stdout__
            info("No state shared memory")
            raise NoSharedMemory("No state shared memory, please activate control script.")

        ret = {}
        for item in str_d:
            if item.find("pos") != -1: 
                if len(item) == 3: ret["1"] = data[str_d[item]].item()
                else : ret[item[4:]] = data[str_d[item]].item()
                

        if T: return ret, data[str_d["cur_t"]].item()
        else: return ret
