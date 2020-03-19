#inherent python libraries
from logging import info, basicConfig, INFO, DEBUG
from configparser import ConfigParser
from atexit import register
from time import time, ctime, sleep
from signal import signal, SIGHUP
from subprocess import Popen as bash
from argparse import ArgumentParser
import sys, io, os, asyncio

#installs
from pipython import GCSDevice
from pipython.gcserror import GCSError
import numpy as np

#telescope libraries
from sce_shmlib import shm
from NPS_lib import NPS

"""

THIS IS A CONTROL SCRIPT FOR THE TIP TILT MIRROR
AND NOT FOR USE BY USER

See TTM_cmds.py or type TTM in terminal to control the TTM 

"""

#This script is not an import
if __name__ != "__main__": sys.exit()

CAN_MOVE = False #whether this device can move on startup
QCONST = False #Whether this device should update shm constantly or only when moving

class AlreadyAlive(Exception):
    """An exception to be thrown if control code is initialized twice"""

    pass

def makeShm(path:str, data=None):
    """Convenience method to make a shared memory structure silently"""
async def update(self, error:int=0):
    """A method to be used with asyncio that continuously checks the
    state of the TTM and updates the shm if necessary.

    Inputs:
        error = the error message to put into the shm
    """

    #continuously check device info
    while True:
        #we need an await so asyncio knows where it can interupt the loop
        await asyncio.sleep(0)
        old = self.Shm_D.get_data()
        cur_t=time()
        try:
            qMOV=self.pidevice.IsMoving()
        #GCSError means that the TTM is not connected
        except GCSError:
            if old[self.str_d["status"]] != 0 or QCONST:
                old[self.str_d["cur_t"]] = cur_t
                old[self.str_d["status"]] = 0
                old[self.str_d["error"]] = error
                self.Shm_D.set_data(old)
            
        #if we are moving, just finished moving, or QCONST, update shm
        if qMOV or QCONST or old[self.str_d["status"]] == 2:
            curpos=dev.qPOS()
            old[self.str_d["cur_t"]] = cur_t
            old[self.str_d["pos_1"]] = curpos["1"]
            old[self.str_d["pos_2"]] = curpos["2"]
            old[self.str_d["status"]] = 2 if qMOV else 1
            old[self.str_d["error"]] = error

async def listener(self) -> int:
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

    req_status=data[self.str_p["status"]]
    if req_status == 1:
        info("On status requested. Checking connection to TTM.")
        #See if the last device state was off
        dataD = self.Shm_D.get_data()
        dev_status = dataD[self.str_d["status"]]
        #status == 0 corresponds to device off
        if dev_status == 0:
            info("Turning on device")
            self.device_on()
            #in case turning on the device changed the command shared
            #memory, we grab it again
            data = self.Shm_P.get_data()

        #perform any requested actions
        self.svo_check(data)
        error = self.move_check(data)
    elif req_status == -1:
        info("Killing control script.")
        self.close()
    elif req_status == 0:
        info("Turning off device.")
        self.device_off()
     info("Commands processed.")
     #we only want update writing to shm_d so we return the error to pass
     #it to update rather than updating directly.
     return error

def move_check(self, data:list) -> int:
    """Checks whether a move command should be sent to the device and sends it if so

    Inputs:
        data = the result of Shm_P.get_data
    Outputs:
        int = the error code (if any) : see TTM.ini for details
    """

    info("Checking whether move is needed.")

    #The loop is open. Movement has to be done differently
    if not all(self.pidevice.qSVO().values()):
        info("Loop open")
        return 2

    #If the loop is closed, continue
    curpos=self.pidevice.qPOS()
    for idx in self.axes:
        target=data[self.str_p["pos_"+idx]].item()
        if target < self.limits["min_"+idx] or target > self.limits["max_"+idx]:
            info("Movement requested outside of motion range.")
            return 1
            elif curpos[idx] != target:
                info("Moving axis {} to {}.".format(idx, target))
                self.pidevice.MOV(idx, target)

    return 0


def svo_check(self, data:list):
    """Checks whether servo states should be changed and changes them if so

    Inputs:
        data = the result of Shm_P.get_data
    """

    info("Checking whether servo values should change.")
    servo_state = self.pidevice.qSVO()
    #populate a dictionary so we can make all servo changes at once
    svo_set={}
    for axis in self.axes:
        #if the current servo state is different than what's in shm_p,
        #add the change to svo_set
        req_state = int(data[self.str_p["svo_{}".format(axis)]].item())
        if servo_state != req_state: svo_set[axis] = req_state

    #only send a command to the device if a change has to be made.
    if len(svo_set > 0) : self.pidevice.SVO(svo_set)

