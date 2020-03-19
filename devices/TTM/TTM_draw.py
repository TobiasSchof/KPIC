#inherent python libraries
from configparser import ConfigParser
from time import sleepi, gmtime
import sys, io

#nfiuserver libraries
from shmlib import shm

DATA = os.environ.get("DATA") #the path to the data directory
LOG_FILE = "FIU_TTM.log" #the name of the log file (appended to DATA/YYYMMDD/)
#the previous log values (so we know if the new ones need to be logged)
OLD_VALS = {"pos":None, "servos":None, "status":None, "error":None}

config=ConfigParser()
config.read("TTM.ini")

#shm data is a list so we populate a dictionary with which
#information is at what index.
str_d={name:config.getint("Shm_D_Content", name) for name in \
    config.options("Shm_D_Content")}
Shm_D=shm(config.get("Shm_path", "Shm_D"))

#shm p is command shared memory
str_p={name:config.getint("Shm_P_Content", name) for name in \
    config.options("Shm_P_Content")}
Shm_P=shm(config.get("Shm_path", "Shm_P"))

async def main():
    """A method that enables asyncio use.

    Waits 5 seconds between iterations.
    """

    #listens for updates on both shared memories
    listenD = asyncio.create_task(Shm_D.await_data())
    listenP = asyncio.create_task(Shm_P.await_data())

    await asyncio.wait([listenD, listenP], return_when=asyncio.FIRST_COMPLETED)

    dataD=Shm_D.get_data()
    dataP=Shm_P.get_data()

    update(dataD, dataP)
    draw(dataD, dataP)

    sleep(5)

async def draw(dataD, dataP):
    """Draws a display with shared memory values.

    Inputs:
        dataD = the result of Shm_D.get_data()
        dataP = the result of Shm_P.get_data()
    """

    #Note, the script off statuses in state shm will never appear
    dpos=[dataD[str_d["pos_1"]].item(), dataD[str_d["pos_2"]].item()]
       
    ppos=[dataP[str_p["pos_1"]].item(), dataP[str_p["pos_2"]].item()]
        
    dstatus={2:"Device moving", 1:"Script: on | Device: on", \
        0:"Script: on | Device: off"}
    dstatus=dstatus[dataD[str_d["status"]].item()]

    pstatus={1:"Device on", 0:"Device off", -1:"Kill script"}
    pstatus=pstatus[dataP[str_p["status"]].item()]

    derror={0:"No error", 1:"Move requested beyond limits", 2:"Loop Open"}
    derror=derror[dataD[str_d["error"]].item()]

    _ = {1:"on", 0:"off"}
    servostat=[_[dataP[str_p["svo_{}".format(axis)]].item()]\
        for axis in ["1","2"]]

    update_t=ctime(dataD[str_d["cur_t"]].item())

    print("\033c", end="")
    print(u"\u250F""{:<77}"u"\u2513".format(u"\u2501"*77))
    print(u"\u2503""{:^77}"u"\u2503".format("TTM Controller"))
    print(u"\u2523""{:<38}"u"\u2533""{:<38}"u"\u252B".format(u"\u2501"*38, u"\u2501"*38))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format("Device state:", "Requests:"))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format("", ""))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format("Position: ", "Position:"))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format(str(dpos), str(ppos)))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format("", ""))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format("Time of last update:", "Servo status:"))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format(update_t, str(servostat)))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format("", ""))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format("Status:", "Status:"))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format(dstatus, pstatus))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format("", ""))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format("Error message:", ""))
    print(u"\u2503"" {:<37}"u"\u2503"" {:<37}"u"\u2503".format(derror, ""))
    print(u"\u2517"+u"\u2501"*38+u"\u253B"+u"\u2501"*38+u"\u251B")

async def update(dataD, dataP):
    """Updates the log.

    TODO: update KTL keywords (Do I want to do this here or add another 
    listener?)
    Inputs:
        dataD = the result of Shm_D.get_data()
        dataP = the result of Shm_P.get_data()
    """

    gmt = gmtime(dataD[str_d["cur_t"]].item())
    date="{:04d}/{:02d}/{:02d}".format(gmt.tm_year, gmt.tm_mon, gmt.tm_mday)

    cur_path = "{}{}".format(DATA, date.replace("/", ""))
    #check whether the date of the last state shared memory update has a folder
    if not os.path.isdir(cur_path): os.mkdir(cur_path)

    log_format = "%(message)s"

    #start logger
    logging.basicConfig(format=log_format,\
        filename="{}/{}".format(cur_path, LOG_FILE))
    logging.root.setLevel(60)
    
    new_vals={}
    new_vals["pos"] = [dataD[str_d["pos_{}".format(axis)]].item()\
        for axis in [1, 2]] 
    new_vals["servos"] = [dataP[str_p["svo_{}".format(axis)]].item()\
        for axis in [1, 2]]
    new_vals["status"] = dataD[str_d["status"]].item()
    new_vals["error"] = dataD[str_d["error"]].item()

    log_t = "{:02d}:{:02d}:{:02d}".format(gmt.tm_hour, gmt.tm_min, gmt.tm_sec)
    #start log message with date and time
    msg="{:<11}{:<10}update:".format(date, log_t)
    #have next part variable
    msg=msg+"{b:1}{name:>6} = {val}"
    #we will be updating this so make sure we have the global parameter
    global OLD_VALS
    for item in OLD_VALS:
        if OLD_VALS[item] != new_vals[item]:
            #log a change if there's a new value
            logging.log(60, msg.format(b="", name=item, val=new_vals[item]))
            #update msg (this way we don't add date and time after first log)
            msg="{b:<29}{name:<6} = {val}"

    #update the last values in the log
    OLD_VALS=new_vals

    #TODO: add KTL writer dispatch writer (Do I want to do this here?)

#continuously run the asyncio processes
while True: asyncio.run(main())
