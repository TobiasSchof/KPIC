#inherent python libraries
from configparser import ConfigParser
from time import sleep, gmtime, time
import sys, io

#nfiuserver libraries
from shmlib import shm

"""
A script to continuously maintain a display of shm values in the TTM tmux 
session and log any changes to the state shared memory. Does not run faster
than once per 5 seconds
"""

DATA = os.environ.get("DATA") #the path to the data directory
LOG_FILE = "FIU_TTM.log" #the name of the log file (appended to DATA/YYYMMDD/)


config=ConfigParser()
config.read("TTM.ini")

#all the info we need to connect to a shm is in Shm_Info
Stat_D = config.get("Shm_Info", "Stat_D").split(",")
Stat_D = shm(Stat_D[0], nbSems=int(Stat_D[1]))

Pos_D = config.get("Shm_Info", "Pos_D").split(",")
Pos_D = shm(Pos_D[0], nbSems=int(Pos_D[1]))

Error = config.get("Shm_Info", "Error").split(",")
Error = shm(Error[0], nbSems=int(Error[1]))

Stat_P = config.get("Shm_Info", "Stat_P").split(",")
Stat_P = shm(Stat_P[0], nbSems=int(Stat_P[1]))

Pos_P = config.get("Shm_Info", "Pos_P").split(",")
Pos_P = shm(Pos_P[0], nbSems=int(Pos_P[1]))

Svos = config.get("Shm_Info", "Svos").split(",")
Svos = shm(Svos[0], nbSems=int(Svos[1]))

#for convenience, we lump all shms together
SHMS=[Stat_D, Pos_D, Error, Stat_P, Pos_P, Svos]

async def main():
    """A method that enables asyncio use.

    Waits 5 seconds between iterations.
    """

    #listens for updates on all shared memories
    listeners = [asyncio.create_task(SHM.await_data()) for SHM in SHM]

    done, _ = await asyncio.wait(listeners, return_when=asyncio.FIRST_COMPLETED)

    updates=[]
    if listeners[SHMS.index(Stat_D)] in done: updates.append(1)
    if listeners[SHMS.index(Pos_D)] in done: updates.append(2)
    if listeners[SHMS.index(Error)] in done: updates.append(3)

    update(updates)
    draw()

    sleep(5)

async def draw():
    """Draws a display with shared memory values.

    Inputs:
        dataD = the result of Shm_D.get_data()
        dataP = the result of Shm_P.get_data()
    """

    #need to take data out of numpy array for proper string conversion
    #we store time here too so we get time and position at same isntance
    dpos = [pos for pos in Pos_D.get_data()]
       
    #need to take data out of numpy array for proper string conversion
    ppos = [pos for pos in Pos_P.get_data()]
        
    #translate the state status for user
    dstatus={2:"Device moving", 1:"Script: on | Device: on", \
        0:"Script: on | Device: off"}
    dstatus=dstatus[Stat_D.get_data()[0]]

    #translate the command status for user
    pstatus={True:"Device on", False:"Device off"}
    pstatus=pstatus[Stat_P.get_data()[0]]

    #translate the error for user
    derror={0:"No error", 1:"Move requested beyond limits", 2:"Loop Open"}
    derror=derror[Error.get_data()[0]]

    #translate servo status for user
    servostat = {True:"on", False:"off"}
    servostat = [servostat(svo) for svo in Svos.get_data()]

    #get time from dpos
    update_t = ctime(dpos[-1])

    #remove time from dpos
    dpos = dpos[:-1]

    print("\033c", end="")
    print(u"\u250F""{:<77}"u"\u2513".format(u"\u2501"*77))
    print(u"\u2503""{:^77}"u"\u2503".format("TTM Controller"))
    print(u"\u2523""{0:<38}"u"\u2533""{0:<38}"u"\u252B".format(u"\u2501"*38))
    print(u"\u2503"" {:<37}"*2+u"\u2503".format("Device state:", "Requests:"))
    print(u"\u2503"" {:<37}"*2+u"\u2503".format("", ""))
    print(u"\u2503"" {:<37}"*2+u"\u2503".format("Position: ", "Position:"))
    print(u"\u2503"" {:<37}"*2+u"\u2503".format(str(dpos), str(ppos)))
    print(u"\u2503"" {:<37}"*2+u"\u2503".format("", ""))
    print(u"\u2503"" {:<37}"*2+u"\u2503".format("Time of last update:", "Servo status:"))
    print(u"\u2503"" {:<37}"*2+u"\u2503".format(update_t, str(servostat)))
    print(u"\u2503"" {:<37}"*2+u"\u2503".format("", ""))
    print(u"\u2503"" {:<37}"*2+u"\u2503".format("Status:", "Status:"))
    print(u"\u2503"" {:<37}"*2+u"\u2503".format(dstatus, pstatus))
    print(u"\u2503"" {:<37}"*2+u"\u2503".format("", ""))
    print(u"\u2503"" {:<37}"u*2+"\u2503".format("Error message:", ""))
    print(u"\u2503"" {:<37}"u"*2+\u2503".format(derror, ""))
    print(u"\u2517"+u"\u2501"*38+u"\u253B"+u"\u2501"*38+u"\u251B")

async def update(update:list):
    """Updates the log.

    Inputs:
        update = the list of state shms that have been updated:
            1 = Stat_D
            2 = Pos_D
            3 = Error
    """

    gmt = gmtime(time())
    date="{:04d}/{:02d}/{:02d}".format(gmt.tm_year, gmt.tm_mon, gmt.tm_mday)

    cur_path = "{}{}".format(DATA, date.replace("/", ""))
    #check whether the date of the last state shared memory update has a folder
    if not os.path.isdir(cur_path): os.mkdir(cur_path)

    log_format = "%(message)s"

    #start logger
    logging.basicConfig(format=log_format,\
        filename="{}/{}".format(cur_path, LOG_FILE))
    #logging seems to be fickle and not log if level is set in basicconfig
    #not as the first command in a script, so set the level separately
    logging.root.setLevel(60)
    
    #translate the update list to names and values
    names = {1:"status", 2:"position", 3:"error"}
    vals = {"status":Stat_D.get_data()[0], "error":Error.get_data()[0],\
        "position":[pos for pos in Pos_D.get_data()[:-1]]}

    log_t = "{:02d}:{:02d}:{:02d}".format(gmt.tm_hour, gmt.tm_min, gmt.tm_sec)
    #start log message with date and time
    msg="{:<11}{:<10}update:".format(date, log_t)
    #have next part variable
    msg=msg+"{b:1}{name:>6} = {val}"
    #we will be updating this so make sure we have the global parameter
    for item in update:
        #log a change if there's a new value
        name = names[item]
        val = vals[name]
        logging.log(60, msg.format(b="", name=name, val=val))
        #update msg (this way we don't add date and time after first log)
        msg="{b:<29}{name:<6} = {val}"

#continuously run the asyncio processes
while True: asyncio.run(main())
