'''
================================================================================
Library for easy control of the CRED2 using ircam0server and other scripts/libs 
    from scexao. This is basically a wrapper around ircam0server and 
    scexao_shmlib.

Notes:
    - Assumes that you've already started the server and other scripts by doing:
        - TODO: Fill in startup procedure here!!

Dependencies:______________________________________________
  Custom:
  - ircam0server        Manages camera control as well as comms
  - scexao_shmlib       Python shared memory library for cameras 

  Native:
  - sys         --
  - time        --
  - os          --

================================================================================
Author:         Dan Echeverri (dechever@caltech.edu)
Origin Date:    08/17/2018
Last Mod:       08/19/2018
'''

'''
____Change Log:____

  __09/06/2018__
  DE:
   * Changed import paths for new structure
     * Removed sys.path.append for labjack path
     * Removed unnecessary os, time imports

  __09/07/2018__
  DE:
   * Changed default value of fname to /tmp/ircam0.im.shm
     * This is what our cred2 shm is always called right now and this library is
       for the cred2 specifically so doing this will simplify instantiation
     * Kept fname as an input argument for compatibility with old scripts

  __12/12/2018__
  JR:
   * log Temp, tint & FPS for the get and set functions
     * Added import of FIU_Log for logit function. Appended path as needed.

  __01/21/19__
  JR:
   * Modification of getNumpyImage.
     * added "Param" keyword to return a structure with the image.
       The structure contained all the parameters associated to the image.

  __02/08/19__
  DE:
   * Modified getNumpyImage() to match new shmlib/scexao_shmlib structure
     * Removed check modification to counter since not needed by new scexao_shm
     * Moved where image is read to outside Param statement to simplify code

'''

## import system library
import sys
## import time library 
import time
## Import OS library
import os

# Location of the FIU_Log library
sys.path.append('/kroot/src/kss/nirspec/nsfiu/dev/lib/')
## Function use to add comments to the automatic log
from FIU_Log import logit


sys.path.append('/kroot/src/kss/nirspec/nsfiu/dev/lib/cred2New')
from scexao_shmlib import shm

class cred2(shm):
    def __init__(self, fname='/tmp/ircam0.im.shm', data=None,
                 verbose=False, nbkw=0):
        ''' --------------------------------------------------------------
        Constructor for a SHM (shared memory) object with cam control features.

        * This object has all the functionality of the scexao_shmlib object as 
            well as aditional functionality for simplifying and unifying control
            of the CRED2 from a python session.

        Parameters:
        ----------
        - fname: name of the shared memory file structure
        - data: some array (1, 2 or 3D of data)
        - verbose: optional boolean
        - nbkw: # of keywords to be appended to the data structure (optional)

        Description from scexao_shmlib:
        ------------------------------
        Depending on whether the file already exists, and/or some new
        data is provided, the file will be created or overwritten.

        In addition to the generic shm data structure, semaphores are
        connected to the object.
        -------------------------------------------------------------- '''
        self.tmux("start")  # Ensure that acquisition is started
                                #Repeat calls to start do not cause a problem
        shm.__init__(self, fname, data, verbose, nbkw)


# ------------------------------------------------------------------
#             Acquisition control commands
# ------------------------------------------------------------------
    def startAcq(self):
        ''' --------------------------------------------------------------
        Function to start image acquisition

        * Starts reading from the detector until a stop signal is sent
        * Explicit call not needed upon initialization
        * Takes ~1s to execute due to built-in call to sleep()

        Parameters:
        ----------

        Returns:
        -------

        -------------------------------------------------------------- '''
        self.tmux("start")
        time.sleep(1)

    def stopAcq(self):
        ''' --------------------------------------------------------------
        Function to stop image acquisition

        * Stops reading from the detector
        * Takes ~1s to execute due to built-in call to sleep()

        Parameters:
        ----------

        Returns:
        -------

        -------------------------------------------------------------- '''
        self.tmux("stop")
        time.sleep(1)

    def fullShutdown(self):
        ''' --------------------------------------------------------------
        Function to end both tmux processes

        * Only call this if you want to stop all acquisition and kill the server
        * DOES NOT NEED to be called; It's okay to leave acquisition running and
            the server active.
        * This will take ~4s to execute do to built-in calls to sleep()

        Parameters:
        ----------

        Returns:
        -------

        -------------------------------------------------------------- '''
        self.tmux("stop")
        time.sleep(1)
        self.tmux("", session="ircam0run", command="kill-session")
        time.sleep(1)
        self.tmux("exit")
        time.sleep(1)
        self.tmux("", session="ircam0ctrl", command="kill-session")
        time.sleep(1)

