#inherent python libraries
from configparser import ConfigParser
from atexit import register
from time import time, ctime, sleep
from signal import signal, SIGHUP
from subprocess import Popen as shell
from argparse import ArgumentParser
import sys, io, os, asyncio, logging

#installs
from pipython import GCSDevice
from pipython.gcserror import GCSError
import numpy as np

#nfiuserver libraries
from shmlib import shm

"""

THIS IS A CONTROL SCRIPT FOR THE FIBER INJECTION UNIT's TIP TILT MIRROR
AND NOT FOR USE BY USER

See FIU_TTM_cmds.py or type FIU_TTM in terminal to control the TTM 

"""

#This script is not an import
if __name__ != "__main__": sys.exit()

info=logging.info

class AlreadyAlive(Exception):
    """An exception to be thrown if control code is initialized twice"""

    pass

async def update(error:int=0):
    """A method to be used with asyncio that continuously checks the
    state of the TTM and updates the shm if necessary.

    Inputs:
        error = the error message to put into the shm
    """

    #continuously check device info
    while True:
        #we need an await so asyncio knows where it can interupt the loop
        await asyncio.sleep(0)
        try:
            qMOV=pidev.IsMoving()
        #GCSError means that the TTM is not connected
        except GCSError:
            if Stat_D.get_data()[0] != 0:
                Stat_D.set_data(np.array([0], np.int8)
                Error.set_data(np.array([error], np.uint8))
                continue
            
        #if we are moving or just finished moving, update shm
        if qMOV or Stat_D.get_data()[0] == 2:
            curpos=pidev.qPOS()
            cur_t = time()
            Pos_D = np.array([curpos["1"], curpos["2"], cur_t], np.float)

            stat = 2 if qMOV else 1
            Stat_D.set_data(np.array([stat], np.int8)

            Error.set_data(np.array([error], np.uint8)
        #otherwise, make sure status is set correctly
        else:
            if Stat_D.get_data()[0] != 1: 
                Stat_D.set_data(np.array([1], np.int8))

async def listener() -> int:
    """A method to be used with asyncio that performs commands from 
    the command shared memory when updated.

    Outputs:
        int = any error message
    """

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
        if not all(pidev.qSVO().values()):
            info("Loop open")
            return 2

        #check whether target is valid before moving
        for idx in axes:
            req = target[int(idx)-1]
            if req < limits["min_"+idx] or target > limits["max_"+idx]:
                info("Movement requested outside of motion range")
                return 1

        #perform movement
        #TODO: don't send move if TTM is already in position (have to check
            #precision of encoder)
        for idx in axes:
            req = target[int(idx)-1]
            info("Moving axis {} to {}.".format(idx, target))
            pidev.MOV(idx, target)

        return 0

    def svo_check(reqs:list):
        """Checks whether servo states should be changed and changes them if so
    
        Inputs:
            reqs = a list with two bools. Index n is axis n+1
        """
    
        info("Checking whether servo values should change.")
        servo_state = pidev.qSVO()
        #populate a dictionary with any necessary servo changes
        svo_set={axis:reqs[int(axis)-1] for axis in servo_state if \
            servo_state[axis] != reqs[int(axis)-1]}
    
        #only send a command to the device if a change has to be made.
        if len(svo_set > 0): pidev.SVO(svo_set)
    
    def connect_device(self):
        """Connects the TTM. If device is already connected, does nothing.
            
        Reloads limits from config file and, if CAN_MOVE==True, moves.
        If the limits in the config file are outside the software limits,
            the config file will be rewrwitten
        """
        
        #Do nothing if device is off or already connected
        if not q_pow() and pidev.IsConnected(): return 

        info("Connecting TTM PI controller.")
        pidev.ConnectTCPIP(ipaddress=config.get('Communication', 'IP_Address'))
        info("TTM connected.")

        info("Extracting limits from config file.")
        global limits
        limits = {name:config.getfloat("TTM_Limits", name) for name in \
            config.options("TTM_Limits")}
        info("Config limits: {}".format(self.limits))

        info("Checking that config limits are within software limits.")
        #keep track of whether config file should be rewritten
        change=False
        #get software limits
        softmin=pidev.qTMN()
        softmax=pidev.qTMX()
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
            with open("TTM.ini", "w") as file:
                info("Changing limits in config file.")
                self.config.write(file)

        info("Getting command shared memory")

        svos = Svos.get_data()
        pos = Pos_P.get_data()

        if CAN_MOVE:
            info("Setting servos to initial values.")
            #load the starting servo values into a dict
            svo_set = {axis:int(svos[int(axis)-1])) for axis in axes}
            pidev.SVO(svo_set)
            info("Moving to initial positions.")
            #load the starting position values into a dict
            pos_i = {axis:pos[int(axis)-1] for axis in axes}
            pidev.MOV(pos_i)
        else:
            info("Cannot move to initial positions. Changing command shared \
                memory values.")
            cur_pos = pidev.qPOS()
            cur_svo = pidev.qSVO()
            #get values for each axis
            for axis in axes:
                pos[int(axis)-1] = cur_pos[axis]
                svos[int(axis)-1] = cir_svo[axis]
            
            Svos.set_data(svos)
            Pos_P.set_data(pos)
    
    def device_off():
        """Turns off the TTM using the NPS"""
    
        info("Checking if TTM is connected.")
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

    #asyncio will let other processes run while we wait for new data in 
    #the command shared memory.
    req_pos = asyncio.create_task(self.Pos_P.await_data())
    req_stat = asyncio.create_task(self.Stat_P.await_data())
    req_svo = asyncio.create_task(self.Stat_P.await_data())

    #wait until one of the command shared memories is updated
    done, _ = asyncio.wait([req_pos, req_stat, req_svo], \
        return_when=asyncio.FIRST_COMPLETED)

    info("command shared memory updated")
    
    error=0
    
    #check status change first
    if req_stat in done:
        info("status updated")
        req_stat = req_stat.result()[0]
        if req_stat == 1:
            info("Turning on device")
            device_on()
        elif req_stat == 0:
            info("Turning off device")
            device_off()

    #check servo change next
    if req_svo in done:
        info("Servo values updated")
        svo_check(req_svo.result())

    #check position change last
    if req_pos in done:
        info("Position updated")
        error = move(req_pos.result())
    
    return error

def close():
    """A cleanup method.

    Closes all communication with the TTM, deletes command shared memory,
    and closes tmux session.
    """

    info("Deleting command shared memory file.")
    #We want to delete all command shared memories  so scripts can't 
    #mistakenly think the control script is alive.
    for shm in [Stat_P, Pos_P, Svos]:
        try: os.remove(shm.fname)
        except FileNotFoundError: info("No command shared memory found.")

    info("Updating state shared memory file.")
    try:
        #define how the status should change
        change = {2:-1, 1:-1, 0:-2, -1:-1, -2:-2}
        #set state status based on above change
        Stat_D.set_data(np.array([change[Stat_D.get_data()[0]]], np.int8))
    #This shouldn't ever happen but in a cleanup method we don't want
    #exceptions.
    except AttributeError: info("Shared memory problem.")

    info("Checking if TTM is connected.")
    try:    
        if pidev.IsConnected():
            info("Closing connection to TTM.")
            pidev.CloseConnection()
    except OSError: info("PIPython not loaded properly.")
        
    info("Closing tmux session.")
    shell(self.config.get("Environment", "end_command").split(" "))

#read TTM config file
config = ConfigParser()
config.read("TTM.ini")

log_path=config.get("Communication", "log_path")
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
    basicConfig(format=debug_format, datefmt="%H:%M:%S", \
        filename=log_path)
    logging.root.setLevel(logging.INFO)

#for now we just want to connect to shm to see if there's already a script
Stat_D = config.get("Shm_Info", "Stat_D").split(",")
Stat_D = shm(Stat_D[0], nbSems=int(Stat_D[1]))

Pos_D = config.get("Shm_Info", "Pos_D").split(",")
Pos_D = shm(Pos_D[0], nbSems=int(Pos_D[1]))

Error = config.get("Shm_Info", "Error").split(",")
Error = shm(Error[0], nbSems=int(Error[1]))

#create a dictionary to translate strings into numpy data types
type_ = {"int8":np.int8, "int16":np.int16, "int32":np.int32, "int64":np.int64,\
    "uint8":np.uint8, "uint16":np.uint16, "uint32":np.uint32,\
    "uint64":np.uint64, "intp":np.intp, "uintp":np.uintp, "float16":np.float16,\ 
    "float32":np.float32, "float64":np.float64, "complex64":np.complex64,\
    "complex128":np.complex128, "bool":np.bool}

try:
    info("Checking whether there is already an active control script.")
    status=Stat_D.get_data()[0]

    if status in [2, 1, 0]:
        info("Active control script exists. Raising exception.")
        msg="State shared memory status {}.".format(status)
        raise AlreadyAlive(msg)
#This means that shm_d doesn't exist, so make it
except AttributeError:
    info("No state shared memory file. Creating file.")

    Stat_D = config.get("Shm_Info", "Stat_D").split(",") +\
        config.get("Shm_Init", "Stat_D").split(",")
    Stat_D = shm(Stat_D[0], data=np.array([Stat_D[3:]], type_[Stat_D[2]]),\
        nbSems=int(Stat_D[1]))

    Pos_D = config.get("Shm_Info", "Pos_D").split(",") +\
        config.get("Shm_Init", "Pos_D").split(",")
    Pos_D = shm(Pos_D[0], data=np.array([Pos_D[3:]], type_[Pos_D[2]]),\
        nbSems=int(Pos_D[1]))

    Error = config.get("Shm_Info", "Error").split(",") +\
        config.get("Shm_Init", "Error").split(",")
    Error = shm(Error[0], data=np.array([Error[3:]], type_[Error[2]]),\
        nbSems=int(Error[1]))

    info("State shared memory files created.")

info("No duplicate control script, continuing with initialization.")

#NOTE: we want to register cleanup after Shm_D is initalized so we can edit it
#register handles keyboard interrupts and exceptions
#signal handles tmux kill-ses
info("Registering cleanup.")
register(self.close)
signal(SIGHUP, self.close)

info("Initializing command shared memory from config file.")

Stat_P = config.get("Shm_Info", "Stat_P").split(",") +\
    config.get("Shm_Init", "Stat_P").split(",")
Stat_P = shm(Stat_P[0], data=np.array([Stat_P[3:]], type_[Stat_P[2]]),\
    nbSems=int(Stat_P[1]))

Pos_P = config.get("Shm_Info", "Pos_P").split(",") +\
    config.get("Shm_Init", "Pos_P").split(",")
Pos_P = shm(Pos_P[0], data=np.array([Pos_P[3:]], type_[Pos_P[2]]),\
    nbSems=int(Pos_P[1]))

Svos = config.get("Shm_Info", "Svos").split(",") +\
    config.get("Shm_Init", "Svos").split(",")
Svos = shm(Svos[0], data=np.array([Svos[3:]], type_[Svos[2]]),\
    nbSems=int(Svos[1]))

info("Command shared memories successfully created.")

info("Initializing NPS")
NPS=NPS_cmds()
info("Finding TTM port")
NPS.dev_idx = NPS.devices.index("FIU TTM")
#convenience methods to deal with the NPS
turn_on = lambda: NPS.turn_on(NPS.dev_idx+1)
turn_off = lambda: NPS.turn_off(NPS.dev_idx+1)
q_pow = lambda: NPS.getStatusAll()[NPS.dev_idx]

#set up PI device.
pidev=GCSDevice()
#the controller actually has 4 axis but the latter 2 are for calibration,
#etc so should never be touched. Therefore, we limit our axes to 1 and 2.
axes=["1", "2"]
if q_pow(): connect_device()
    
info("Starting display drawer")        
#we use popen to start the drawing scrip separately to prevent blocking
display_cmd = "kpython3 TTM_draw.py"
shell(display_cmd.split(" "))

async def manager(error:int=0) -> int:
    """A manager to start the asyncio tasks"""

    #We start both methods as tasks, passing the error to update
    Shm_D_handler = asyncio.create_task(update(error))
    Shm_P_handler = asyncio.create_task(listener())

    #wait for shm p to update so we can update error message in task1
    return await Shm_P_handler

error = 0

info("Beginning loop.")
while True: error = asyncio.run(manager(error))
