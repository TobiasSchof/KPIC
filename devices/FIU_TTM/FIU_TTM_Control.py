#!/usr/bin/env kpython3

#inherent python libraries
from configparser import ConfigParser
from atexit import register, unregister
from time import time, ctime, sleep
from signal import signal, SIGHUP, SIGTERM
from subprocess import Popen
from argparse import ArgumentParser
import sys, os, threading, logging

#installs
from pipython import GCSDevice
from pipython.gcserror import GCSError
import numpy as np
import posix_ipc

#nfiuserver libraries
from KPIC_shmlib import Shm
from NPS_cmds import NPS_cmds

"""

THIS IS A CONTROL SCRIPT FOR THE FIBER INJECTION UNIT's TIP TILT MIRROR
AND NOT FOR USE BY USER

See FIU_TTM_cmds or type FIU_TTM in terminal to control the TTM 

"""

#This script is not an import
if __name__ != "__main__": 
    print("FIU_TTM_Control is not meant to be used as an import.")
    sys.exit()

# ip address for the PI device
IP = "10.136.1.45"

#a flag to tell the update thread to stop what it's doing
STOP = False
cur_thread = None

# a flag to tell this script when to end
alive = True

info=logging.info

class NPSError(Exception):
    """An exception to be thrown if there is an error with the NPS"""
    pass

class AlreadyAlive(Exception):
    """An exception to be thrown if control code is initialized twice"""
    pass

def update(error:int=0):
    """A method to be used in a thread that continuously checks the
    state of the TTM and updates the shm if necessary.
    """

    #continuously check device info
    while not STOP:
        try:
            with pi_lock: qMOV=pidev.IsMoving()
            stat = Stat_D.get_data()[0]
            #if we are moving update shm
            if qMOV["1"] or qMOV["2"]:
                with pi_lock: curpos=pidev.qPOS()
                cur_t = time()
                Pos_D.set_data(np.array([curpos["1"], curpos["2"]],\
                    Pos_D.npdtype), atime=cur_t)
    
                # if device is moving and Stat_D doesn't reflect this, change Stat_D
                if not (stat & 4):
                    Stat_D.set_data(np.array([stat | 4], Stat_D.npdtype), atime=cur_t)

            #otherwise, make sure status is set correctly
            else:
                with pi_lock: curpos=pidev.qPOS(); loop=pidev.qSVO()
                cur_t = time()

                # update status                
                stat = 3 | ((loop["1"] and loop["2"]) << 3)
                Stat_D.set_data(np.array([stat], Stat_D.npdtype), cur_t)

                # update position
                Pos_D.set_data(np.array([curpos["1"], curpos["2"]],\
                    Pos_D.npdtype), atime=cur_t)

                # update error
                Error.set_data(np.array([error], Error.npdtype), atime=cur_t)
                break
        #GCSError means that the TTM is not connected
        except GCSError:
            # update status
            Stat_D.set_data(np.array([1], Stat_D.npdtype))
            # update error
            Error.set_data(np.array([error], Error.npdtype))
            break

def move(target:list) -> int:
    """Tries to move TTM to target position.

    If target is outside of limits, returns an error message (but does not
    throw any errors).

    Inputs:
        target = a list with two floats. Index n is axis n+1.
    Outputs:
        int = the error message (check FIU_TTM.ini for translation)
    """

    with pi_lock:
        try: check = pidev.qSVO()
        except GCSError: info("Device off. Can't move."); return 3
        if not all([check[axis] for axis in axes]):
            info("Loop open")
            return 2

    #check whether target is valid before moving
    for idx in axes:
        req = target[int(idx)-1]
        if req < limits["min_"+idx] or req > limits["max_"+idx]:
            info("Movement requested outside of motion range")
            return 1

    #perform movement
    for idx in axes:
        req = target[int(idx)-1]
        info("Moving axis {} to {}.".format(idx, req))
        with pi_lock: pidev.MOV(idx, req)

    return 0

