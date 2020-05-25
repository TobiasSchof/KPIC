import telnetlib
import time

class Conex_Device(object):
    '''Class for controlling the Newport Conex Stages over Telnet
    '''
    DELAY       = .05       #Number of seconds to wait after writing a message
    MVTIMEOUT   = 600       #(MVTIMEOUTxDELAY)= number of seconds device will 
                                #wait before declaring a move timeout error
    # IP and Ports of known conexes to control
    DEVS      = {'FEU' : ('nspecterm', 10007),
                 'FIU' : (None, None)}

    def __init__(self, devid, verbose=False):
        # Define verbosity 
        self.verbose = verbose

        # Identify which device to connect to
        try:
            ip      = self.DEVS[devid][0]
            port    = self.DEVS[devid][1]
        except KeyError as e:
            print('\nUnidentified device id.')
            err1 = '  Options are:'
            for i in self.DEVS.keys():
                err1 += ' %s'%i
            print(err1+'\n')
            raise

        # Create telnet object
        self.tel    = telnetlib.Telnet(ip,port)
        
        # Send 'ID?' command to synchronize comms with device:
            #The first message sent after the device is powered up is 
            #automatically ignored by the device. I did not want to send
            #'1RS' since this would reset the device 
        self.write('1ID?')
        self.readAll() # Clear read buffer

        # Query type of device to know if its linear or angular
        self.write('1ID?')
        rd = self.read()

        # Set flag marking what type of device it is
        if 'M100D' in rd:
            # Device is an angular stage
            self.isAngular = True
            if self.verbose:
                print('Connected to an M100D Angular Stage')
        else:
            # Device is probably a linear stage
            self.isAngular = False
            if self.verbose:
                print('Connected to a Linear Stage')
        
        # Set the available axes based on the type of device
        if self.isAngular:
            # Angular device requires one of two axes identifier
            self.axes   = ['V', 'U']    # Axis labels, IN ORDER. X first, then Y 
        else:
            # Linear device does not require any axis identifier
            self.axes   = ['']          # Blank axis label to append nothing

        # Read the limits on the device to populate range variables
        self.reqLim()
                
    def close(self):
        '''Close telnet connection to the device
        '''
        self.tel.close()

    def write(self, MSG, append=None):
        # Convert 'append' and append to end
        if append != None:
            MSG = MSG + str(append)

        # Add terminator and convert to bytes
        MSG = MSG + '\r\n'
        msg = MSG.encode('ascii')
        
        # Send message
        self.tel.write(msg)

    def readAll(self):
        cnt     = 0
        resl    = []                # List of lines
        res = self.read(tmt=0.25)   # Read first line
        resl.append(res)
        while len(res) > 0 and cnt < 50:
            # Keep reading until no new data or 50 lines have been read
            res = self.read(tmt=0.25)   # Read line
            resl.append(res)
            cnt += 1
            time.sleep(0.05)
        # Remove last, blank line
        if cnt < 50:
            resl.pop()
        return resl

    def read(self, tmt=1.0):
        return self.tel.read_until(bytes('\r\n','utf-8'),tmt).strip().decode('utf-8')

    def _formAx(self,axis):
        try:
            ax = self.axes[axis]
        except (IndexError, TypeError) as e:
            err1 = 'Error::: %s is not a recognized axis.'%str(axis)
            if len(self.axes) == 1:
                err2 = "   Device is a linear stage so only axis is 0"
            else:
                err2 = "   Available axes are:"
                for i in range(len(self.axes)):
                    err2 += " (%d - '%s')"%(i, self.axes[i])
            print("\n"+err1)
            print(err2+"\n")
            raise
        return ax

    def moveAbs(self, newPOS, axis=0, isBlocking=False):
        # Format axis identifier
        ax = self._formAx(axis)
        # Send formatted move command 
        self.write('1PA'+ax, newPOS)

        #Check for errors
        erFlg, erCd = self.isError()
        if erFlg:
            if erCd in ['C', 'G']:
                ind = self.axes.index(ax)
                mn  = self.minpos[ind]
                mx  = self.maxpos[ind]
                print('ERROR::: Desired position likely beyond limits\n' +
                      '  Must be within [%0.4f and %0.4f]' %(mn, mx))
                return
            print('DEV ERROR::: Device returned error:\n' +
                  '  ' + self.errorStr(erCd))
            return

        #Wait for move to complete when isBlocking is set
        if isBlocking:
            tmtItr = 0;     #Iteration counter for timeout
            while self.isMoving(axis=axis):
                if tmtItr > self.MVTIMEOUT:
                    #exit loop in case of timout
                    print('ERROR::: moveAbs() timed out\n' +
                          '  Call isError()/errStr() to get device error.\n' +
                          '  Timeout is set to %f s' %(self.DELAY*self.MVTIMEOUT))
                    break
                time.sleep(self.DELAY)
                tmtItr += 1
            return self.reqPosAct(axis)
    
    def reqPosAct(self, axis=0):
        '''Requests the current position
        Returns:
            Actual position in mm/degrees as reported by device
            -9999 if error occurred
        '''
        # Format axis identifier
        ax  = self._formAx(axis)
        # Send formatted position request command
        cmd = '1TP'+ax
        self.write(cmd)         #get current position
        rd = self.read()
        
        #Check for errors
        erFlg, erCd = self.isError()
        if erFlg:
            print('DEV ERROR::: Device returned error:\n' +
                  '  ' + self.errorStr(erCd))
            return -9999
        
        # Parse output for position value
        return float(rd.split(cmd,1)[1])

    def isMoving(self, rd = None, axis=0):
        #Request status if 'rd' not provided
        if rd == None:
            #Check if device is in 'Moving' state
            ax  = self._formAx(axis)
            self.write('1TS'+ax)   #get positioner error and controller state
            rd = self.read()
        
        #Check for moving case
        if (rd[-2:] in '28'):
            return True
        else:
            return False

    def isError(self):
        #Uses TE to reduce read time
        '''Checks for device errors
        Returns:
            boolean True/False to mark if an error occurred
            str with error code returned by device
        '''
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
        #Send error code to device for translation
        self.write('1TB', erCd)   #get command error string
        rd = self.read()    
        
        if rd[3:4] != erCd:
            print('ERRORR::: Device did not recognize provided error code')
            return 'Unrecognized Error Provided:  ' + erCd
        else:
            return rd[3:]


    def reqLim(self):
        # Initialize lower limit list to same length as axes list
        self.minpos = [-9999]*len(self.axes)
        for i in range(len(self.axes)):
            # Request and read lower limit
            cmd = '1SL'+self.axes[i]
            self.write(cmd+'?')     #Get negative software limit
            rd  = self.read()
            # Format and set minpos value
            self.minpos[i]  = float(rd.split(cmd,1)[1]) 
        
        self.maxpos = [9999]*len(self.axes)
        for i in range(len(self.axes)):
            # Request and read upper limit
            cmd = '1SR'+self.axes[i]
            self.write(cmd+'?')     #Get positive software limit
            rd  = self.read()
            #Format and set MXPS instance variable     
            self.maxpos[i]  = float(rd.split(cmd,1)[1])
        
        return (self.minpos, self.maxpos)        
