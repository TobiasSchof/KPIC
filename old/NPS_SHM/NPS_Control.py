from subprocess import Popen as bash
from configparser import ConfigParser
from atexit import register
from signal import SIGHUP, signal
from time import sleep
import numpy as np
import os, sys, io
import telnetlib, asyncio

from sceshm_lib import shm

#
#Script to control the network power switch. Not for general use.
#
if __name__ != "__main__": sys.exit()

TIMEOUT   = 3.0 #time to wait before declaring a timeout (in s)
CONF_PATH = os.environ.get("CONFIG") #location of config files

#register handles exceptions and ctrl-c, SIGHUP handles tmux kill-ses
#close will update Shm_D, destroy Shm_P, logout of and close telnet
register(close)
signal(SIGHUP, close)

class TelnetError(Exception)
    """An exception to be raised when there's an issue with the NPS"""

    pass

def connect():
    """Connects to telnet.

    Will keep trying if initial attempt fails
    """

    res = [-1]
    count = 0
    while res[0] == -1:
        print("\033cOpening communication{:<4}".format("."*count), end ="\r")
        #connect to NPS
        telnet = telnetlib.Telnet(ADDRESS, PORT)
        sleep(.5)
        #establish communication
        telnet.write(("@@@@\r\n").encode("ascii"))
        res = telnet.expect([bytes("IPC ONLINE!", "utf-8")], TIMEOUT)
        count = (count + 1)%4

def getStatusAll() -> dict:
    """Gets the status of all ports.

    Outputs:
        dict = keys are ports, values are booleans (whether port is on).
    """

    #query outlets
    telnet.write(("DX0\r\n").encode("ascii"))
    #get the full list of ports
    res = telnet.expect([bytes("J8", "utf-8")], TIMEOUT)
    #flush the buffer
    telnet.read_eager()

    #if response timed out, try reconnecting to device
    if res[0] = -1: 
        connect()
        telnet.write(("DX0\r\n").encode("ascii"))
        res = telnet.expect([bytes("J8", "utf-8")], TIMEOUT)
        telnet.read_eager()
        #if response times out again, raise error
        if res[0] = -1: raise TelnetError("No J8 in response")
    
    #the dictionary to be returned
    ret = {}

    #get the NPS response as a string
    info = res[2].decode("ascii")
    idx = 0
    #response is of the form OUTLET n ON/OFF
    while idx > -1:
        idx = info.find("OUTLET", idx)
        #this will set the key to port value and value to whether the second
        #letter in ON/OFF is "N" (i.e. whether the port is on)
        ret[int(info[idx+7])] = (info[idx+10] == "N")
        idx += 10

    return ret

def send(vals:dict):
    """Send on or off messages for given ports if value is different than
    current state

    Inputs:
        vals = keys are port, values are status (1 = on 0 = off)
    """

    dev_stat=getStatusAll()

    #format message for any ports that should be turned on
    ons = ["N{:02d}\r\n".format(port) for port in vals\
         if vals[port] != dev_stat[port] and vals[port]==1]
    #format message for any ports that should be turned off  
    offs = ["F{:02d}\r\n".format(port) for port in vals\
         if vals[port] != dev_stat[port] and vals[port]==0]

    #send on messages
    for msg in ons: telnet.write(msg.encode("ascii"))

    #give devices time to do shutdown procedures before sending off messages
    sleep(1)
    for msg in offs: telnet.write(msg.encode("ascii"))