def connect_device():
    """Connects the TTM. If device is already connected, does nothing.
        
    Reloads limits from config file and, if CAN_MOVE==True, moves.
    """
    
    #Do nothing if device is off or already connected
    with pi_lock:
        if not nps.getStatus() or pidev.IsConnected(): return 

    info("Connecting TTM PI controller.")
    with pi_lock:
        while True:
            try:
                pidev.ConnectTCPIP(ipaddress=IP)
                info("FIU TTM Connected.")
                break
            except GCSError:
                info("Trouble connecting FIU TTM.")
                print("Connection to FIU TTM...")
                sleep(1)

    info("Extracting limits from config file.")
    global limits
    limits = {name:config.getfloat("TTM_Limits", name) for name in \
        config.options("TTM_Limits")}
    info("Config limits: {}".format(limits))

    info("Checking that config limits are within software limits.")
    #get software limits
    with pi_lock: softmin=pidev.qTMN()
    with pi_lock: softmax=pidev.qTMX()
    with pi_lock:
        for axis in axes:
            min_="min_{}".format(axis)
            max_="max_{}".format(axis)
            if limits[min_] < softmin[axis]:
                info("Changing {} limit to {}.".format(min_, softmin[axis]))
                limits[min_] = softmin[axis]
            if limits[max_] < softmax[axis]:
                info("Changing {} limit to {}.".format(max_, softmax[axis]))
                limits[max_] = softmax[axis]

    # update D shms
    update(0)

    info("Getting command shared memory")
    if CAN_MOVE:
        stat = Stat_P.get_data()[0]
        pos = Pos_P.get_data()

        info("Setting servos to initial values.")
        #load the starting servo values into a dict
        svo_set = {axis:bool(stat & 8) for axis in axes}
        with pi_lock: pidev.SVO(svo_set)
        info("Moving to initial positions.")
        #load the starting position values into a dict
        pos_i = {axis:pos[int(axis)-1] for axis in axes}
        with pi_lock: pidev.MOV(pos_i)
    else:
        info("Cannot move to initial positions. Changing command shared " +\
         "memory values.")
        # set P shms to current values
        Pos_P.set_data(Pos_D.get_data())
        Stat_P.set_data(Stat_D.get_data())

def device_off():
    """Turns off the TTM using the NPS"""

    # do nothing if nps port is already off
    if not nps.getStatus(): return

    info("Checking if TTM is connected.")
    with pi_lock:
        if pidev is not None and pidev.IsConnected():
            #Standard procedure for turning off TTM
            info("Turning off servos.")
            pidev.SVO({axis:0 for axis in axes})
            info("Zeroing voltage.")
            pidev.SVA({axis:0 for axis in axes})

            #update needs pi_lock so release it for now
            pi_lock.release()
            
            #update position
            #if there is an existing update thread, tell it to stop
            global cur_thread
            if cur_thread is not None and cur_thread.is_alive():
                cur_thread.join()
            else: update() #update shm

            pi_lock.acquire()
            
            info("Closing connection to TTM.")
            pidev.CloseConnection()

    info("Sending off command to NPS")
    nps.turnOff()

    info("Waiting for TTM to turn off.")
    while nps.getStatus(): sleep(.5)

    Stat_D.set_data(np.array([1], np.int8))

def device_on():
    """Waits for NPS to turn on device and then connects"""

    # if device is already on, do nothing
    if nps.getStatus(): return

    info("Sending on command to NPS")
    nps.tunrOn()

    info("Waiting for NPS to turn on device.")
    while not nps.getStatus(): sleep(.1)

    info("Opening connection to TTM.")
    connect_device()

def listener():
    """A method that performs commands from the command shared memory when 
    updated, and spawns a thread that updates the position of the TTM in shm.
    """

    # variable to store old status
    old_stat = Stat_P.get_data()[0]

    #we put the listening process in an infinite loop
    while alive:

        info("command shared memory updated")
        
        error=0
        
        # check status change first
        new_stat = Stat_P.get_data()[0]
        change = new_stat ^ old_stat
        # xor bit-wise to see if any bits have flipped
        if (change):
            info("status updated")
            # if script bit is off, close
            if not (new_stat & 1): signal_handler(None, None); break
            # check device bit 
            if change & new_stat & 2:
                info("Turning on device")
                device_on()
            elif change & ~new_stat & 2:
                info("Turning off device")
                device_off()
            # check open/close loop bit
            if change & new_stat & 8:
                with pi_lock: pidev.SVO({axis:True for axis in axes})
            elif change & ~new_stat & 8:
                with pi_lock: pidev.SVO({axis:False for axis in axes})
    
        #check position change last
        if Pos_P.mtdata["cnt0"] != Pos_P.get_counter():
            info("Position updated")
            error = move(Pos_P.get_data())
        
        #if there is an existing update thread, tell it to stop
        global cur_thread
        if cur_thread is not None and cur_thread.is_alive():
            global STOP
            STOP = True
            cur_thread.join()
            STOP = False
        #start a new update thread with the new error value
        cur_thread = threading.Thread(target=update, args=(error,), daemon=True)
        cur_thread.start()

        # wait for a new update
        ShmP.acquire()

