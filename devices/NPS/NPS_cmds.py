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

#TODO::: @Dan -  talk to sylvain about moving conf file into [..]/dev/config

import os
import sys
import telnetlib
import time
import numpy as np

CONFILE = '/home/nfiudev/bin/pulizzi.cfg' 

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
        self.devices = list()
        # Populate class variables with values from conf file
        self.readConf()
        self.verbose = False

    # =========================================================================
    def readConf(self):
        ''' -------------------------------------------------------------------
        ------------------------------------------------------------------- '''
        # Try to open the config file
        try:
            File = open(self.conf, "r")
        except:
            print("Failed to open configuration file: " + self.conf)
            return
        # Extract information from the configuration file
        Lines = File.readlines()
        # Close the config file
        File.close()
        # Create an index
        index = 0
        # Populate thelist of deviced connected to the NPS based on information
        # contains in the config file 
        while(index < len(Lines)):
            line = Lines[index].strip()
            if(line.startswith("#") or line == ""):
                index = index + 1
                continue
            if(line == "<TAB>"):
                index = index + 1
                self.name = Lines[index].strip()
                index = index + 1
                if(Lines[index].strip() == "IPC32XX"):
                    print('ERROR::: Invalid controller type')
                    print('  This library is currently not set up to handle IPC32XX controllers.')
                    print('  Check your provided conf file: %s'%self.conf)
                    return
                    #StatusFnc   = 'IPC32XX_Status'
                    #PowerOnFnc  = 'IPC32XX_On'
                    #PowerOffFnc = 'IPC32XX_Off'
                elif(Lines[index].strip() == "IPC34XX"):
                    # These are not currently used but are left here to make it
                    # easier to implement IPC32 vs 34 control
                    StatusFnc   = 'IPC34XX_Status'
                    PowerOnFnc  = 'IPC34XX_On'
                    PowerOffFnc = 'IPC34XX_Off'
                else:
                    print('ERROR::: Unrecognized Pulizzi Model:')
                    #print("Unrecognized Pulizzi Model: " + Lines[index].strip())
                    print('  Conf file: %s'%self.conf)
                    print('  Model: %s'%(Lines[index].strip()))
                    return
                index = index + 1
                sp = Lines[index].strip().split()
                self.address = sp[0]
                self.port    = sp[1]
                index = index + 1
                while(index < len(Lines) and Lines[index].strip() != "<TAB>"):
                    if(Lines[index].strip() == ""):
                        index = index + 1
                        continue
                    self.devices.append(Lines[index].strip())
                    index = index + 1
                    # This would be the index for enable/disable
                    index = index + 1
                    # This would be the index for the description
                    index = index + 1
                #Finished reading first tab so exit
                break

    # =========================================================================
    def getStatusAll(self):
        ''' -------------------------------------------------------------------
        Returns the status of all the outlets on the Pulizzi

        Returns:
            list of booleans with one boolean for every names outlet 

        NOTE: 
            if timeout occurs while reading an outlet, that value will be None
            As such, it might be a good idea to check against False explicitly
        ------------------------------------------------------------------- '''
        # Start telnet connection
        try:
            telnet = telnetlib.Telnet(self.address, self.port)
        except:
            print("%s - Connection to controller failed. Try again."%self.name)
            return
        # Wait 0.5 second
        time.sleep(0.5)

        # Establish comms
        telnet.write(("@@@@\r\n").encode('ascii'))
        res = telnet.expect([bytes("IPC ONLINE!", 'utf-8')], self.TIMEOUT)

        if(res[0] == -1):
            #Timed out
            telnet.close()
            print('%s - Timed out while attempting to establish connection.'%self.name)
            return
        # Wait 0.5 second
        time.sleep(0.5)

        # Query all outlets (device does not have an easy way to query single)
        telnet.write(("DX0\r\n").encode('ascii'))

        # Initialize list for outlet status
        devstat = [None]*len(self.devices)  
        for i in range(len(self.devices)):
            tmp_1 = "OUTLET " + str(i+1) + " ON"
            tmp_2 = "OUTLET " + str(i+1) + " OFF"
            fmt   = 'utf-8' 
            res = telnet.expect([bytes(tmp_1,fmt), bytes(tmp_2,fmt)], self.TIMEOUT)
            
            if(res[0] == -1):
                msg = " - Outlet " + str(i+1) + " timed out while waiting for status."
                #Timed out
                print(self.name + msg)
            elif(res[0] == 0):
                #Outlet is on
                devstat[i] = True
            else:
                #Outlet is off
                devstat[i] = False
            
        telnet.write(("LO\r\n").encode('ascii'))
        res = telnet.expect([bytes("LOGGED-OUT!", 'utf-8')], self.TIMEOUT)

        if(res[0] == -1):
            #Timed out
            print(self.name + " - Timed out when attempting to logout of pulizzi.")

        telnet.close()
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
            list of booleans reporting if outlet was succesfully changed
                 True if change was successful, False if timeout occurred
        
        Example:
            turnOn(5) 
                This will turn on only outelt 5
            turnOn([2,5,8])
                This will turn on outlets 2, 5, and 8
        '''
        # Start telnet connection
        try:
            telnet = telnetlib.Telnet(self.address, self.port)
        except:
            print("%s - Connection to controller failed. Try again."%self.name)
            return

        time.sleep(0.5)

        # Establish comms
        telnet.write(("@@@@\r\n").encode('ascii'))
        res = telnet.expect([bytes("IPC ONLINE!", 'utf-8')], self.TIMEOUT)

        if(res[0] == -1):
            #Timed out
            telnet.close()
            print('%s - Timed out while attempting to establish connection.'%self.name)
            return

        time.sleep(0.5)
     
        if not isinstance(outlets, list):
            # Cast outlets to a list since it is likely a single integer
            outlets = [outlets]
         
        devstat = [None]*len(outlets)  # initialize list for outlet statuses
        for i in range(len(outlets)):
            telnet.write(("N0" + str(outlets[i]) + "\r\n").encode('ascii'))
            res = telnet.expect([bytes("DONE", 'utf-8')], self.TIMEOUT)

            if(res[0] == -1):
                #Timed out
                #telnet.close()
                print('%s - Outlet %d timed out while attempting to ON'%(self.name,outlets[i]))
                devstat[i] = False 
                #return
            else:
                #print('%s - Outlet %d successfully turned ON.'%(self.name, outlets[i]))
                devstat[i] = True

        telnet.write(("LO\r\n").encode('ascii'))
        res = telnet.expect([bytes("LOGGED-OUT!", 'utf-8')], self.TIMEOUT)

        if(res[0] == -1):
            #Timed out
            print(self.name + " - Timed out when attempting to logout of pulizzi.")

        telnet.close()
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
        try:
            telnet = telnetlib.Telnet(self.address, self.port)
        except:
            print("%s - Connection to controller failed. Try again."%self.name)
            return

        time.sleep(0.5)

        # Establish comms
        telnet.write(("@@@@\r\n").encode('ascii'))
        res = telnet.expect([bytes("IPC ONLINE!", 'utf-8')], self.TIMEOUT)

        if(res[0] == -1):
            #Timed out
            telnet.close()
            print('%s - Timed out while attempting to establish connection.'%self.name)
            return

        time.sleep(0.5)
     
        if not isinstance(outlets, list):
            # Cast outlets to a list since it is likely a single integer
            outlets = [outlets]
         
        devstat = [None]*len(outlets)  # initialize list for outlet statuses
        for i in range(len(outlets)):
            telnet.write(("F0" + str(outlets[i]) + "\r\n").encode('ascii'))
            res = telnet.expect([bytes("DONE", 'utf-8')], self.TIMEOUT)

            if(res[0] == -1):
                #Timed out
                #telnet.close()
                print('%s - Outlet %d timed out while attempting to OFF'%(self.name,outlets[i]))
                devstat[i] = False 
                #return
            else:
                #print('%s - Outlet %d successfully turned OFF.'%(self.name, outlets[i]))
                devstat[i] = True

        telnet.write(("LO\r\n").encode('ascii'))
        res = telnet.expect([bytes("LOGGED-OUT!", 'utf-8')], self.TIMEOUT)

        if(res[0] == -1):
            #Timed out
            print(self.name + " - Timed out when attempting to logout of pulizzi.")

        telnet.close()
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

if __name__ == "__main__":
    main()