def startListening(ports):
    """Appends the devices registered at ports to the listening list and checks
    to make sure device is at requested state
    
    Will ignore any device not in devs

    Inputs:
        ports = the port (int) or ports ([int]) that should start listening
    """

    added={}

    #cast ports to a list if it's an int
    if type(ports) is int: ports = [ports]

    dev_stat = getStatusAll()
    for port in ports:
        try: 
            listening[port] = [shm(devs[port][0]),\
                lambda: int(listening[port][1].get_data()[devs[port][1]])
            added[port] = listening[port][1]()
        #if port isn't in devs, go to next device
        except KeyError: continue

    if len(added) > 0: send(added)

def stopListening(ports):
    """Removes the devices registered at ports to the listening list and turns
    them off.

    Will ignore any device not in devs
    
    This method enables device control scripts to turn off the device when they
    die by setting the NPS command memory status to 0

    Inputs:
        ports = the port (int) or ports ([int]) that should stop listening
    """

    removed = {}

    #cast ports to a list if it's an int
    if type(ports) is int: ports = [ports]

    for port in ports: 
        try: listening.pop(port)
        except KeyError: continue
        #turn off the port if it's currently on
        removed[port] = 0

    if len(removed) > 0: send(removed)

def close()
    """Cleans up on close"""

    #if Shm_P isn't initialized, it means that the constructor didn't finish
    if Shm_P is None: sys.exit()
    
    #remove P shared memory
    os.remove(config.get("Shm_path", "Shm_P"))

    #update D shared memory
    stat = getStatusAll()
    data = [dev for dev in stat]
    Shm_D.set_data(np.array(data, np.bool, ndmin=2))

    #close telnet connection
    if not telnet is None:
        telnet.write(("LO\r\n").encode("ascii")
        telnet.close()
    
    #close tmux session
    bash("tmux kill-ses -t NPS".split(" "))

async def listen(port:int):
    """An awaitable method that handle's a single device.

    listens for changes in the device's shared memory and turns off/on the
    device as necessary. Also updates NPS shm_d and redraws NPS display

    Inputs:
        port = the port to listen to
    """

    while True:
        
        old_data = int(listening[port][1]())
        data = old_data
        #keep awaiting until the status has changed
        while old_data == data or data not in [1, 0, -1, -2]: 
            old_data = data
            data = int(await listening[port][0].await_data()[devs[port][1]])

        #if data is 1 or -1, it means the device should be on        
        send({port:int(data in [1, -1])})

        check = data in [1, -1]
        #wait for NPS to react correctly
        while getStatusAll()[port] != check: sleep(.01)
        
        #update shm_d
        dev_stat = getStatusAll()
        data = [dev_stat[port] for port in shm_idx]
        Shm_D.set_data(np.array(data), np.bool, ndmin=2)

        #draw display
        draw()

def draw():
    """Draws the interface for the Network Power Switch"""

    def P(port:int) -> str:
        """Returns the message to be shown for Shm_D for given port

        Inputs:
            port = the port to display message for
        Outputs:
            str = the message to be displayed
        """

        #if we were unable to load config, display such
        if port not in devs: return "Could not load config file."

        #otherwise, check if we're listening to that port
        if port not in listening: return "Not listening."
            
        #otherwise return status
        return "Listening. Status is: {}".format(listening[port][1]())

    D = Shm_D.get_data()
    trans = {True:"On", False="Off"}
    D = {port:trans[D[shm_idx[port]]] for port in shm_idx}

    print("\033c", end="")
    print(u"\u250F""{:<77}"u"\u2513".format(u"\u2501"*77))
    print(u"\u2503""{:^77}"u"\u2503".format("NPS Controller"))
    print(u"\u2523""{:<38}"u"\u2533""{:<38}"u"\u252B".format(u"\u2501"*38, u"\u2501"*38))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format("Device state:", "Listening status:"))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format("", ""))
    dev_name = lambda port: config.get("Names", port)
    for port in shm_idx:
        print(u"\u2503"" {0:<37}".format(devs(port))*2+u"\u2503")
        print((u"\u2503"" {:<37}"*2).format(D[port], P(port))+u"\u2503")
        print(u"\u2503"" {:<37}"*2+u"\u2503".format("", ""))
    print(u"\u2517"+u"\u2501"*38+u"\u253B"+u"\u2501"*38+u"\u251B")


async def loop():
    #start listening to device shared memories
    devs={port:asyncio.create_task(listen(port)) for port in listening}

    #start listening to NPS shared memory
    nps_shm = await asyncio.create_task(Shm_P.await_data())

    for port in shm_idx:
        #stop listening if currently listening and shm_p value is 0
        if port in listening and nps_shm[port] == 0: stopListening(port)
        #start listening if currently not listening and shm_p value is 1
        elif port not in listening and nps_shm[port] == 1: startListening(port)

    #wait for NPS to do what it needs to
    sleep(.5)

    #update shm_d
    dev_stat = getStatusAll()
    data = [dev_stat[port] for port in shm_idx]
    Shm_D.set_data(np.array(data), np.bool, ndmin=2)

    draw()
    

config=ConfigParser()
config.read(CONF_PATH+"NPS.ini")

#Check whether there is already an NPS script running
if not os.path.isfile(config.get("Shm_path", "Shm_P"):
    raise AlreadyAlive("NPS control script already alive (shm_p exists)")

#Get address and port for NPS
ADDRESS = config.get("Device_info", "address")
PORT    = config.get("Device_info", "port")

#Populate dict with port number keys and device name values
devs = {config.getint("Ports", name):name for name in config.options("Ports")}

#Get shm info for each of the devices
for port in devs:
    #create a config parser to parse device configs for shm info
    dev_conf=ConfigParser()
    _ = dev_conf.read(CONF_PATH+devs[port]+".ini")
    #if _ is empty, it means the config file wasn't found
    if _ = []: dev = devs.pop(port)
    else:
        shm_path = dev_conf.get("Shm_path", "Shm_P")
        shm_idx = dev_conf.getint("Shm_P_Content", "status")
        #change devs dict so keys are the NPS port of the device, and values
        #are the location of the device's Shm_P and index of status in Shm_P
        devs[port] = [shm_path, shm_idx]
        
#connect port with Shm index
shm_idx={config.getint("Ports", name):config.getint("Shm_indices", name) for\
    name in config.options("Ports")}
        
#set up shm_d with current status of devices.
dev_stat = getStatusAll()
#make a list with the current status of all the devices
data = [dev_stat(port) for port in shm_idx]
Shm_D = shm(config.get("Shm_path", "Shm_D"), np.array(data, np.bool, ndmin=2))

#open communication with NPS
connect()

#find which devices have active command shared memories
listening = {} #which shared memories to listen to
for port in devs: if os.path.isfile(devs[port][0]): startListening(port)

#populate shm_p with -1
data = [-1]*config.getint("Shm_dim", "Shm_P_dim")
#change any devices with good configs to 0
for port in devs: shm_p_data[shm_idx[port]] = 0
#change any devices with active command shared memory to 1
for port in listening: shm_p_data[shm_idx[port]] = 1
Shm_P = shm(config.get("Shm_path", "Shm_P"), np.array(data, np.int8, ndmin=2))

#start asyncio loop
while True: asyncio.run(loop)

