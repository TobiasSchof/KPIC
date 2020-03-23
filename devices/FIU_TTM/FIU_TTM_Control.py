#inherent python libraries
from configparser import ConfigParser
from atexit import register
from time import time, ctime, sleep
from signal import signal, SIGHUP
from subprocess import Popen as bash
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
        old = Pos_D.get_data().item()
        cur_t = time()
        try:
            qMOV=pidev.IsMoving()
        #GCSError means that the TTM is not connected
        except GCSError:
            if Stat_D.get_data().item() != 0 or QCONST:
                Stat_D.set_data() = 0
                old[str_d["error"]] = error
                Shm_D.set_data(old)
            
        #if we are moving, just finished moving, or QCONST, update shm
        if qMOV or QCONST or old[self.str_d["status"]] == 2:
            curpos=pidev.qPOS()
            old[str_d["cur_t"]] = cur_t
            old[str_d["pos_1"]] = curpos["1"]
            old[str_d["pos_2"]] = curpos["2"]
            old[str_d["status"]] = 2 if qMOV else 1
            old[str_d["error"]] = error

async def listener() -> int:
    """A method to be used with asyncio that performs commands from 
    the command shared memory when updated.

    Outputs:
        int = any error message
    """

    #asyncio will let other processes run while we wait for new data in 
    #the command shared memory.
    data = await self.Shm_P.await_data()
    info("command shared memory updated")
        
    error=0

    req_status=data[str_p["status"]]
    if req_status == 1:
        info("On status requested. Checking connection to TTM.")
        #See if the last device state was off
        dataD = Shm_D.get_data()
        dev_status = dataD[str_d["status"]]
        #status == 0 corresponds to device off
        if dev_status == 0:
            info("Turning on device")
            device_on()
            #in case turning on the device changed the command shared
            #memory, we grab it again
            data = Shm_P.get_data()

        #perform any requested actions
        svo_check(data)
        error = move_check(data)
    elif req_status == -1:
        info("Killing control script.")
        close()
    elif req_status == 0:
        info("Turning off device.")
        device_off()
     info("Commands processed.")
     #we only want update writing to shm_d so we return the error to pass
     #it to update rather than updating directly.
     return error

def move_check(data:list) -> int:
    """Checks whether a move command should be sent to the device
    and sends it if so.

    Inputs:
        data = the result of Shm_P.get_data
    Outputs:
        int = the error code (if any) : see TTM.ini for details
    """

    info("Checking whether move is needed.")

    #TODO: add open love movement
    #The loop is open. Movement has to be done differently
    if not all(pidev.qSVO().values()):
        info("Loop open")
        return 2

    #If the loop is closed, continue
    curpos=pidev.qPOS()
    for idx in axes:
        target=data[str_p["pos_"+idx]].item()
        if target < limits["min_"+idx] or target > limits["max_"+idx]:
            info("Movement requested outside of motion range.")
            return 1
        elif curpos[idx] != target:
            info("Moving axis {} to {}.".format(idx, target))
            pidev.MOV(idx, target)

    return 0


def svo_check(data:list):
    """Checks whether servo states should be changed and changes them if so

    Inputs:
        data = the result of Shm_P.get_data
    """

    info("Checking whether servo values should change.")
    servo_state = pidev.qSVO()
    #populate a dictionary so we can make all servo changes at once
    svo_set={}
    for axis in axes:
        #if the current servo state is different than what's in shm_p,
        #add the change to svo_set
        req_state = int(data[str_p["svo_{}".format(axis)]].item())
        if servo_state[axis] != req_state: svo_set[axis] = req_state

    #only send a command to the device if a change has to be made.
    if len(svo_set > 0) : pidev.SVO(svo_set)

def connect_device(self):
    """Connects the TTM. If device is already connected, does nothing.
        
    Reloads limits from config file and, if CAN_MOVE==True, moves.
    If the limits in the config file are outside the software limits,
        the config file will be rewrwitten
    """

    if qon() and not pidev.IsConnected():
        info("Connecting TTM PI controller.")
        pidev.ConnectTCPIP(ipaddress=config.get('Communication','IP_Address'))
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
                info("Changing {}".format(min_))
                limits[min_] = softmin[axis]
                config.set("TTM_Limits", min_, str(softmin[axis]))
                change=True 
            if limits[max_] < softmax[axis]:
                info("Changing {}".format(max_))
                limits[max_] = softmax[axis]
                config.set("TTM_Limits", max_, str(softmax[axis]))
                change=True 
        #if a change is necessary, rewrite the config file
        if change:
            with open("TTM.ini", "w") as file:
                info("Changing limits in config file.")
                self.config.write(file)

        info("Getting command shared memory")
        data=Shm_P.get_data()

        if CAN_MOVE:
            info("Setting servos to initial values.")
            #load the starting servo values into a dict
            svo_set = {axis:int(data[str_p["svo_{}".format(axis)]].item()) for\
                axis in axes}
            pidev.SVO(svo_set)
            info("Moving to initial positions.")
            #load the starting position values into a dict
            pos_i = {axis:data[str_p["pos_".format(axis)]].item() for\
                 axis in axes}
            pidev.MOV(pos_i)
        else:
            info("Cannot move to initial positions. Changing command shared memory values.")
            pos=pidev.qPOS()
            #get values for each axis
            for axis in axes:
                data[str_p["pos_{}".format(axis)]] = pos[axis]
                data[str_p["svo_{}".format(axis)]] = pidev.qSVO()[axis]
            Shm_P.set_data(data)
            #decrement the semaphore value since we just wrote to shm_p
            Shm_P.get_data(check=True)

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

    info("Waiting for TTM to turn off.")
    while qon(): sleep(.5)

