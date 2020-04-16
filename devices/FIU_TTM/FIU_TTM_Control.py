#inherent python libraries
from configparser import ConfigParser
from atexit import register, unregister
from time import time, ctime, sleep
from signal import signal, SIGHUP, SIGTERM
from subprocess import Popen
from argparse import ArgumentParser
import sys, io, os, posix_ipc, threading, logging

#installs
from pipython import GCSDevice
from pipython.gcserror import GCSError
import numpy as np

#nfiuserver libraries
from shmlib import shm
from NPS import NPS_cmds

"""

THIS IS A CONTROL SCRIPT FOR THE FIBER INJECTION UNIT's TIP TILT MIRROR
AND NOT FOR USE BY USER

See FIU_TTM_cmds.py or type FIU_TTM in terminal to control the TTM 

"""

#This script is not an import
if __name__ != "__main__": 
    print("FIU_TTM_Control.py is not meant to be used as an import.")
    sys.exit()

#a flag to tell the update thread to stop what it's doing
STOP=False

cur_thread = None

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

    Inputs:
        error = the error message to put into the shm
    """

    #continuously check device info
    while not STOP:
        try:
            with pi_lock: qMOV=pidev.IsMoving()
            #if we are moving or just finished moving, update shm
            if qMOV["1"] or qMOV["2"] or Stat_D.get_data()[0] == 2:
                with pi_lock: curpos=pidev.qPOS()
                cur_t = time()
                Pos_D.set_data(np.array([curpos["1"], curpos["2"]],\
                    np.float32), atime=cur_t)
    
                stat = 2 if (qMOV["1"] or qMOV["2"]) else 1
                Stat_D.set_data(np.array([stat], np.int8), atime=cur_t)
    
                Error.set_data(np.array([error], np.uint8), atime=cur_t)
            #otherwise, make sure status is set correctly
            else:
                if Stat_D.get_data()[0] != 1: 
                    Stat_D.set_data(np.array([1], np.int8))
                if error != 0 or Error.get_data()[0] != error:
                    Error.set_data(np.array([error], np.uint8))
                with pi_lock: curpos=pidev.qPOS()
                cur_t = time()
                Pos_D.set_data(np.array([curpos["1"], curpos["2"]],\
                    np.float32), atime=cur_t)

                break
        #GCSError means that the TTM is not connected
        except GCSError:
            if Stat_D.get_data()[0] != 0:
                Stat_D.set_data(np.array([0], np.int8))
                Error.set_data(np.array([error], np.uint8))
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

    #TODO: add open loop movement
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
    #TODO: don't send move if TTM is already in position (have to check
        #precision of encoder)
    for idx in axes:
        req = target[int(idx)-1]
        info("Moving axis {} to {}.".format(idx, target))
        with pi_lock: pidev.MOV(idx, req)

    return 0

def svo_check(reqs:list):
    """Checks whether servo states should be changed and changes them if so

    Inputs:
        reqs = a list with two bools. Index n is axis n+1
    """

    info("Checking whether servo values should change.")
    with pi_lock: 
        try: servo_state = pidev.qSVO()
        except GCSError: info("GCSError."); return
    #populate a dictionary with any necessary servo changes
    svo_set={axis:reqs[int(axis)-1] for axis in axes if \
        servo_state[axis] != reqs[int(axis)-1]}

    #only send a command to the device if a change has to be made.
    if len(svo_set) > 0: 
        with pi_lock: 
            try: pidev.SVO(svo_set)
            except GCSError: info("GCSError."); return

def connect_device():
    """Connects the TTM. If device is already connected, does nothing.
        
    Reloads limits from config file and, if CAN_MOVE==True, moves.
    If the limits in the config file are outside the software limits,
        the config file will be rewrwitten
    """
    
    #Do nothing if device is off or already connected
    with pi_lock:
        if not q_pow() or pidev.IsConnected(): return 

    info("Connecting TTM PI controller.")
    with pi_lock:
        while True:
            try:
                pidev.ConnectTCPIP(ipaddress=config.get('Communication',\
                    'IP_Address'))
                info("FIU TTM Connected.")
                break
            except GCSError:
                info("Trouble connecting FIU TTM.")
                sleep(1)

    info("Extracting limits from config file.")
    global limits
    limits = {name:config.getfloat("TTM_Limits", name) for name in \
        config.options("TTM_Limits")}
    info("Config limits: {}".format(limits))

    info("Checking that config limits are within software limits.")
    #keep track of whether config file should be rewritten
    change=False
    #get software limits
    with pi_lock: softmin=pidev.qTMN()
    with pi_lock: softmax=pidev.qTMX()
    with pi_lock:
        for axis in axes:
            min_="min_{}".format(axis)
            max_="max_{}".format(axis)
            if limits[min_] < softmin[axis]:
                info("Changing {} limit".format(min_))
                limits[min_] = softmin[axis]
                config.set("TTM_Limits", min_, str(softmin[axis]))
                change=True 
            if limits[max_] < softmax[axis]:
                info("Changing {} limit".format(max_))
                limits[max_] = softmax[axis]
                config.set("TTM_Limits", max_, str(softmax[axis]))
                change=True 
    #if a change is necessary, rewrite the config file
    if change:
        with pi_lock:
            with open("TTM.ini", "w") as file:
                info("Changing limits in config file.")
                config.write(file)

    info("Getting command shared memory")

    svos = Svos.get_data()
    pos = Pos_P.get_data()

    if CAN_MOVE:
        info("Setting servos to initial values.")
        #load the starting servo values into a dict
        svo_set = {axis:int(svos[int(axis)-1]) for axis in axes}
        with pi_lock: pidev.SVO(svo_set)
        info("Moving to initial positions.")
        #load the starting position values into a dict
        pos_i = {axis:pos[int(axis)-1] for axis in axes}
        with pi_lock: pidev.MOV(pos_i)
    else:
        info("Cannot move to initial positions. Changing command shared\
         memory values.")
        with pi_lock: cur_pos = pidev.qPOS()
        with pi_lock: cur_svo = pidev.qSVO()
        #get values for each axis
        for axis in axes:
            pos[int(axis)-1] = cur_pos[axis]
            svos[int(axis)-1] = cur_svo[axis]
        
        Svos.set_data(svos)
        Pos_P.set_data(pos)

def device_off():
    """Turns off the TTM using the NPS"""

    info("Checking if TTM is connected.")
    with pi_lock:
        if pidev is not None and pidev.IsConnected():
            #Standard procedure for turning off TTM
            info("Turning off servos.")
            pidev.SVO({axis:0 for axis in axes})
            info("Zeroing voltage.")
            pidev.SVA({axis:0 for axis in axes})
            info("Closing connection to TTM.")
            pidev.CloseConnection()

    info("Sending off command to NPS")
    turn_off()

    info("Waiting for TTM to turn off.")
    while q_pow(): sleep(.5)

def device_on():
    """Waits for NPS to turn on device and then connects"""

    info("Sending on command to NPS")
    turn_on()

    info("Waiting for NPS to turn on device.")
    while not q_pow(): sleep(.1)

    info("Opening connection to TTM.")
    connect_device()

def listener():
    """A method that performs commands from the command shared memory when 
    updated, and spawns a thread that updates the position of the TTM in shm.
    """

    #we put the listening process in an infinite loop
    while True:

        #here we look at metadata instead of reading new metadata to ensure
        #  we're getting the count of the last time we updated 
        pos_cnt = Pos_P.mtdata["cnt0"]
        stat_cnt = Stat_P.mtdata["cnt0"]
        svo_cnt = Svos.mtdata["cnt0"]

        ShmP.acquire()
    
        info("command shared memory updated")
        
        error=0
        
        #check status change first
        if Stat_P.get_counter() != stat_cnt:
            info("status updated")
            req_stat = Stat_P.get_data()[0]
            if req_stat == 1:
                info("Turning on device")
                device_on()
            elif req_stat == 0:
                info("Turning off device")
                device_off()
    
        #check servo change next
        if Svos.get_counter() != svo_cnt:
            info("Servo values updated")
            svo_check(Svos.get_data())
    
        #check position change last
        if Pos_P.get_counter() != pos_cnt:
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
    except Exception as ouch: print("Exception on close: {}".format(ouch))

    info("Killing draw process.")
    try: draw_proc.terminate()
    except Exception as ouch: print("Exception on close: {}".format(ouch))

    info("Deleting command shared memory file.")
    #We want to delete all command shared memories  so scripts can't 
    #mistakenly think the control script is alive.
    try:
        for shm in [Stat_P, Pos_P, Svos]:
            try: os.remove(shm.fname)
            except Exception as ouch: print("Exception on close: {}".format(ouch))
    except Exception as ouch: print("Exception on close: {}".format(ouch))

    info("Checking if TTM is connected.")
    try:    
        if pidev.IsConnected():
            info("Turning off TTM.")
            device_off()
    except Exception as ouch: print("Exception on close: {}".format(ouch))
    
    info("Updating state shared memory file.")
    try:
        #define how the status should change
        change = {2:-1, 1:-1, 0:-2, -1:-1, -2:-2}
        #set state status based on above change
        Stat_D.set_data(np.array([change[Stat_D.get_data()[0]]], np.int8))
    except Exception as ouch: print("Exception on close: {}".format(ouch))

    #killing semaphore listening processes.
    try:
        for proc in Sem_Listeners:
            try: proc.terminate()
            except Exception as ouch: print("Exception on close: {}".format(ouch))
    except Exception as ouch: print("Exception on close: {}".format(ouch))
    
    try: ShmP.unlink()
    except Exception as ouch: print("Exception on close: {}".format(ouch))
        
    info("Closing tmux session.")
    Popen(config.get("Environment", "end_command").split(" "))

#read TTM config file
config = ConfigParser()
config.read("FIU_TTM.ini")

log_path=config.get("Communication", "debug_log")
debug_format = "%(filename)s.%(funcName)s@%(asctime)s - %(levelname)s: %(message)s"

parser = ArgumentParser()
#boolean flag for CAN_MOVE
parser.add_argument("-m", action="store_true")
#flags to put into debug move
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
    "complex128":np.complex128, "bool":np.bool}

#for now we just want to connect to shm to see if there's already a script
Stat_D = config.get("Shm_Info", "Stat_D").split(",")
if os.path.isfile(Stat_D[0]): 
    Stat_D = shm(Stat_D[0])
    status=Stat_D.get_data()[0]

    if status in [2, 1, 0]:
        info("Active control script exists. Raising exception.")
        msg="State shared memory status {}.".format(status)
        raise AlreadyAlive(msg)
else:
    info("No state shared memory file. Creating file.")
    Stat_D = config.get("Shm_Info", "Stat_D").split(",") +\
        config.get("Shm_Init", "Stat_D").split(",")
    Stat_D = shm(Stat_D[0], data=np.array([Stat_D[2:]], dtype=type_[Stat_D[1]]))


Pos_D = config.get("Shm_Info", "Pos_D").split(",")
if os.path.isfile(Pos_D[0]): Pos_D = shm(Pos_D[0])
else:
    info("No state shared memory file. Creating file.")
    Pos_D = config.get("Shm_Info", "Pos_D").split(",") +\
        config.get("Shm_Init", "Pos_D").split(",")
    Pos_D = shm(Pos_D[0], data=np.array([Pos_D[2:]], dtype=type_[Pos_D[1]]))

Error = config.get("Shm_Info", "Error").split(",")
if os.path.isfile(Error[0]): Error = shm(Error[0])
else:
    info("No state shared memory file. Creating file.")
    Error = config.get("Shm_Info", "Error").split(",") +\
        config.get("Shm_Init", "Error").split(",")
    Error = shm(Error[0], data=np.array([Error[2:]], dtype=type_[Error[1]]))

info("No duplicate control script, continuing with initialization.")

#NOTE: we want to register cleanup after Shm_D is initalized so we can edit it
#register handles keyboard interrupts and exceptions
#signal handles tmux kill-ses, and terminate
info("Registering cleanup.")
register(close)
signal(SIGHUP, close)
signal(SIGTERM, close)

info("Initializing command shared memory from config file.")

#create a subscription semaphore to link all P shms
ShmP = posix_ipc.Semaphore(None, flags = posix_ipc.O_CREX)

#create a list to store processes that are updating semaphores (to be killed 
#   at close)
Sem_Listeners = []

Stat_P = config.get("Shm_Info", "Stat_P").split(",") +\
    config.get("Shm_Init", "Stat_P").split(",")
Stat_P = shm(Stat_P[0], data=np.array([Stat_P[2:]], dtype=type_[Stat_P[1]]),\
     sem=True)
Sem_Listeners.append(Popen(["linksem", Stat_P.sem.name, ShmP.name]))

Pos_P = config.get("Shm_Info", "Pos_P").split(",") +\
    config.get("Shm_Init", "Pos_P").split(",")
Pos_P = shm(Pos_P[0], data=np.array([Pos_P[2:]], dtype=type_[Pos_P[1]]),\
    sem=True)
Sem_Listeners.append(Popen(["linksem", Pos_P.sem.name, ShmP.name]))

Svos = config.get("Shm_Info", "Svos").split(",") +\
    config.get("Shm_Init", "Svos").split(",")
Svos = shm(Svos[0], data=np.array([Svos[2:]], dtype=type_[Svos[1]]), sem=True)
Sem_Listeners.append(Popen(["linksem", Svos.sem.name, ShmP.name]))

def Punlink():
    """Tries to unlink the lock semaphores on the P shms"""

    try: 
        Stat_P.lock.unlink()
    except (AttributeError, posix_ipc.ExistentialError) as ouch:
        print("Exception on close: {}".format(ouch))

    try: 
        Pos_P.lock.unlink()
    except (AttributeError, posix_ipc.ExistentialError) as ouch:
        print("Exception on close: {}".format(ouch))

    try: 
        Svos.lock.unlink()
    except (AttributeError, posix_ipc.ExistentialError) as ouch:
        print("Exception on close: {}".format(ouch))

#we want to register P shm unlink before creating shared memory, otherwise
#  the shm will be cleaned up and we lose access to the lock
register(Punlink)
signal(SIGHUP, Punlink)

info("Command shared memories successfully created.")

info("Initializing NPS")
NPS=NPS_cmds()
info("Finding TTM port")
NPS.TTM_port = None
for port, dev in enumerate(NPS.devices):
    if dev == "FIU TTM":
        NPS.TTM_port = port
        break
if NPS.TTM_port is None:
    info("Cannot find NPS port")
    raise NPSError("Cannot find NPS port")

#convenience methods to deal with the NPS
turn_on = lambda: NPS.turnOn(NPS.TTM_port)
turn_off = lambda: NPS.turnOff(NPS.TTM_port)
q_pow = lambda: NPS.getStatusAll()[NPS.TTM_port]

#set up PI device.
pidev=GCSDevice()
#the controller actually has 4 axis but the latter 2 are for calibration,
#etc so should never be touched. Therefore, we limit our axes to 1 and 2.
axes=["1", "2"]
#since we will have multiple threads accessing the PI device, we need to 
#  avoid interruption during communication
pi_lock = threading.Lock()

#if the device is already on, connect to it
if q_pow(): connect_device()
    
info("Starting display drawer")        
#we use popen to start the drawing scrip separately to prevent blocking
display_cmd = "kpython3 FIU_TTM_draw.py"
draw_proc=Popen(display_cmd.split(" "))

error = 0

info("Beginning update thread.")
cur_thread = threading.Thread(target=update, daemon=True)
cur_thread.start()
info("Beginning loop.")
listener()
