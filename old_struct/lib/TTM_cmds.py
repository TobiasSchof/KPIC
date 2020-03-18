#!/usr/bin/env kpython3

#out of the box libraries
from configparser import ConfigParser
from subprocess import Popen as bash
import sys

#installed libraries
import numpy as np

#location of command scripts
sys.path.insert(1, "/kroot/src/kss/nirspec/nsfiu/dev/lib")

from sce_shmlib import shm

sys.path.insert(1, "/tmp/TobiasTest")
from General_cmds import General_cmds
from Exceptions import *

class NoSharedMemory(Exception):
	pass

class TTM_cmds(General_cmds):
	"""Class for controlling the tip tilt mirror via shared memory.
    
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
        set_pos
        get_pos
        get_target
        getOldPos
        update
    with change:
        set_status
    """

	def __init__(self):
		"""Constructor for TTM_cmds"""

        super().__init__("TTM")
		
	def center(self):
		"""Moves the TTM to the center of its range"""

		info("Requesting TTM to move to center.")

		mid_1=float(self.config.get("TTM_Limits", "min_1")+self.config.get("TTM_Limits", "max_1"))/2
		mid_2=float(self.config.get("TTM_Limits", "min_2")+self.config.get("TTM_Limits", "max_2"))/2
		self.set_pos(axis_1=mid_1, axis_2=mid_2)

    def set_status(self, status:int):
        """Checks that status is valid."""

        assert status in [1, 0, -1]

        super().set_status(status)
