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
sys.path.insert(1, "/kroot/src/kss/nirspec/nsfiu/lib")

from sce_shmlib import shm
from General_cmds import General_cmds
from Exceptions import *

class TCP_cmds(General_cmds):
    """Class for user control of the tracking camera pickoff
    
    from General_cmds imports the following:
    without change:
        on
        off
        is_Active
        is_On
        get_error
        is_svo_on
        set_svo
        _checkAlive
        _checkOnAndAlive
    with change:
        set_status
        update
        set_pos
        get_pos
        get_target
        getOldPos

    adds the following:
        is_ref
        ref
        slot    
    """

    def __init__(self):
        """Constructor for tacking camera pickoff python library"""
    
        super().__init__("TCP")
    
    def set_status(self, status:int):
        """Checks for valid input before calling super method"""

        assert status in [1, 0, -1, 2]

        super().set_status(status)

    def update(self):
        """Adds a check of whether the device is referenced or not"""

        super().update()

        info("Checking error message")
        if self.get_error() == 2:
            info("Unreferenced axis error")
            raise UnreferencedAxis("Must use TCP_cmds.ref(), position may be unreliable")
 
    def is_ref(self) -> bool:
        """Returns whether this device is referenced and can move."""

        super()._checkOnAndAlive()

        info("Checking reference status.")

        try:
            super().update()
            return True
        except UnreferencedAxis:
            return False

    def ref(self):
        """References the device."""

        super()._checkOnAndAlive()

        info("Referencing device.")

        self.set_status(2)

    def slot(self, slot):
        """Moves the TCP to one of the mirrors.

        Inputs:
            num = the slot to move to (1, 2, 3, or a name in the config file)
        """

        super()._checkOnAndAlive()

        info("Moving TCP to slot {}".format(slot))
        
        try: assert slot in [1, 2, 3]
        except AssertionError as error:
            for num in [1, 2, 3]:
                if self.config.get("Slots", "name{}".format(num)) == slot:
                    slot = num
                    break
            if not slot in [1, 2, 3]:
                raise ValueError("Invalid slot. See config file for options.") from error

        data=self.Shm_P.get_data()
        pos=self.config.getfloat("Slots", "pos{}".format(slot))
        data[self.str_p["pos"]]=pos
        self.Shm_P.set_data(data)

    def set_pos(self, pos:float, block:bool=True):
        """Modify's super's method for only one axis and to check errors"""

        super().set_pos()
        
        err=self.get_error()
        if err == 1:
            raise MovementRange("See config file for limits")
        elif err == 2:
            raise UnreferencedAxis("Must reference device with TCP_cmds.ref()")
        elif err == 3:
            raise MovementTimeout("Movement took too long. Check for blockages.")

    def get_pos(self, push:bool=True, T:bool=False, nb_ite:int=1):
        """Edit formatting of super's method for only one axis
        
        Outputs:
            instead of dict for positions, returns float
        """

        if nb_ite == 1:
            if not T: return super().get_pos(push, T, nb_ite)["1"]
            else:
                pos, time=super().get_pos(push, T, nb_ite)
                return pos["1"], time
                
        else:
            ret = super().get_pos(push, T, nb_ite)
            for idx, q in enumerate(ret):
                if not T: ret[idx] = q["1"]
                else: ret[idx]=[q[0]["1"], q[1]]
            return ret
        
    def get_target(self) -> float:
        """Edit formatting of super's method for only one axis

        Outputs:
            instead of dict for positions, returns float
        """

        return super().get_target()["1"]

    def getOldPos(T=False):
        """Edit formatting of super method
        
        Outputs:
            instead of dict for positions, returns float
        """
        
        if T:
            pos, time = super().getOldPos(T, "TCP")
        else:
            pos = super().getOldPos(T, "TCP")

        pos=pos["1"]

        if T:
            return pos, time
        else:
            return pos
