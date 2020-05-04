#inherent python libraries
from configparser import ConfigParser
from subprocess import Popen
from time import sleep
import os

#installs
import numpy as np

#nfiuserver libraries
from shmlib import shm
from dev_Exceptions import *

RELDIR = os.environ.get("RELDIR")
if RELDIR[-1] == "/": RELDIR=RELDIR[:-1]

config = ConfigParser()
config.read(RELDIR+"/data/Mode_Change.ini")


Pos_D = shm(config.get("Shm_Info", "Pos_D").split(",")[0])
Error = shm(config.get("Shm_Info", "Error").split(",")[0])
Stat  = shm(config.get("Shm_Info", "Stat_D").split(",")[0])

def activate_Control_Script():
    """Activates the control script"""

    cmd = config.get("Environment", "start_command").split("|")

    Popen(cmd[0].split(" ")+cmd[1])

def zern(isBlocking:bool=False):
    """Changes to Zernike viewing mode
    
    Input:
        isBlocking = whether this method will block execution until move is
            complete
    """
    
    try: Pos_P = shm(config.get("Shm_Info", "Pos_P").split(",")[0])
    except: raise ScriptOff("Please start control script")

    Error = None
    cnt = None
    if isBlocking:
        Error = shm(config.get("Shm_Info", "Error").split(",")[0])
        cnt = Error.get_counter()

    Pos_P.set_data(np.array([-3], np.float16)

    if isBlocking:
        while cnt == Error.get_counter(): sleep(.5)

def focal(isBlocking:bool=False):
    """Changes to focal viewing mode
    
    Input:
        isBlocking = whether this method will block execution until move is
            complete
    """
    
    try: Pos_P = shm(config.get("Shm_Info", "Pos_P").split(",")[0])
    except: raise ScriptOff("Please start control script")

    Error = None
    cnt = None
    if isBlocking:
        Error = shm(config.get("Shm_Info", "Error").split(",")[0])
        cnt = Error.get_counter()

    Pos_P.set_data(np.array([-2], np.float16)

    if isBlocking:
        while cnt == Error.get_counter(): sleep(.5)

def pupil(isBlocking:bool=False):
    """Changes to pupil viewing mode
    
    Input:
        isBlocking = whether this method will block execution until move is
            complete
    """
    
    try: Pos_P = shm(config.get("Shm_Info", "Pos_P").split(",")[0])
    except: raise ScriptOff("Please start control script")

    Error = None
    cnt = None
    if isBlocking:
        Error = shm(config.get("Shm_Info", "Error").split(",")[0])
        cnt = Error.get_counter()

    Pos_P.set_data(np.array([-1], np.float16)

    if isBlocking:
        while cnt == Error.get_counter(): sleep(.5)

def set_pos(pos:float, isBlocking:bool=False):
    """Set the position of the Conex stage to the given position
    
    Blocks the program until movement is complete
    Input:
        pos = the position (in mm) to move to.
        isBlocking = whether this method will block execution until move is
            complete
    """
    
    try: assert type(pos) is float
    except AssertionError: raise ValueError("Position must be a float.")

    try: Pos_P = shm(config.get("Shm_Info", "Pos_P").split(",")[0])
    except: raise ScriptOff("Please start control script")

    Error = None
    cnt = None
    if isBlocking:
        Error = shm(config.get("Shm_Info", "Error").split(",")[0])
        cnt = Error.get_counter()

    Pos_P.set_data(np.array([pos], np.float16))

    if isBlocking:
        while cnt == Error.get_counter(): sleep(.5)

def get_pos(time:bool=False):
    """Returns the current position of the Conex stage in the shm

    Inputs:
        time = wehther or not to include the time in the output
    Outputs:
        float, float = the position and the time (if time is True)
    """

    try: Pos_D = shm(config.get("Shm_Info", "Pos_P").split(",")[0])
    except: raise ShmError("No Pos_D shm. Please restart control script.")

    if time: return Pos_D.get_data(), Pos_D.get_time()
    else: return Pos_D.get_data()
