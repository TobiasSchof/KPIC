from configparser import ConfigParser
from time import sleepi, gmtime
import sys, io

from sce_shmlib import shm

DATA = os.environ.get("DATA") #the path to the data directory
LOG_FILE = "FIU_TTM.log" #the name of the log file (appended to DATA/YYYMMDD/)
#the values to write into the log if they change
OLD_VALS = {"pos":None, "servos":None, "status":None, "error":None}

config=ConfigParser()
config.read("TTM.ini")

#shared memory creation is noisy so we silence it
_ = io.StringIO()
sys.stdout = _

#shm data is a list so we populate a dictionary with which
#information is at what index.
str_d={}
for name in config.options("Shm_D_Content"):
    str_d[name]=np.int(config.getfloat("Shm_D_Content", name))

Shm_D=shm(config.get("Shm_path", "Shm_D"))

#shm p is command shared memory

str_p={}
for name in config.options("Shm_P_Content"):
    str_p[name]=np.int(config.getfloat("Shm_P_Content", name))

Shm_P=shm(config.get("Shm_path", "Shm_P"))

sys.stdout = sys.__stdout__

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

    #Note, the script off statuses in state shm will never appear so we don't deal with them.
    dpos=[dataD[str_d["pos_1"]].item(), dataD[str_d["pos_2"]].item()]
       
    ppos=[dataP[str_p["pos_1"]].item(), dataP[str_p["pos_2"]].item()]
        
    dstatus={2:"Device moving", 1:"Script: on | Device: on", 0:"Script: on | Device: off"}
    dstatus=dstatus[dataD[str_d["status"]].item()]

    pstatus={1:"Device on", 0:"Device off", -1:"Kill script"}
    pstatus=pstatus[dataP[str_p["status"]].item()]

    derror={0:"No error", 1:"Move requested beyond limits", \
                2:"Loop Open"}
    derror=derror[dataD[str_d["error"]].item()]

    servostat="on" if dataP[str_p["svos"]]==1 else "off"

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
    if not os.path.isdir(cur_path): 
        os.mkdir(cur_path)

    log_format = "%(message)s"

    #start logger
    logging.basicConfig(format=log_format,\
        filename="{}/{}".format(cur_path, LOG_PATH), level=60)
    
    new_vals={}
    new_vals["pos"]=[dataD[str_d["pos_{}".format(axis)]].item()\
        for axis in [1, 2]] 
    new_vals["servos"] = [dataP[str_p["svo_{}".format(axis)]].item()\
        for axis in [1, 2]]
    new_vals["status"] = dataD[str_d["status"]].item()
    new_vals["error"] = dataD[str_d["error"]].item()

    log_t = "{:02d}:{:02d}:{:02d}".format(gmt.tm_hour, gmt.tm_min, gmt.tm_sec)
    msg="{:<11}{:<10}update:".format(date, log_t)
    msg=msg+"{b:1}{name:>6} = {val}"
    for item in OLD_VALS:
        if OLD_VALS[item] != new_vals[item]:
            #log a change if there's a new value
            logging.log(60, msg.format(b="", name=item, val=new_vals[item])
            #update msg (this way we change after the first
            msg="{b:<29}{name:<6} = {val}"

    #update the last values in the log
    OLD_VALS=new_vals

    #TODO: add KTL writer dispatch writer (Do I want to do this here?)

#continuously run the asyncio processes
while True: asyncio.run(main())
