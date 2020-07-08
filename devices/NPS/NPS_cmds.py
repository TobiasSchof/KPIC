# inherent python libraries
from configparser import ConfigParser
import os

# nfiuserver libraries
from KPIC_shmlib import Shm

def activate_Control_Script():
    """Activates the NPS control script"""

    RELDIR = os.environ.get("RELDIR")
    if RELDIR = "": raise Exception("$RELDIR not found")
    if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

class NPS_cmds:
    """Class for controlling the pulizzi NPS through shared memory"""

    def __init__(self):
        """Constructor for NPS_cmds class"""

        config = ConfigParser()
        config.read("")