def close():
    """A cleanup method.

    Closes all communication with the TTM, deletes command shared memory,
    and closes tmux session.
    """

    try:
        global STOP
        STOP = True
        if cur_thread is not None and cur_thread.is_alive():
            cur_thread.join()
    except Exception as ouch: info("Exception on close: {}".format(ouch))

    info("Killing draw process.")
    try: draw_proc.terminate()
    except Exception as ouch: info("Exception on close: {}".format(ouch))

    info("Deleting command shared memory file.")
    #We want to delete all command shared memories  so scripts can't 
    #mistakenly think the control script is alive.
    try:
        for shm in [Stat_P, Pos_P, Svos]:
            try: os.remove(shm.fname)
            except Exception as ouch: info("Exception on close: {}".format(ouch))
    except Exception as ouch: info("Exception on close: {}".format(ouch))

    info("Checking if TTM is connected.")
    try:    
        if pidev.IsConnected():
            info("Turning off TTM.")
            device_off()
    except Exception as ouch: info("Exception on close: {}".format(ouch))
    
    info("Updating state shared memory file.")
    try:
        #define how the status should change
        change = {2:-1, 1:-1, 0:-2, -1:-1, -2:-2}
        #set state status based on above change
        Stat_D.set_data(np.array([change[Stat_D.get_data()[0]]], np.int8))
    except Exception as ouch: info("Exception on close: {}".format(ouch))

    #killing semaphore listening processes.
    try:
        for proc in Sem_Listeners:
            try: proc.terminate()
            except Exception as ouch: info("Exception on close: {}".format(ouch))
    except Exception as ouch: info("Exception on close: {}".format(ouch))
    
    try: ShmP.unlink()
    except Exception as ouch: info("Exception on close: {}".format(ouch))
        
    info("Closing tmux session.")
    unregister(close)
    Popen(config.get("Environment", "end_command").split(" "))

def signal_handler(signum, stack):
    """A function to gracefully exit when a signal is encountered"""

    global alive = False
    try: ShmP.release()
    except: pass

RELDIR = os.environ.get("RELDIR")
if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

#read TTM config file
config = ConfigParser()
config.read(RELDIR+"/data/FIU_TTM.ini")

log_path=config.get("Communication", "debug_log")
debug_format = "%(filename)s.%(funcName)s@%(asctime)s - %(levelname)s: %(message)s"

parser = ArgumentParser()
#boolean flag for CAN_MOVE
parser.add_argument("-m", action="store_true")
#flags to put into debug mode
parser.add_argument("-d", default=-1, nargs="?")
parser.add_argument("-d!", "--dd", default=-1, nargs="?")

args = parser.parse_args()

CAN_MOVE = args.m #whether this device can move on startup

if args.dd != -1:
    if not args.dd is None: log_path=args.dd
    logging.basicConfig(format=debug_format, datefmt="%H:%M:%S",\
        filename=log_path)
    logging.root.setLevel(logging.DEBUG)
elif args.d != -1:
    if not args.d is None: log_path=args.d
    logging.basicConfig(format=debug_format, datefmt="%H:%M:%S", \
        filename=log_path)
    logging.root.setLevel(logging.INFO)

#make the folder for shared memories if it doesn't already exist
if not os.path.isdir("/tmp/FIU_TTM"): os.mkdir("/tmp/FIU_TTM")

#create a dictionary to translate strings into numpy data types
type_ = {"int8":np.int8, "int16":np.int16, "int32":np.int32, "int64":np.int64,
    "uint8":np.uint8, "uint16":np.uint16, "uint32":np.uint32,
    "uint64":np.uint64, "intp":np.intp, "uintp":np.uintp, "float16":np.float16,
    "float32":np.float32, "float64":np.float64, "complex64":np.complex64,
    "complex128":np.complex128}