# ------------------------------------------------------------------
#             short hands for tmux commands
# ------------------------------------------------------------------
    def tmux(self, cargs="", session="ircam0ctrl", command="send-keys"):
        ''' ------------------------------------------------------------
        Synthesizes and sends a tmux command. The default option was
        chosen to match the most common one, hence making the code
        below more concise.
        ------------------------------------------------------------ '''
        if cargs == "":
            os.system("tmux %s -t %s" % (command, session))
        else:
            os.system("tmux %s -t %s '%s' Enter" % (command, session, cargs))


# ------------------------------------------------------------------
#             query functions 
# ------------------------------------------------------------------
    def getNumpyImage(self, check=True, timeout=1.0,Param = False):
        ''' --------------------------------------------------------------------
        Function to read image from shm structure and return as numpy array
        
        * NOTE: under the default parameters, this function will wait up to 1 
                sec for the newest image.
                This means for long exposures, the image you get, even if you 
                have check=True, might not be the newest image. 

        Arguments:
        ----------
        - check:    (def=True) optional flag to to wait for latest image
        - timeout:  (def=1.0) optional value to control length of wait if check
        - Param:    (def=False) optional flag to read shm keywords as well

        Returns:
        --------
        - (ndarray) of (floats) with image in appropriate dimensions 
        - [optional when Param=True] (Dict) of keywords from shm

        -------------------------------------------------------------------- '''
        # Conversion to counter is no longer needed by scexao_shmlib
        #if check:
            #Convert check into expected integer
        #    check = self.get_counter()
        
        # Get image
        im = self.get_data(check, reform=True, timeout=timeout).astype('float')

        if Param:
            self.read_keywords()
            CredPara = {}
            for i in [0,1,2,3,4,5,6,7]:
                CredPara[self.kwds[i]['name']] = self.kwds[i]['value']
            CredPara['tint'] = round(CredPara['tint'],7)
            CredPara['temp'] = round(CredPara['temp'],3)
            return im, CredPara
        else: 
            return im 


    def getTemp(self):
        ''' --------------------------------------------------------------------
        Function to read camera temperature 
        * Queries ircam0server to update shm structure then reads structure.
        * NOTE: this function has a 1 sec sleep to ensure current value is read

        Arguments:
        ----------

        Returns:
        --------
        - (float) with sensor temperature [in degrees C]

        -------------------------------------------------------------------- '''
        # Query temperature from camera and update ircamconf shm
        self.tmux("gtemp") 
        time.sleep(1)

        # Read value from image shm
        ii0 = 7     # index of temperature in keywords structure
        self.read_keyword(ii0)
        self.temp = self.kwds[ii0]['value']

        # Update the log
        logit('Cred2_Temperature[get] : %10.2f [C] ' %  self.temp)
        return self.temp

    def getFPS(self):
        ''' --------------------------------------------------------------------
        Function to read camera frames per second
        * Queries ircam0server to update shm structure then reads structure.
        * NOTE: this function has a 1 sec sleep to ensure current value is read

        Arguments:
        ----------

        Returns:
        --------
        - (float) with frames per second [in Hz]

        -------------------------------------------------------------------- '''
        # Query fps from camera and update ircamconf shm
        self.tmux("gfps")
        time.sleep(1)

        # Read value from image shm
        self.get_fps()
        # Update the log
        logit('Cred2_FPS[get] : %10.2f [Hz]' %  self.fps)      
        return self.fps

    def getTint(self):
        ''' --------------------------------------------------------------------
        Function to read camera exposure time 
        * Queries ircam0server to update shm structure then reads structure.
        * NOTE: this function has a 1 sec sleep to ensure current value is read

        Arguments:
        ----------

        Returns:
        --------
        - (float) with exposure time [in seconds]

        -------------------------------------------------------------------- '''
        # Queryi tint from camera and update ircamconf shm
        self.tmux("gtint") 
        time.sleep(1)

        # Read value from image shm
        self.get_expt()
        # Update the log
        logit('Cred2_Integration_Time[get] : %10.2f [us]' % (self.expt*1e6))
        return self.expt


