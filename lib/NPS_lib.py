#
# THIS IS AN EMPTY PYTHON LIBRARY TO MIMIC THE NPS WITHOUT FUNCTIONALITY
#

import sys, io

from sce_shmlib import shm

class NPS():

    def __init__(self):
        
        #We use devices so we create a devices parameter

        self.devices=["FIU TTM", "FIU TCP"]
        self.status=[True, True]

    def getStatusAll(self):
        #We use this method, just have it say everything is on

        return self.status

    def turnOn(self, idx:int):
        #this will do nothing

        self.status[idx]=True

    def turnOff(self, idx:int):
        #this will do nothing

        self.status[idx]=False