#for now we just want to connect to shm to see if there's already a script
Stat_D = config.get("Shm_Info", "Stat_D").split(",")
if os.path.isfile(Stat_D[0]): 
    Stat_D = Shm(Stat_D[0])
    status=Stat_D.get_data()[0]

    if (status & 1):
        info("Active control script exists. Raising exception.")
        msg="State shared memory status {}.".format(status)
        raise AlreadyAlive(msg)
else:
    info("No state shared memory file. Creating file.")
    Stat_D = config.get("Shm_Info", "Stat_D").split(",")
    Stat_D = Shm(Stat_D[0], data=np.array([1], dtype=type_[Stat_D[1]]),
        mmap = (Stat_D[2] == "1"))


Pos_D = config.get("Shm_Info", "Pos_D").split(",")
if os.path.isfile(Pos_D[0]): Pos_D = Shm(Pos_D[0])
else:
    info("No state shared memory file. Creating file.")
    Pos_D = Shm(Pos_D[0], data=np.array([-5000., -5000.],
        dtype=type_[Pos_D[1]]), mmap = (Pos_D[2] == "1"))

Error = config.get("Shm_Info", "Error").split(",")
if os.path.isfile(Error[0]): Error = Shm(Error[0])
else:
    info("No state shared memory file. Creating file.")
    Error = config.get("Shm_Info", "Error").split(",")
    Error = Shm(Error[0], data=np.array([0], dtype=type_[Error[1]]),
        mmap = (Error[2] == "1"))

info("No duplicate control script, continuing with initialization.")

#NOTE: we want to register cleanup after Shm_D is initalized so we can edit it
#register handles keyboard interrupts and exceptions
#signal handles tmux kill-ses, and terminate
info("Registering cleanup.")
register(close)
signal(SIGHUP, signal_handler)
signal(SIGTERM, signal_handler):

info("Initializing command shared memory from config file.")

#create a subscription semaphore to link all P shms
ShmP = posix_ipc.Semaphore(None, flags = posix_ipc.O_CREX)

#create a list to store processes that are updating semaphores (to be killed 
#   at close)
Sem_Listeners = []

Stat_P = config.get("Shm_Info", "Stat_P").split(",")
Stat_P = Shm(Stat_P[0], data=Stat_D.get_data(), sem=True, mmap = (Stat_P[2] == "1"))
Sem_Listeners.append(Popen(["linksem", Stat_P.sem.name, ShmP.name]))

Pos_P = config.get("Shm_Info", "Pos_P").split(",")
Pos_P = Shm(Pos_P[0], data=Pos_D.get_data(), sem=True, mmap = (Pos_P[2] == "1"))
Sem_Listeners.append(Popen(["linksem", Pos_P.sem.name, ShmP.name]))

def Punlink():
    """Tries to unlink the lock semaphores on the P shms"""

    try: 
        Stat_P.lock.unlink()
    except (AttributeError, posix_ipc.ExistentialError) as ouch:
        info("Exception on close: {}".format(ouch))

    try: 
        Pos_P.lock.unlink()
    except (AttributeError, posix_ipc.ExistentialError) as ouch:
        info("Exception on close: {}".format(ouch))

    unregister(Punlink)

#we want to register P shm unlink acter creating shared memory, otherwise
#  the shm will be cleaned up and we lose access to the lock
register(Punlink)

info("Command shared memories successfully created.")

info("Initializing NPS")
try: nps = NPS_cmds("FIU TTM")
except:
    info("Cannot find NPS port")
    raise NPSError("Cannot find NPS port")

if not nps.is_Active():
    info("No NPS control script")
    raise NPSError("No Active NPS control script.")

#set up PI device.
pidev=GCSDevice()
#the controller actually has 4 axis but the latter 2 are for calibration,
#etc so should never be touched. Therefore, we limit our axes to 1 and 2.
axes=["1", "2"]
#since we will have multiple threads accessing the PI device, we need to 
#  avoid interruption during communication
pi_lock = threading.Lock()

#if the device is already on, connect to it
if nps.getStatus(): connect_device()
    
info("Starting display drawer")        
#we use popen to start the drawing script separately to prevent blocking
display_cmd = "FIU_TTM_draw"
draw_proc=Popen(display_cmd.split(" "))

error = 0

info("Beginning update thread.")
cur_thread = threading.Thread(target=update, daemon=True)
cur_thread.start()
info("Beginning loop.")
listener()