def connect_device(self):
    """Connects the TTM. If device is already connected, does nothing.
        
    Reloads limits from config file and, if CAN_MOVE==True, moves.
    If the limits in the config file are outside the software limits,
        the config file will be rewrwitten
    """

    if self.NPS.getStatusAll()[NPS_PORT] and not self.pidevice.IsConnected():
        info("Connecting TTM PI controller.")
        self.pidevice.ConnectTCPIP(ipaddress = self.config.get('Communication','IP_Address'))
        info("TTM connected.")

        info("Extracting limits from config file.")
        self.limits = {}
        for name in self.config.options('TTM_Limits'):
            self.limits[name] = self.config.getfloat('TTM_Limits', name)
        info("Config limits: {}".format(self.limits))

        info("Checking that config limits are within software limits.")
        #keep track if config file should be rewritten
        change=False
        #get software limits
        softmin=self.pidevice.qTMN()
        softmax=self.pidevice.qTMX()
        for axis in self.axes:
            if self.limits["min_{}".format(axis)] < softmin[axis]:
                info("Changing min_{}".format(axis))
                self.limits["min_{}".format(axis)] = softmin[axis]
                self.config.set("TTM_Limits", "min_{}".format(axis), str(softmin[axis]))
                change=True 
            if self.limits["max_{}".format(axis)] < softmax[axis]:
                info("Changing max_{}".format(axis))
                self.limits["max_{}".format(axis)] = softmax[axis]
                self.config.set("TTM_Limits", "max_{}".format(axis), str(softmax[axis]))
                change=True 
        if change:
            with open("TTM.ini", "w") as file:
                info("Changing limits in config file.")
                self.config.write(file)

        data=self.Shm_P.get_data()

        if CAN_MOVE:
            info("Setting servos to initial values.")
            #load the starting servo values into a dict
            svo_set = {x:int(data[self.str_p["svo_{}".format(x)]].item()) for x in self.axes}
            self.pidevice.SVO(svo_set)
            info("Moving to initial positions.")
            #load the starting position values into a dict
            pos_i = {x:data[self.str_p["pos_".format(x)]].item() for x in self.axes}
            self.pidevice.MOV(pos_i)
        else:
            info("Cannot move to initial positions. Changing command shared memory values.")
            pos=self.pidevice.qPOS()
            #get values for each axis
            for axis in self.axes:
                data[self.str_p["pos_{}".format(axis)]] = pos[axis]
                data[self.str_p["svo_{}".format(axis)]] = self.pidevice.qSVO()[axis]
            self.Shm_P.set_data(data)
            #decrement the semaphore value since we just wrote to shm_p
            self.Shm_P.get_data(check=True)

def device_off(self):
    """Turns off the TTM using the NPS"""

    info("Checking if TTM is connected.")
    if self.pidevice is not None and self.pidevice.IsConnected():
        #Standard procedure for turning off TTM
        info("Turning off servos.")
        self.pidevice.SVO({x:0 for x in self.axes})
        info("Zeroing voltage.")
        self.pidevice.SVA({x:0 for x in self.axes})
        info("Closing connection to TTM.")
        self.pidevice.CloseConnection()

    info("Checking if TTM is off.")
    if self.NPS.getStatusAll()[NPS_PORT]:
        info("Turning TTM off.")
        self.NPS.turnOff(NPS_PORT)
        #Wait for device to power off completely before continuing
        while self.NPS.getStatusAll()[NPS_PORT]: sleep(.5)

def device_on(self):
    """Turns on the TTM using the NPS"""

    info("Checking if TTM is on.")
    if not self.NPS.getStatusAll()[NPS_PORT]:
        info("Turning on TTM.")
        self.NPS.turnOn(NPS_PORT + 1)
        #Wait for device to turn on
        while not self.NPS.getStatusAll()[NPS_PORT]: sleep(.5)

    info("Opening connection to TTM.")
    self.connect_device()

