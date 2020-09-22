from time import sleep
from logging import debug
import telnetlib, serial

#Should Modify:
#Add method to class change serial timeout
#Implement error checking at end of each write (TE)

class TimeoutError(Exception):
    """An error to be thrown for movement timeout"""
    pass

class Conex_Device:
    '''Class for controlling the Newport Conex Stages
    
    Currently handles:
        - CONEX-AG-LS25
        - CONEX-AG-M100D
    '''

    DELAY       = .05       #Number of seconds to wait after writing a message
    MVTIMEOUT   = 600       #(MVTIMEOUTxDELAY)= number of seconds device will 
                                #wait before declaring a move timeout error
    
    def __init__(self):
        '''Constructor for Conex device'''

        # a variable to keep track of what kind of connection is open
        self.con_type = None
        
        #Other Instance Variables
        self.SN     = 'DevNotOpenedYet'     #Device serial number
                #self.SN also serves as flag to check if device has been opened
        self.TY     = 'DevNotOpenedYet'     #Device type
        self.FW     = 'DevNotOpenedYet'     #Device Revision Information
        self.lims   = {}                    #Device limits

    #:::::::::::::::::::::::PORT MANAGEMENT FUNCTIONS::::::::::::::::::::::::::                
    def open_Serial(self, devnm:str, baud:int):
        """Opens a serial connection to the device

        Also queries the device to obtain basic information to confirm communication

        Does not reopen the device if already open

        Args:
            devnm = the device name to connect to
            baud = the baudrate to connect at
        """

        # if port is already open, return
        if not self.con_type is None:
            debug("(SN:{}) is already open".format(self.SN))
            return

        debug("Connecting to serial: {}:{}...".format(devnm, baud))
        self.con = serial.Serial()
        self.con.timeout = 3
        self.con.port = devnm
        self.con.baudrate = baud
        self.con.open()
        self.con_type = "serial"

        self.reqInfo()

        if self.TY.find("M100DD") != -1:
            self.axes = {1:"V", 2:"U"}
        elif self.TY.find("LS25") != -1:
            self.axes = {1:""}
        elif self.TY.find("PR100P") != -1:
            self.axes = {1:""}
        else:
            raise Exception("Controller type not recognized: {}".format(self.TY))

        debug('Device is a   : %s \n'   %self.TY +
              'Serial Number : %s \n'   %self.SN +
              'Frameware vs. : %s \n'   %self.FW)
        
        self.reqLim()

    def open_Telnet(self, host:str, port:int):
        '''Opens a telnet connection to device
        Also queries the device to obtain basic information
            This serves to confirm communication
        *Does not reopen device if already open

        Args:
            host = the hostname of the telnet connection
            port = the port to connect to
        '''
        #Open port if not already open
        if not self.con_type is None:
            debug('(SN:%s) is already open' %self.SN)
        else:
            debug('Connecting to telnet: {}:{}...'.format(host, port))
            self.con = telnetlib.Telnet()
            self.con.open(host, port, 3)
            self.con_type = "telnet"
            
            #Send 'ID?' command to synchronize comms with device:
                #The first message sent after the device is powered up is 
                #automatically ignored by the device. I did not want to send
                #'1RS' since this would reset the device everytime open() is called
            self.write('1ID?')
            self.readAll()  #clear read buffer
            
            #Request Device Information
            self.reqInfo()
        
            if self.TY.find("M100D") != -1:
                self.axes = {1:"V", 2:"U"}
            elif self.TY.find("LS25") != -1:
                self.axes = {1:""}
            elif self.TY.find("PR100P") != -1:
                self.axes = {1:""}
            else:
                raise Exception("Controller type not "+\
                                "recognized: {}".format(self.TY))

            debug('Device is a   : %s \n'   %self.TY +
                  'Serial Number : %s \n'   %self.SN +
                  'Frameware vs. : %s \n'   %self.FW )

            self.reqLim()
              
    def close(self):
        '''Closes the device connection'''
        if self.con_type is None:
            debug("Device is already closed")
        else:
            self.con.close()
            self.con_type = None
    
    #:::::::::::::::::::::::WRITE/READ FUNCTIONS:::::::::::::::::::::::::::::::    
    def write(self, MSG, append = None):
        '''Formats a string, 'MSG' and sends it to the device
        MSG should be the message as string (ex. '1ID?')
            Should NOT include CR\LF
        Can append data (including numbers) to the end of the MSG
        *Data requests using 'write' should be followed by a read
            Otherwise unread items in buffer may cause problems
        **This function is useful for sending messages that do not
            have a dedicated function yet.
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return
            
        #convert 'append' and append to end
        if append != None:
            MSG = MSG + str(append)
            
        MSG = MSG + '\r\n'
        msg = MSG.encode()
            
        #Send message using telnet
        self.con.write(msg)
        
    def readAll(self):
        '''Returns the full read buffer or the first 50 lines
        Also serves as a 'flush' function to clear buffer itself
            Useful for debugging reads to ensure read data is as expected
        Returns the read data as bytes in bytearray
            Does NOT strip() CR\LF at end of messages
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return

        cnt  = 0
        resl = []
        res = self.read(tmt=.25)
        resl.append(res)
        while len(res) > 0 and cnt < 50:
            res = self.read(tmt=.25)
            resl.append(res)
            cnt += 1
            sleep(.05)
        if len(resl[-1]) == 0:
            resl.pop()
        return resl
        
    def read(self, tmt=1.0):
        '''Reads a single line from the readbuffer
        Strips the CR\LF and decodes it into a string

        Inputs:
            tmt = timeout in seconds
        Returns:
            str = result of single-line read
        '''
        #Does not check if port is open to avoid slow-downs from checking
            #if port is open repeatedly when back-to-back reads are performed 
        if self.con_type == "telnet":
            return self.con.read_until(bytes('\r\n', 'utf-8'), tmt).strip().decode('utf-8')
        elif self.con_type == "serial":
            self.con.timeout = tmt
            return self.con.readline().strip().decode("utf-8")

    
    #:::::::::::::::::::::::STATE CHANGE FUNCTIONS:::::::::::::::::::::::::::::
    def home(self, isBlocking = False):
        '''Homes the device
        
        calls reset() first when called in isReady() or isMoving() state

        Inputs:
            isBlocking = True will block execution until homing completes
        Returns:
            -1 if no communication is open
            or
            str = the error code if an error occurred
            or
            None if there's no error
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
            
        #Reset device to allow home() if needed
        if self.isReady() or self.isMoving(): self.reset()
            
        self.write('1OR')   #execute home search
        
        #Check for errors
        erFlg, erCd = self.isError()
        if erFlg:
            debug('DEV ERROR::: Device returned error:\n' +
                  '  ' + self.errorStr(erCd))
            return erCd
            
        #Wait for move to complete when isBlocking is set
        if isBlocking:
            tmtItr = 0;     #Iteration counter for timeout
            while self.isHoming():
                if tmtItr > self.MVTIMEOUT: 
                    raise TimeoutError("Timeout on home.")
                sleep(self.DELAY)
                tmtItr += 1
                
    def reset(self):
        '''Reset the device

        Returns:
            -1 if no communication is open
            or
            str = the error code if an error occurred
            or
            None if there's no error
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
            
        self.write('1RS')   #execute home search
        sleep(10*self.DELAY)   #reset takes time to execute
        
        #Check for errors
        erFlg, erCd = self.isError()
        if erFlg:
            debug('DEV ERROR::: Device returned error:\n' +
                  '  ' + self.errorStr(erCd))
            return erCd
            
    def stop(self):
        '''Stop all motion on the device

        Returns:
            -1 if no communication is open
            or
            str = the error code if an error occurred
            or
            None if there's no error
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
            
        self.write('1ST')   #execute home search
        
        #Check for errors
        erFlg, erCd = self.isError()
        if erFlg:
            debug('DEV ERROR::: Device returned error:\n' +
                  '  ' + self.errorStr(erCd))
            return erCd
        
    def enable(self):
        '''Disables the device (set 'Enable' state)

        Returns:
            -1 if Communication is not open
            or 
            str = error code if there's an error
            or
            None if no error
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
        
        self.write('1MM1')  #enter disable state
        
        #Check for errors
        erFlg, erCd = self.isError()
        if erFlg:
            debug('DEV ERROR::: Device returned error:\n' +
                  '  ' + self.errorStr(erCd))
            return erCd

    def disable(self):
        '''Disables the device (set 'Disable' state)

        Returns:
            -1 if Communication is not open
            or 
            str = error code if there's an error
            or
            None if no error
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
        
        self.write('1MM0')  #enter disable state
        
        #Check for errors
        erFlg, erCd = self.isError()
        if erFlg:
            debug('DEV ERROR::: Device returned error:\n' +
                  '  ' + self.errorStr(erCd))
            return erCd
        
    #:::::::::::::::::::::::STATE CHECK FUNCTIONS::::::::::::::::::::::::::::::    
    def isReady(self) -> bool:
        '''Checks that the device is in a 'Ready' state

        Returns: 
            bool = whether or not the device is in a ready state
            or
            -1 if communication is not open
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
        
        rd = []
        #get positioner error and controller state
        for axis in self.axes:
            self.write('1TS{}'.format(self.axes[axis]))
            rd.append(self.read())

        # state is in last two characters
        return all([item[-2:] in ["32", "33", "34", "35", "36"] for item in rd])
            
    def isDisable(self) -> bool:
        '''Checks that the device is in a 'Disable' state

        Returns: 
            bool = whether or not the device is in a disable state
            or
            -1 if communication is not open
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
        
        rd = []
        #get positioner error and controller state
        for axis in self.axes:
            self.write('1TS{}'.format(self.axes[axis]))
            rd.append(self.read())

        # state is in last two characters
        return all([item[-2:] in ["3C", "3D"] for item in rd])
            
    def isReferenced(self) -> bool:
        '''Checks that the device is in a 'Referenced' state

        Returns: 
            bool = whether or not the device is in a referenced state
            or
            -1 if communication is not open
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
        
        rd = []
        #get positioner error and controller state
        for axis in self.axes:
            self.write('1TS{}'.format(self.axes[axis]))
            rd.append(self.read())

        # state is in last two characters
        return all([item[-2:] in ["0A", "0B", "0C", "0D", "0E", "0F", "10"] for item in rd])
            
    def isConfiguration(self) -> bool:
        '''Checks that the device is in 'Configuration' state

        Returns: 
            bool = whether or not the device is in configuration state
            or
            -1 if communication is not open
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
        
        rd = []
        #get positioner error and controller state
        for axis in self.axes:
            self.write('1TS{}'.format(self.axes[axis]))
            rd.append(self.read())

        # state is in last two characters
        return all([item[-2:] == "14" for item in rd]) 
    
    def isHoming(self) -> bool:
        '''Checks that the device is in 'Homing' state

        Returns: 
            bool = whether or not the device is in homing state
            or
            -1 if communication is not open
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
        
        rd = []
        #get positioner error and controller state
        for axis in self.axes:
            self.write('1TS{}'.format(self.axes[axis]))
            rd.append(self.read())

        # state is in last two characters
        return all([item[-2:] == "1E" for item in rd]) 
            
    def isMoving(self, homing=True, ol=True) -> bool:
        '''Checks that the device is in 'Moving' state

        Inputs:
            homing = whether to check for homing as well
            ol = whether to check for open loop movement as well
        Returns: 
            bool = whether or not the device is in moving state
            or
            -1 if communication is not open
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
        
        rd = []
        #get positioner error and controller state
        for axis in self.axes:
            self.write('1TS{}'.format(self.axes[axis]))
            rd.append(self.read())

        # Closed loop movement
        ret = all([stat[-2:] == "28" for stat in rd]) 
        # Open loop step and jog (respectively)
        if ol: ret = (ret or all([stat[-2:] in ["29", "46"] for stat in rd]))
        # Homing
        if homing: ret = (ret or all([stat[-2:] == "1E" for stat in rd]))
        
        return ret
            
    #:::::::::::::::::::::::MOVE FUNCTIONS:::::::::::::::::::::::::::::::::::::        
    def moveAbs(self, newPOS:dict, isBlocking:bool = False) -> dict:
        '''Moves device to newPOS.values() mm from current position

        Inputs:
            newPOS = keys as axes, values as amt to move
            isBlocking = whether this function blocks program until done
        Returns:
            dict = key as axis, value as error code
            or
            -1 if communications aren't open
            or
            None if no error
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1

        #Check that all axes are valid
        if not all([1 if axis in self.axes else 0 for axis in newPOS]):
            msg = "Invalid axis. Available axes: " + str(list(self.axes.keys()))
            raise ValueError(msg)

        err = {}
        for axis in self.axes:
            #move absolute
            self.write('1PA{}{}'.format(self.axes[axis], newPOS[axis]))
        
            #Check for errors
            erFlg, erCd = self.isError()
            if erFlg:
                debug('DEV ERROR::: Device returned error:\n' +\
                    '  ' + self.errorStr(erCd))
                err[axis] = erCd

        #Wait for move to complete when isBlocking is set
        if isBlocking:
            tmtItr = 0;     #Iteration counter for timeout
            while self.isMoving():
                if tmtItr > self.MVTIMEOUT:
                    msg = "Timeout on absolute move: {}".format(relMOV)
                    raise TimeoutError(msg)
            sleep(self.DELAY)
            tmtItr += 1

        if len(err) > 0: return err
        else: return
        
    def moveRel(self, relMOV:dict, isBlocking:bool = False) -> dict:
        '''Moves device relMOV.values() mm from current position

        Inputs:
            relMOV = keys as axes, values as amt to move
            isBlocking = whether this function blocks program until done
        Returns:
            dict = key as axis, value as error code
            or
            -1 if communications aren't open
            or
            None if no error
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1

        #Check that all axes are valid
        if not all([1 if axis in self.axes else 0 for axis in relMOV]):
            msg = "Invalid axis. Available axes: " + str(list(self.axes.keys()))
            raise ValueError(msg)

        err = {}
        for axis in self.axes:
            #move relative
            self.write('1PR{}{}'.format(self.axes[axis], relMOV[axis]))
        
            #Check for errors
            erFlg, erCd = self.isError()
            if erFlg:
                debug('DEV ERROR::: Device returned error:\n' +\
                    '  ' + self.errorStr(erCd))
                err[axis] = erCd

        #Wait for move to complete when isBlocking is set
        if isBlocking:
            tmtItr = 0;     #Iteration counter for timeout
            while self.isMoving():
                if tmtItr > self.MVTIMEOUT:
                    msg = "Timeout on relative move: {}".format(relMOV)
                    raise TimeoutError(msg)
            sleep(self.DELAY)
            tmtItr += 1

        if len(err) > 0: return err
        else: return

    #:::::::::::::::::::::::ERROR CHECK FUNCTIONS::::::::::::::::::::::::::::::    
    def isError(self):
        #Uses TE to reduce read time
        '''Checks for device errors
        Returns:
            boolean True/False to mark if an error occurred
            str with error code returned by device
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
       
        #Read error
        self.write('1TE')   #get command error string
        rd = self.read()
        
        #Check if error occurred and return accoridingly
        erCd  = rd[3:]
        erFlg = False
        if erCd != '@':
            #error occurred
            erFlg = True
        return erFlg, erCd
    
    def errorStr(self, erCd):
        '''Translates the error code ,'erCd', to a readable string
        Returns:
            str with text describing the error code
            *If device is not open(), the code itself is returned
        '''
        #Check if port is open
        if self.con_type is None:
            debug('WARNING::: Device must be open to translate string\n' + 
                  '  solution: call open()')
            return erCd
        
        #Send error code to device for translation
        self.write('1TB{}'.format(erCd))   #get command error string
        rd = self.read()    
        
        if rd[3:4] != erCd:
            debug('ERRORR::: Device did not recognize provided error code')
            return 'Unrecognized Error Provided:  ' + erCd
        else:
            return rd[3:]

    #:::::::::::::::::::::::POSITION CHECK FUNCTIONS:::::::::::::::::::::::::::            
    def reqPosSet(self) -> dict:
        '''Requests the target position

        Returns:
            dict = keys as axes, values as position or -9999 if error
                if there is an error, another dict is returned with error codes
            or
            -1 if communication isn't open
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
        
        ret = {}
        err = {}
        for axis in self.axes:
            self.write('1TH{}'.format(self.axes[axis]))    #get target position
            rd = self.read()[3:]
            rd = rd[len(self.axes[axis]):]
        
            #Check for errors
            erFlg, erCd = self.isError()
            if erFlg:
                debug('DEV ERROR::: Device returned error:\n' +
                    '  ' + self.errorStr(erCd))
                ret[axis] = -9999
                err[axis] = erCd
            else: ret[axis] = float(rd)

        if len(err) > 0: return ret, err
        else: return ret
    
    def reqPosAct(self) -> dict:
        '''Requests the current position

        Returns:
            dict = keys as axes, values as position or -9999 if error
                if there is an error, another dict is returned with error codes
            or
            -1 if communication isn't open
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
            
        ret = {}
        err = {}
        for axis in self.axes:
            self.write('1TP{}'.format(self.axes[axis]))  #get current position
            rd = self.read()[3:]
            rd = rd[len(self.axes[axis]):]
        
            #Check for errors
            erFlg, erCd = self.isError()
            if erFlg:
                debug('DEV ERROR::: Device returned error:\n' +
                    '  ' + self.errorStr(erCd))
                ret[axis] = -9999
                err[axis] = erCd
            else: ret[axis] = float(rd)
        
        if len(err) > 0: return ret, err
        else: return ret

    def reqInfo(self):
        '''Reads device information and updates variables
        *These values usually don't change so accessing them from the 
            instance variable is more efficient than repeating a call to 
            reqInfo()
        *To simply display values, use devPrint()
        Returns: 
            Serial number, device number, revision version
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
        
        #Request and read device information
        self.write('1ID?')     #Get stage identifier
        rd  = self.read()
        
        #Format and set SN and TY instance variables
        self.SN     = rd[18:25] 
        self.TY     = rd[3:14] 
        
        #Request and read revision information
        self.write('1VE')     #Get controller revision information 
        rd  = self.read()
        
        #Format and set FW instance variable
        self.FW     = rd[15:]
               
    def reqLim(self) -> dict:
        '''Reads device software limits and updates variables
        *These values usually don't change so accessing them from the 
            instance variable is more efficient than repeating a call to 
            reqLim()
        *To simply display the values, use devPrint()
        Returns: 
            dict = keys as axes, values as lists: index 0 = min, index 1 = max
            or
            -1 if communication isn't open
        '''
        #Check if port is open
        if self.con_type is None:
            debug('ERROR::: Device must be open\n' + 
                  '  solution: call open()')
            return -1
        
        for axis in self.axes: 
            #Request and read lower limit
            self.write('1SL{}?'.format(self.axes[axis]))
            rd  = self.read()[3:]
            rd = rd[len(self.axes[axis]):]
        
            #Format and set MNPS instance variable
            temp_lim = [float(rd)]
        
            #Request and read upper limit
            self.write('1SR{}?'.format(self.axes[axis]))
            rd  = self.read()[3:]
            rd = rd[len(self.axes[axis]):]
        
            #Format and set MXPS instance variable     
            temp_lim.append(float(rd))

            self.lims[axis] = temp_lim
        
        return self.lims        
