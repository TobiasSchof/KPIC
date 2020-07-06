#!/usr/bin/env kpython3

# inherent python libraries
from configparser import ConfigParser
from atexit import register, unregister
from time import sleep
from signal import signal, SIGHUP, SIGTERM
from subprocess import Popen
from argparse import ArgumentParser
import sys, os, logging

# installs
from pipython import GCSDevice
from pipython.gcserror import gcserror
import numpy as np
from pos_ipc import Semaphore, O_CREX, ExistentialError

# nfiuserver libraries
from KPIC_shmlib import KPIC_shmlib
from NPS_cmds import NPS_cmds

"""
THIS IS A CONTROL SCRIPT FOR THE FIBER INJECTION UNIT'S TRACKING
CAMERA PICKOFF AND NOT FOR USE BY USER

see TCP_cmds or type TCP in terminal to control the stage
"""

devnm = ""

# This script is not an import
if __name__ != "__main__":
    print("TCP_Control is not meant to be used as an import.")
    sys.exit()

# info is most of what we'll be using from logging
info = logging.info

class NPSError(Exception):
    """An exception to be thrown if there is an error with the NPS"""
    pass

class AlreadAlive(Exception):
    """An exception to be thrown if control code is initialized twice."""
    pass

def move(target:float) -> int:
    """Moves device to target position

    Args:
        target = the position to move to
    Returns:
        int = error code
    """

    err = 0

    if not (dev.qSVO()["1"] and dev.qFRF()["1"]):
        info("Movement requested in open loop.")
        return 2

    if target < limits[0] or target > limits[1]:
        info("Movement {} requested outside limits {}.".format(target, limits))
        return 3

    try: dev.MOV({"1":target})
    except gcserror: err = 1

    return err

def do_stat() -> int:
    """Sends desired state to controller

    Returns:
        int = any error
    """

    req = format(Stat_P.get_data()[0], "08b")
    cur = format(Stat_D.get_data()[0], "08b")

    # kill script if requested
    if req[-1] == "0": signal_handler(0, 0); return

    starting = False
    # turn device on/off as requested
    if req[-2] == "1" and cur[-2] == "0":
        err = device_on()
        # if we can't move, update P shms
        if not CAN_MOVE:
            req[-3] = dev.qSVO()["1"] and dev.qFRF()["1"]
            Stat_P.set_data(np.array([int(req, 2)], Stat_P.npdtype))
            Pos_P.set_data(np.array([dev.qPOS()["1"]], Pos_P.npdtype))
            return err
        starting = True
    elif req[-2] == "0" and cur[-2] == "1": return device_off()

    # close the loop and home if requested
    if req[-3] == "1" and (cur[-3] == "0" or starting):
        try:
            if dev.qSVO()["1"]: dev.SVO({})