# ------------------------------------------------------------------
#             set functions 
# ------------------------------------------------------------------
    def setTemp(self, degC):
        ''' --------------------------------------------------------------------
        Function to set camera temperature 
        * NOTE: this function does not return the new temperature since it takes
                time for camera to cool/heat.

        Arguments:
        ----------
        - degC: new temperature setpoint [in Celsius]

        -------------------------------------------------------------------- '''
        self.tmux("stemp %f" %(degC)) 
        # Update the log
        logit('Cred2_Temperature[set] : %10.2f [C] ' % degC)

    def setFPS(self, fps):
        ''' --------------------------------------------------------------------
        Function to set camera frames per second
        
        !!!WARNING!!!: 
            please be careful about the framerate setting. The camera will let 
            you set a framerate higher than the max and I don't know what this 
            is doing. I am working on copying the safety features from Chuck but
            this may take some time. 
        
        * Reads new fps setting reported in shm structure
        * NOTE: this funct. has 1 sec sleep to ensure current value is set/read

        Arguments:
        ----------
        - fps:  new fps setting [in Hz]

        Returns:
        --------
        - (float) with resulting frames per second [in Hz]

        -------------------------------------------------------------------- '''
        # Set value
        self.tmux("sfps %f" %(fps)) 
        time.sleep(1)
        # Query
        self.get_fps()
        # Update the log
        logit('Cred2_FPS[set] : %10.2f [Hz]' %  self.fps) 
        return self.fps

    def setTint(self, tint):
        ''' --------------------------------------------------------------------
        Function to set camera exposure time 
        * Reads new exposure time setting in  shm structure.
        * NOTE: this funct. has 1 sec sleep to ensure current value is set/read
        * NOTE: the value you set may not be the actual value taken by the 
                camera; the camera automatically pushes your value to fit within 
                its bounds. However, the returned val IS the actual tint setting

        Arguments:
        ----------
        - tint: new exposure time setting [in seconds]

        Returns:
        --------
        - (float) with resulting exposure time [in seconds]

        -------------------------------------------------------------------- '''
        # Set Value
        self.tmux("stint %f" %(tint))
        time.sleep(1)
        # Query Value
        self.get_expt()
        # Update the log
        logit('Cred2_Integration_Time[set] : %10.2f [us]' % (tint*1e6))
        return self.expt

    def setCropMode(self, mode):
        ''' --------------------------------------------------------------------
        Function to set camera crop mode
        
        * Only accepts the crop modes implemnted by ircam0server.c PLUS full:
            
            PREDEFINED CROP MODES [from ircam0server]:
              [0]  320 x 256    ( 160-479 x  128-383)  fps = 1192.3 Hz
              [1]  224 x 188    ( 192-415 x  160-347)  fps = 1872.6 Hz
              [2]  128 x 128    ( 256-383 x  192-319)  fps = 3192.6 Hz
              [3]   64 x  64    ( 288-351 x  224-287)  fps = 6428.9 Hz
              [4]  192 x 192    ( 224-415 x  160-351)  fps = 1949.8 Hz
              [5]  320 x 256    ( 128-447 x  128-383)  fps = 1192.3 Hz
              [6]  224 x 188    ( 160-383 x  160-347)  fps = 1872.6 Hz
              [7]  128 x 128    ( 224-351 x  192-319)  fps = 3192.6 Hz
              [8]   64 x  64    ( 256-319 x  224-287)  fps = 6428.9 Hz
              [9]  192 x 192    ( 192-383 x  160-351)  fps = 1949.8 Hz

            FULL CROP MODE
              [10] 640 x 512    ( 000-639 x  000-512)  fps = 0403.7 Hz
        
        * Other crop mode values will be ignored and function will do nothing 
        * Tint and fps are automatically changed when crop mode is changed:
            As such, you will have to re-set these settings manually if you want
            specific values.
        * Function re-reads new camera setting to update shm structure
        
        * NOTE: this funct. takes >12 seconds to complete and WILL block 
                    execution until it is done.

        Arguments:
        ----------
        - mode: pre-defined crop mode (see table above)
                    This value MUST be an integer 0>= mode >= 10

        Returns:
        --------

        -------------------------------------------------------------------- '''
        if mode == 10:
            # Full mode 
            print('-- Stopping Capture')
            self.tmux("stop")
            time.sleep(2)
            print('-- Editing Crop Settings')
            self.tmux("cropOFF")
            time.sleep(2)
            self.tmux("scrop_cols 0 639")
            time.sleep(2)
            self.tmux("scrop_rows 0 511")
            time.sleep(2)
            print('-- Starting Capture Temporarily')
            self.tmux("start")
            time.sleep(5)
            print('-- Stopping Capture To Flush')
            self.tmux("stop")
            time.sleep(2)
            print('-- Restarting Capture')
            self.tmux("start")
            time.sleep(5) 
            print('-- Full Crop Mode Set')
        elif 0 <= mode < 10:
            # pre-determined cropped mode
            print('-- Setting Crop Mode')
            self.tmux("setcrop %i"%(mode))
            time.sleep(12)
            print("-- Crop Mode %i set"%(mode))
        else:
            # invalid mode; do nothing
            return
        
        # Re-load python shm structure to match new settings
        print('-- Reinitializing shm structure')
        self.__init__(fname=self.fname)
        
        #Update shm elements
        self.getFPS()
        self.getTint()
        self.tmux("gNDR")
        time.sleep(1)
        self.get_ndr()