def close(self):
    """A cleanup method.

    Closes all communication with the TTM, deletes command shared memory,
    and closes tmux session.
    """

    info("Checking whether this instance is alive.")
    try:
        #if constructor didn't get to shm_p, this will raise an error
        self.Shm_P
        info("Command shared memory initialized, instance alive.")
        info("Continuing with cleanup.")
    except AttributeError:
        info("No command shared memory initialized. Doing nothing.")
        return

    info("Deleting command shared memory file.")
    #We want to delete shm_p so scripts can't think the control script
    #is alive.
    try:
        os.remove(self.p_shm_name)
    except FileNotFoundError:
        info("No command shared memory found.")

    info("Updating state shared memory file.")
    try:
        data=self.Shm_D.get_data()
        stat=data[self.str_d["status"]].item()
        if stat == 2: stat = 1
        if stat in [1, 0]:
            data[self.str_d["status"]] = stat-2
            data[self.str_d["cur_t"]] = time()
            self.Shm_D.set_data(data)
    #This shouldn't ever happen but in a cleanup method we don't want
    #exceptions.
    except AttributeError:
        info("No state shared memory found.")

    info("Checking if TTM is connected.")
    try:    
        if self.pidevice.IsConnected():
            info("Closing connection to TTM.")
            self.pidevice.CloseConnection()
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

CAN_MOVE = args.m
QCONST = args.c

if args.dd != -1:
    if not args.dd is None: log_path=args.dd
    basicConfig(format=debug_format, datefmt="%H:%M:%S",\
        filename=log_path, level=INFO, filemode="w")
elif args.d != -1:
    if not args.d is None: log_path=args.d
    basicConfig(format=debug_format, datefmt="%H:%M:%S", \
        filename=log_path, level=DEBUG, filemode="w")

#register handles keyboard interupts and exceptions
#signal handles tmux kill-ses
info("Registering cleanup.")
register(self.close)
signal(SIGHUP, self.close)

#shm d is state shared memory.
d_shm_name=config.get("Shm_path", "Shm_D")
info("Reading state shared memory.")

#load the indices for the shared memory
str_d={}
for name in config.options("Shm_D_Content"):
    str_d[name]=config.getint("Shm_D_Content", name)

#silence std out for shm creation
_ = io.StringIO()
sys.stdout = _

Shm_D=shm(d_shm_name)

#return std out to normal
sys.stdout=sys.__stdout__

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
    data = [] 
    for name in config.options("Shm_D_Content"):
        data.append(config.getfloat("Shm_D_Init", name))

    _ = io.StringIO()
    sys.stdout = _

    self.Shm_D  = shm(d_shm_name, data = data)
    sys.stdout=sys.__stdout__
    info("State shared memory file created.")

info("No duplicate control scripts, continuing with initialization.")
#shm p is command shared memory, 
self.p_shm_name=self.config.get("Shm_path", "Shm_P")
info("Initializing command shared memory from config file.")
data=np.zeros([np.int(self.config.getfloat("Shm_dim", "Shm_P_dim")), 1])
#here we load indices for the shared memory and populate data
self.str_p = {}
for name in self.config.options("Shm_P_Content"):
    self.str_p[name]=np.int(self.config.getfloat("Shm_P_Content", name))
    data[self.str_p[name],0]=self.config.getfloat("Shm_P_Init", name)

_ = io.StringIO()
sys.stdout = _

self.Shm_P=shm(self.p_shm_name, data=data)

sys.stdout=sys.__stdout__
        
#creating the shm incrememnts the semaphore, so we zero it
self.Shm_P.get_data(check=True)
info("Command shared memory successfully created.")

info("Initializing NPS.")
self.NPS=NPS()

#set up PI device.
self.pidevice=GCSDevice()
#the controller actually has 4 axis but the latter 2 are for calibration,
#etc so should never be touched. Therefore, we limit our axes to 1 and 2.
self.axes=["1", "2"]
if self.NPS.getStatusAll()[NPS_PORT] == True: self.connect_device()
    
info("Starting display drawer")        
#we use popen to start the drawing scrip separately to prevent blocking
display_cmd = "kpython3 TTM_draw"
bash(display_cmd.split(" "))

info("Beginning loop.")
self.loop()

async def manager(self, error:int=0) -> int:
    """A manager to start the asyncio tasks"""

    #We start both methods as tasks, passing the error to update
    task1 = asyncio.create_task(self.update(error))
    task2 = asynvio.create_task(self.listener())

    #We only wait for task 2 to finish because task1 will continuously
    #check but we need to update the error if listener runs.
    return await task2

error = 0
while True: error = asyncio.run(self.manager(error))