def device_on():
    """Waits for NPS to turn on device and then connects"""

    info("Waiting for NPS to turn on device.")
    while not qon(): sleep(.1)

    info("Opening connection to TTM.")
    connect_device()

def close():
    """A cleanup method.

    Closes all communication with the TTM, deletes command shared memory,
    and closes tmux session.
    """

    info("Deleting command shared memory file.")
    #We want to delete shm_p so scripts can't think the control script
    #is alive.
    try:
        os.remove(p_shm_name)
    except FileNotFoundError:
        info("No command shared memory found.")

    info("Updating state shared memory file.")
    try:
        data=Shm_D.get_data()
        stat=data[str_d["status"]].item()
        if stat == 2: stat = 1
        if stat in [1, 0]:
            data[str_d["status"]] = stat-2
            data[str_d["cur_t"]] = time()
            Shm_D.set_data(data)
    #This shouldn't ever happen but in a cleanup method we don't want
    #exceptions.
    except AttributeError:
        info("No state shared memory found.")

    info("Checking if TTM is connected.")
    try:    
        if pidev.IsConnected():
            info("Closing connection to TTM.")
            pidev.CloseConnection()
    except OSError:
        info("PIPython not loaded properly.")
    except AttributeError:
        info("No PI device.")
        
    info("Closing tmux session.")
    bash(self.config.get("Environment", "end_command").split(" "))


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
#boolean flag for QCONST
parser.add_argument("-c", action="store_true")

args = parser.parse_args()

CAN_MOVE = args.m #whether this device can move on startup
QCONST = args.c #whether to update constantly or only when moving

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

#shm d is state shared memory.
d_shm_name=config.get("Shm_path", "Shm_D")
info("Reading state shared memory.")

#load the indices for the shared memory
str_d={name:config.getint("Shm_D_Content", name) for name in \
    config.options("Shm_D_Content")}

#for now we just want to connect to shm to see if there's already a script
Shm_D=shm(d_shm_name)

try:
    info("Checking whether there is already an active control script.")
    status=Shm_D.get_data()[str_d["status"]]

    if status in [1, 0]:
        info("Active control script exists. Raising exception.")
        msg="State shared memory status {}.".format(status)
        raise AlreadyAlive(msg)
#This means that shm_d doesn't exist, so make it
except AttributeError:
    info("No state shared memory file. Creating file.")
    #load initial values from config
    data = [config.getfloat("Shm_D_Init", name) for name in \
        config.options("Shm_D_Content")] 
    #we need float to hold the position 
    #NOTE: might be able to get away with float16 but can't find 
        #precision of stage to find out. 
    Shm_D  = shm(d_shm_name, data=np.array(data, np.float32, ndmin=2)
    info("State shared memory file created.")

info("No duplicate control script, continuing with initialization.")

#NOTE: we want to register cleanup after Shm_D is initalized so we can edit it
#register handles keyboard interrupts and exceptions
#signal handles tmux kill-ses
info("Registering cleanup.")
register(self.close)
signal(SIGHUP, self.close)

#shm p is command shared memory, 
p_shm_name=config.get("Shm_path", "Shm_P")
info("Initializing command shared memory from config file.")
#get the names of the values to be stored in shm_p
names = self.config.options("Shm_P_Content")
#get shm indices for each value
str_p = {name:config.getint("Shm_P_Content", name) for name in names}
#get initial value for each
data=[config.getfloat("Shm_P_Init", name) for name in names]

#use float32 for position as above
Shm_P=shm(p_shm_name, data=np.array(data, np.float32, ndmin=2))

#creating the shm incremements the semaphore, so we decrement it
self.Shm_P.get_data(check=True)
info("Command shared memory successfully created.")

info("Finding NPS shared memories")
_=ConfigParser()
_.read("NPS.ini")
#TODO: in executable, check if NPS shm exists and warn user if not
#set nps to listen for TTM
nps_shm_p = _.get("Shm_path", "Shm_P")
if not os.path.isfile(nps_shm_p):
    tmp = shm(nps_shm_p)
    tmp_data = tmp.get_data()
    tmp_data[_.getint("Shm_indices", "TTM")] = 1
    tmp.set_data(tmp_data)

#initialize NPS shm_d and store index of TTM (use qon defined below)
NPS_Shm_D = [shm(_.get("Shm_path", "Shm_D"), _.getint("Shm_indices", "TTM")]
#create lambda method to easily fetch TTM on status
qon = lambda: bool(NPS_Shm_D[0].get_data()[NPS_Shm_D[1]])

#set up PI device.
pidev=GCSDevice()
#the controller actually has 4 axis but the latter 2 are for calibration,
#etc so should never be touched. Therefore, we limit our axes to 1 and 2.
axes=["1", "2"]
if qon(): connect_device()
    
info("Starting display drawer")        
#we use popen to start the drawing scrip separately to prevent blocking
display_cmd = "kpython3 TTM_draw.py"
bash(display_cmd.split(" "))

async def manager(error:int=0) -> int:
    """A manager to start the asyncio tasks"""

    #We start both methods as tasks, passing the error to update
    task1 = asyncio.create_task(update(error))
    task2 = asynvio.create_task(listener())

    #We only wait for task 2 to finish because task1 will continuously
    #check but we need to update the error if listener runs.
    return await task2

error = 0

info("Beginning loop.")
while True: error = asyncio.run(manager(error))
