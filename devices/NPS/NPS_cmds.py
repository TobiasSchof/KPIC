'''
================================================================================
Library for easy control of the NPS. Based off pulizzi.py by Sylvain Cetre.

Notes:

Dependencies:______________________________________________
  Custom:
  - None     
   
  Native:
  - telnetlib   --
  - sys         --
  - time        --
  - os          --

================================================================================
Author:         Dan Echeverri (dechever@caltech.edu)
Origin Date:    11/21/2018
'''

'''
____Change Log:____

'''

from time import gmtime
from configparser import ConfigParser
import os, sys, telnetlib 

CONFILE = 'NPS.ini' 

def ConnectionError(Exception):
    """A connection to be thrown on connection error"""
    pass

class NPS_cmds(object):
    '''--------------------------------------------------------------
    Class for controlling the pulizzi NPS.
    
    * NOTE: This class is currently only setup up to handle 
        IPC34XX type controllers.
    * Does not currently throw any errors
    -------------------------------------------------------------- '''
    TIMEOUT = 3.0

    # =========================================================================
    def __init__(self, conf=CONFILE):
        ''' -------------------------------------------------------------------
        ------------------------------------------------------------------- '''
        self.conf = conf
        # Populate class variables with values from conf file
        self.readConf()
        self.verbose = False

    # =========================================================================
    def readConf(self):
        ''' -------------------------------------------------------------------
        Reads the config file specifed in constructor
        ------------------------------------------------------------------- '''
        
        config = ConfigParser()
        ret = config.read(self.conf)

        #check to make sure config file was read correclty
        if self.conf not in ret: raise Exception("Could not find config file")

        model = config.get("Device_Info", "model").strip()
        if model == "IPC34XX":
            # These are not currently used but are left here to make it
            # easier to implement IPC32 vs 34 control
            self.StatusFnc   = 'IPC34XX_Status'
            self.PowerOnFnc  = 'IPC34XX_On'
            self.PowerOffFnc = 'IPC34XX_Off'
        elif model == "IPC32XX":
            # This library is not meant to be used with this model
            msg = "This library is currently not set up to handle IPC32XX" +\
                " controllers."
            raise Exception(msg)
        else:
            msg = "Invalid pulizzi model: {}".format(model)
            raise Exception(msg)

        # load communication info
        self.address = config.get("Communication", "address")
        self.port = config.get("Communication", "port")
        
        #load devices
        self.devices={}
        for port in config.options("Ports"):
            self.devices[port] = self.config.get("Ports", port)

    # =========================================================================
    def __startConnection(self):
        """Opens the connection to the NPS. DO NOT USE EXTERNALLY"""
        
        # Start telnet connection
        try: telnet = telnetlib.Telnet(self.address, self.port)
        except: raise ConnectionError("Controller connection failed.")

        # Wait 0.5 second
        time.sleep(0.5)

        # Establish comms
        telnet.write(("@@@@\r\n").encode('ascii'))
        res = telnet.expect([bytes("IPC ONLINE!", 'utf-8')], self.TIMEOUT)

        if(res[0] == -1):
            #Timed out
            telnet.close()
            raise ConnectionError("Connection timeout on startup.")
        # Wait 0.5 second
        time.sleep(0.5)

    # =========================================================================
    def __closeConnection(self):
        """Closes the connection to the NPS"""

        # send logout command
        telnet.write(("LO\r\n").encode('ascii'))
        res = telnet.expect([bytes("LOGGED-OUT!", 'utf-8')], self.TIMEOUT)

        #timed out
        if(res[0] == -1):
            telnet.close()
            raise ConnectionError("Connection timeout on logout.")

        telnet.close()

    # =========================================================================
    def getStatusAll(self) -> dict:
        ''' -------------------------------------------------------------------
        Returns the status of all the outlets on the Pulizzi

        Returns:
            dict of boolean values and integer keys keys = port, value = if on

        NOTE: 
            if timeout occurs while reading an outlet, that port won't be in
            the dictionary.
        ------------------------------------------------------------------- '''
        
        # Open connection to the NPS
        self.__startConnection()

        # Query all outlets (device does not have an easy way to query single)
        telnet.write(("DX0\r\n").encode('ascii'))

        devstat = {}
        for i in self.devices:
            tmp_1 = "OUTLET {} ON".format(i)
            tmp_2 = "OUTLET {} OFF".format(i)
            fmt   = 'utf-8' 
            res = telnet.expect([bytes(tmp_1,fmt), bytes(tmp_2,fmt)], self.TIMEOUT)
            
            # outlet is on
            if res[0] == 0 : devstat[i] = True
            # outlet is off (-1 is a timeout)
            elif res[0] != -1: devstat[i] = False
            
        # Close connection to the NPS
        self.__closeConnection()
            
        return devstat

    # =========================================================================
    def turnOn(self, outlets):
        '''Sets the provided outlets to ON
       
        Arguments:        
            outlets (list of ints) 
                      List indicating which outlets to activate.
                      Values should be between 1 and 8
                *** NOTE: 'outlets' can also be a single integer

        Returns:
            dict of booleans reporting if outlet was succesfully changed
                 True if change was successful, False if timeout occurred
        
        Example:
            turnOn(5) 
                This will turn on only outelt 5
            turnOn([2,5,8])
                This will turn on outlets 2, 5, and 8
        '''
        # Start telnet connection
        self.__startConnection()
     
        # Cast outlets to a list since it is likely a single integer
        if not type(outlets) is list: outlets = [outlets]
         
        # check that the outlet is valid
        for i in outlets:
            try: self.devices[int(i)]
            except (KeyError, ValueError):
                self.__closeConnection()
                msg = "Invalid port {}".format("i")
                raise ValueError(msg)

        devstat = {}
        for i in outlets:
            telnet.write("N0{}\r\n".format(i).encode('ascii'))
            res = telnet.expect([bytes("DONE", 'utf-8')], self.TIMEOUT)

            # -1 corresponds to a timeout
            if res[0] == -1: devstat[i] = False
            else: devstat[i] = True

        # Close connection to the NPS
        self.__closeConnection()

        return devstat

    # =========================================================================
    def turnOff(self, outlets):
        '''Sets the provided outlets to OFF
       
        Arguments:        
            outlets (list of ints) 
                      List indicating which outlets to deactivate.
                      Values should be between 1 and 8
                *** NOTE: 'outlets' can also be a single integer

        Returns:
            list of booleans reporting if outlet was succesfully changed
                 True if change was successful, False if timeout occurred
        
        Example:
            turnOff(5) 
                This will turn off only outelt 5
            turnOff([2,5,8])
                This will turn off outlets 2, 5, and 8
        '''

        # Start telnet connection
        self.__startConnection()
     
        # Cast outlets to a list since it is likely a single integer
        if not type(outlets) is list: outlets = [outlets]

        # check that the outlet is valid
        for i in outlets:
            try: self.devices[int(i)]
            except (KeyError, ValueError):
                self.__closeConnection()
                msg = "Invalid port {}".format("i")
                raise ValueError(msg)

        devstat = {}
        for i in outlets:
            telnet.write("F0{}\r\n".format(i).encode('ascii'))
            res = telnet.expect([bytes("DONE", 'utf-8')], self.TIMEOUT)

            # -1 corresponds to a timeout
            if(res[0] == -1): devstat[i] = False 
            else: devstat[i] = True

        # Close connection to the NPS
        self.__closeConnection()

        return devstat

    # =========================================================================
    def status(self,):
        ''' -------------------------------------------------------------------
        Description:
            This function print the status of each port of the NPS.
        Returns:
            - None 
        ------------------------------------------------------------------- '''
        try:
            # Get the status of all the ports
            tmp = self.getStatusAll()
            
            # Print all parameters
            print('##################################################')
            print('Status of each port of the FIU NPS:')
            for i in np.arange(8):
                
                # Prepare information to print
                j = i+1
                s = 'On' if tmp[i] else 'Off'
                d = self.devices[i].ljust(15)
                # Print information
                print('- Port #%d - Device = ' %j + d + ' - Status: ' + s )
            print('##################################################')
            
            # Does not return anything
            return
        except:
            print('\033[91mERROR: Something wrong happened.\033[0m')
            # Does not return anything
            return

