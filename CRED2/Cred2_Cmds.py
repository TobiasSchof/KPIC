
'''----------------------------------------------------------------------------

--------------------------------------------------------------------------- '''

############################## Import Libraries ###############################

## Math Library
import numpy as np
## Import operating system library
import os
## Import system library
import sys
## Time library 
import time
## Semaphore library 
import posix_ipc as ipc
##
import pdb
## import library used to manipulate fits files
from astropy.io import fits
## Import subprocess library used for making making sys call
import subprocess as sp
## Config files library
import configparser

# Location of all sheared memory libraries
sys.path.append('/kroot/src/kss/nirspec/nsfiu/dev/lib/cred2New/')
from shmlib import shm as shm0

# Location of Shm lib
sys.path.append('/kroot/src/kss/nirspec/nsfiu/dev/scripts/FIU/')
## Shared memory library
import shmlibJR as shmlib

# Location of the KPIC libraries
sys.path.append('/kroot/src/kss/nirspec/nsfiu/dev/lib/')
## Function used to add comments to the automatic log
from Auto_Log import logit
## Function used to get the path where data should be saved
from FIU_Commands import get_path
## Function used to get access to Keck II metrology
from K2_Metrology import K2_Metrology_cmds

# Instancy Keck II metrology commands class
met2     = K2_Metrology_cmds()

################################# Parameters ##################################

# Path to the conf file specifying which keywords to query using keyheader
KEYCONFPTH = '/kroot/src/kss/nirspec/nsfiu/dev/config/nfiu_fitsheader.conf'

# Location of all .ini files
configpath = '/kroot/src/kss/nirspec/nsfiu/dev/config/'

################################# Class cred2 #################################

class cred2(shm0):
    # =========================================================================
    def __init__(self, fname=None, data=None, verbose=False, nbkw=0):
        ''' -------------------------------------------------------------------
        Constructor for a SHM (shared memory) object.
        
        Arguments:
        - fname		: name of the shared memory file structure
        - data		: some array (1, 2 or 3D of data)
        - verbose	: optional boolean
        - packed	: True -> packed / False -> aligned data format
        - nbkw		: # of keywords to be appended to the data structure
        
        Depending on whether the file already exists, and/or some new
        data is provided, the file will be created or overwritten.
        
        In addition to the generic shm data structure, semaphores are
        connected to the object.
        ------------------------------------------------------------------- '''
        # Local copy of the verbose parameter
        self.verbose = verbose
        #
        self.nosem = True
        #
        shm0.__init__(self, fname, data, verbose, False, nbkw)
        # Number of semaphores to address
        self.nsem = 10
        # 
        myname = fname.split('/tmp/')[-1].split('.')[0]
        #
        for ii in range(self.nsem):
            semf = "%s_sem%02d" % (myname, ii)
            tmp = 'self.sem%02d = ipc.Semaphore(semf, os.O_RDWR | ipc.O_CREAT)'
            exec(tmp % (ii,))
            test = ipc.Semaphore("%s_semlog" % (myname,), os.O_RDWR | ipc.O_CREAT)
            
        #
        self.nosem = False
        
        # This value contain the value of the semaphore when check = True
        # Used by get_data()
        self.semVal = 0
        
        # Number of the semaphore check default value = 1.
        # 0 is used by thorcam
        # 1 is the default value
        # 2 is used by TheAverager.py
        # 3 is used by TC_Calibration.py
        # 4 is used by PSF_Position.py
        # 5 is used by Sylvain
        # 6 is used by DM_control.py
        self.semNb = 1
        
        # Pre-allocate space for a list of parameters associated to each image
        self.names = ['tint','fps','ndr','x_min','x_max','y_min','y_max','temp']
        self.TCParam = {}
        self.nb_param = np.int(np.size(self.names))
        # 
        self.dim_x = -1
        self.dim_y = -1
        #
        for i in np.arange(self.nb_param): self.TCParam[self.names[i]] = 0.
        
        # Instantiate the class ConfigParser()
        config = configparser.ConfigParser()
        # parse .ini file
        config_path = config.read(configpath + 'TC_Param.ini') 
        # Extract the name of the sheared memory from the .init file.
        Name_P  = config.get('Shm_path','Shm_P')
        # Create an array of zero to initialize the sheared memory.
        self.Param   = np.zeros([np.int(config.getfloat('Shm_dim','Shm_P_dim')),1])
        # Create the structure variable associated to the parameter.
        self.Str_P  = {}
        # Fill the structure and initialize the parameters with information contains
        # in the .ini file 
        for n in config.options('Shm_P_Content'):
            self.Str_P[n] = np.int(config.getfloat('Shm_P_Content',n))  
            self.Param[self.Str_P[n],0] = config.getfloat('Shm_P_Init',n)
        # Try to read the shm who contains the parameters of the TC.
        try:
            self.Shm_P = shmlib.shm(Name_P)
        except:
            # Creat the shm if it does not already exist.
            self.Shm_P = shmlib.shm(Name_P, data = self.Param)
            # Initialize the values
            self.Param = self.get_all_parameters()
        
        # Read the parameters contains into the sheared memory
        self.Param = self.Shm_P.get_data()

        # Load calibration data if exist
        self.load_calibration_images()        
        
        # parse .ini file
        config_path = config.read(configpath + 'TC_Config.ini') 
        # Create the structure variable associated to the predefined config.
        self.Config  = {}
        # Fill the structure with information contains in the .ini file 
        for n in config.options('Config_FPS'):
             fps  =   np.int(config.getfloat('Config_FPS' ,n))
             tint = np.float(config.getfloat('Config_Tint',n))
             ndr  =   np.int(config.getfloat('Config_NDR' ,n))
             temp = np.float(config.getfloat('Config_Temp',n))
             xmin =   np.int(config.getfloat('Config_Xmin',n))
             xmax =   np.int(config.getfloat('Config_Xmax',n))
             ymin =   np.int(config.getfloat('Config_Ymin',n))
             ymax =   np.int(config.getfloat('Config_Ymax',n))
             mmin = np.float(config.getfloat('Config_Mmin',n))
             mmax = np.float(config.getfloat('Config_Mmax',n))
             flux = np.float(config.getfloat('Config_Flux',n))          
             self.Config[n] = [fps,tint,ndr,temp,xmin,xmax,ymin,ymax,mmin,mmax,flux]
        
        # Update shape of the image
        tmp = self.get_image_shape()
        # Extract and sort the list of config predifined
        self.Config_List = sorted(self.Config.keys())

    # =========================================================================
    def tmux(self, cargs="", session="ircam0ctrl", command="send-keys"):
        ''' -------------------------------------------------------------------
        Synthesizes and sends a tmux command. The default option was
        chosen to match the most common one, hence making the code
        below more concise.
        ------------------------------------------------------------------- '''
        if cargs == "":
            os.system("tmux %s -t %s" % (command, session))
        else:
            os.system("tmux %s -t %s '%s' Enter" % (command, session, cargs))
    
    # =========================================================================
    def set_data(self, data, check_dt = False):
        ''' -------------------------------------------------------------------
        This function is used to:
        - update the data contains into the sheared memory.
        - post semaphores to signal data has been updated.
        ------------------------------------------------------------------- '''
        # Update the data contains into the sheared memory
        shm0.set_data(self, data, check_dt)
        #
        if self.nosem is False:
            for ii in range(10):
                semf = "%s_sem%02d" % (self.mtdata['imname'], ii)
                exec('self.sem%02d.release()' % (ii,))
        else:
            print("skip sem post this first time")
            
    # =========================================================================
    def get_data(self,check=False,reform=True,sleepT=0.001,timeout=5):
        ''' -------------------------------------------------------------------
        Description:
            Wrapper around shmlib.py's "get_data". This adds the use of 
            semaphores when reading data so that we don't need to use a sleep. 
            This should help improve the timing stability of image reads.
            
        Returns:
            - Last image captured by the detector.
        ------------------------------------------------------------------- '''
        # Wait for semaphore post when check is set
        if (self.nosem is False) and (check is not False):
            # Get the current value of the semaphore.
            exec('self.semVal=self.sem%02d.value' % (self.semNb))
            for k in range(0,self.semVal):
                exec('self.sem%02d.acquire()' % (self.semNb))
            
            semf = "%s_sem%02d" % (self.mtdata['imname'],self.semNb)
            exec('self.sem%02d.acquire()' % (self.semNb))
            # Set check to false to avoid performing check again in shm0 lib
            check = False
        
        # Call get_data as usual
        return shm0.get_data(self, check, reform, sleepT, timeout)
        
    # =========================================================================
    def close(self,):
        ''' -------------------------------------------------------------------
        Description:
            This function close access to the sheared memory
        ------------------------------------------------------------------- '''
        #
        shm0.close(self)
        # if self.nosem is False:
        for ii in range(self.nsem):
            semf = "%s_sem%02d" % (self.mtdata['imname'], ii)
            exec('self.sem%02d.close()' % (ii,))

    # =========================================================================
    def get_tint(self,):
        ''' -------------------------------------------------------------------
        Description:
            Function used to get the exposure time of the detector.
            
        Returns:
        - tint	= exposure time of the detector in second          - keyword #0		
        ------------------------------------------------------------------- '''
        # Query exposure time from camera and update ircamconf shm
        self.tmux("gtint") 
        # Wait a second
        time.sleep(1)
        
        # Index of the exposure time parameter in keywords
        ii0 = 0
        # Read the keyword
        self.read_keyword(ii0)
        # Update the local value of the exposure time
        self.TCParam['tint'] = round(self.kwds[ii0]['value'],7)
        # Get data contains into the parameter shm
        self.Param = self.Shm_P.get_data()
        # Update the parameters contains into the sheared memory
        self.Param[self.Str_P['tint']] = self.TCParam['tint']
        # Update the shm
        self.Shm_P.set_data(self.Param)
        # Returns the exposure time
        return self.TCParam['tint']
        
    # =========================================================================
    def get_fps(self,):
        ''' -------------------------------------------------------------------
        Description:
            Function used to get the frame rate of the detector.
        
        Returns:
        - FPS	= number of frame acquired per second              - keyword #1
        ------------------------------------------------------------------- '''
        # Query the FPS value from camera and update ircamconf shm
        self.tmux("gfps") 
        # Wait a second
        time.sleep(1)
        
        # Index of the frame rate parameter in keywords
        ii0 = 1
        # Read the keyword
        self.read_keyword(ii0)
        # Update the local value of the fps
        self.TCParam['fps'] = self.kwds[ii0]['value']
        # Get data contains into the parameter shm
        self.Param = self.Shm_P.get_data()
        # Update the parameters contains into the sheared memory
        self.Param[self.Str_P['fps']] = self.TCParam['fps']
        # Update the shm
        self.Shm_P.set_data(self.Param)
        # Return the number of frame per second
        return self.TCParam['fps']
        
    # =========================================================================
    def get_max_fps(self,dimensions = None):
        ''' -------------------------------------------------------------------
        Description:
            This function return the maximum fps under the current Cred2 
            configuration.
        Note:			
            JR did tests at Keck. The image can be transfert efficiently 
            between the CRED2 and the computer if the flow of data is lower or 
            equal to 200*512*640 pixels per second (Full frame read at 200 Hz).
            This maximum flow of data will evolved in the futur. 
        Arguments:
            - dimensions: (optional) if provided, compute the readout using 
                          this dimension for the image. If not provided,
                          compute the readout using the current dimension of
                          the image.
        
        Returns:
        - max_fps
        ------------------------------------------------------------------- '''
        # Check if dim has been provided by the user
        if dimensions != None:
            if not isinstance(dimensions,(list,tuple,np.ndarray)):
                if self.verbose:
                    text = 'The dimension argument must be a vector.' 
                    print('Error: ' + text)
                return False
            else:
                if not np.shape(dimensions) == (2,):
                    if self.verbose:
                        text = 'The dimension argument must contains 2 values.'
                        print('Error: ' + text)
                    return False
                else:
                    local_dim_x = np.int(dimensions[0])
                    local_dim_y = np.int(dimensions[1])
        
        else: 
            # Verify if the dimensions of the image are known 
            if self.dim_x == -1: self.get_image_shape()
            # Update local dimension x and y based on the current dimensions 
            # of the image provided by the detector
            local_dim_x = self.dim_x
            local_dim_y = self.dim_y

        # Compute the maximum FPS for the current dimension of the image
        max_fps = (200.*640*512)/(local_dim_x*local_dim_y)

        # Return the maximum FPS who can be set.
        return max_fps

    # =========================================================================
    def get_tint_limits(self):
        ''' -------------------------------------------------------------------
        Description:
            This function return the limits value for the tint under the  
            current Cred2 configuration.
        Note:			
            None. 
        Arguments:
            None
        Returns:
            [min_tint,max_tint]
        ------------------------------------------------------------------- '''
        # Compute the maximum exposure time based on current FPS
        max_tint = np.round(1./self.get_fps()-self.get_readout(),6)
        # Verify if max_tint is longer than min_tint
        if max_tint == 0.000050: max_tint < 0.000050 
        # Return the maximum FPS who can be set.
        return [0.000050,max_tint]

    # =========================================================================
    def get_fps_limits(self):
        ''' -------------------------------------------------------------------
        Description:
            This function return the limits value for the fps under the  
            current Cred2 configuration.
        Note:			
            None. 
        Arguments:
            None
        Returns:
            [min_fps,max_fps]
        ------------------------------------------------------------------- '''
        max_fps_size = self.get_max_fps()
        max_fps_tint = 1./(self.get_tint()+self.get_readout())
        # Select the maximum fps 
        max_fps = np.floor(np.min([max_fps_size,max_fps_tint]))  
        # Verify if max_fps is higher than min_fps
        if max_fps == 0.000050: max_fps <= 0.000050 
        # Return the maximum FPS who can be set.
        return [1.,max_fps]
        
    # =========================================================================
    def get_readout(self,variante = '400FPS',dimensions = None):
        ''' -------------------------------------------------------------------
        Description:
            Function used to get the readout time. This value depend on the 
            variant of the CRED2 software used (see user manual version 190109 
            section 7.3.1).

        Arguments:
            - variant   : Case #1 = '400FPS' (default) set the readout speed at
                          80% of 195Mpix/sec
                          Case #2 = '600FPS' set the readout speed at 80% of 
                          292Mpix/sec
            - dimensions: (optional) if provided, compute the readout using 
                          this dimension for the image. If not provided,
                          compute the readout using the current dimension of
                          the image.						   
        Returns:
        - readout	= time in second required to read an image.
        ------------------------------------------------------------------- '''
        # Check if dim has been provided by the user
        if dimensions != None:
            if not isinstance(dimensions,(list,tuple,np.ndarray)):
                if self.verbose:
                    text = 'The dimension argument must be a vector.' 
                    print('Error: ' + text)
                return False
            else:
                if not np.shape(dimensions) == (2,):
                    if self.verbose:
                        text = 'The dimension argument must contains 2 values.'
                        print('Error: ' + text)
                    return False
                else:
                    local_dim_x = np.int(dimensions[0])
                    local_dim_y = np.int(dimensions[1])
		
        else: 
            # Verify if the dimensions of the image are known 
            if self.dim_x == -1: self.get_image_shape()
            # Update local dimension x and y based on the current dimensions 
            # of the image provided by the detector
            local_dim_x = self.dim_x
            local_dim_y = self.dim_y
            
        # Verify if the variant value provided is valid and known
        if isinstance(variante,(str)):
            if   variante.lower() in ['400fps']: speed = (195*1e6)*0.8
            elif variante.lower() in ['600fps']: speed = (292*1e6)*0.8
            else:
                if self.verbose:
                    T ='The variante of the CRED2 software provided is unkown.' 
                    print(T)
                return False
        else:
            if self.verbose:
                T ='The variante argument must be a string.' 
                print(T)
            return False
        # Return the readout
        return (local_dim_x*local_dim_y)/speed
        
    # =========================================================================
    def get_ndr(self,):
        ''' -------------------------------------------------------------------
        Description:
            Function used to get the # of non destructive reads of the detector
            
        Returns:
        - NDR	= number of non-destructive read per image         - keyword #2
        ------------------------------------------------------------------- '''
        # Query the NDR value from camera and update ircamconf shm
        self.tmux("gNDR") 
        # Wait a second
        time.sleep(1)
        
        # Index of the NDR parameter in keywords
        ii0 = 2 
        # Read the keyword
        self.read_keyword(ii0)
        # Update the local value of the ndr
        self.TCParam['ndr'] = self.kwds[ii0]['value']
        # Get data contains into the parameter shm
        self.Param = self.Shm_P.get_data()
        # Update the parameters contains into the sheared memory
        self.Param[self.Str_P['ndr']] = self.TCParam['ndr']
        # Update the shm
        self.Shm_P.set_data(self.Param)
        # Return the ndr
        return self.TCParam['ndr']
        
    # =========================================================================
    def get_crop(self,):
        ''' -------------------------------------------------------------------
        Description:
            Function used to get the crop parameter of the detector.
        
        Returns:
        Case # 1: A vector who contains the crop parameter of the detector.
            crop = [x_min,x_max,y_min,y_max]
            - x_min	= X position of the first pixel of the (sub)images - kwd #5
            - x_max	= X position of the last  pixel of the (sub)images - kwd #6
            - y_min	= Y position of the first pixel of the (sub)images - kwd #4
            - y_max	= Y position of the last  pixel of the (sub)images - kwd #3
        Case # 2:
            - False : if the size of the image is not coherent with the values
                      contain in the crop vector.
        ------------------------------------------------------------------- '''
        # Query the values from camera and update ircamconf shm
        self.tmux("gcrop_cols")
        self.tmux("gcrop_rows")
        # Wait a second
        time.sleep(1)
        # Index of the first parameter used to define the (sub)images
        ii0 = 3 
        # Read the all keywords
        for i in range(4): self.read_keyword(ii0+i)
        # Update the local value of these parameters
        # X and Y have been inverted to be coherent with the size of the images
        # with the function "get_data"
        self.TCParam['x_min'] = self.kwds[5]['value']
        self.TCParam['x_max'] = self.kwds[6]['value']
        self.TCParam['y_min'] = self.kwds[3]['value']
        self.TCParam['y_max'] = self.kwds[4]['value']
        # Get data contains into the parameter shm
        self.Param = self.Shm_P.get_data()
        # Update the parameters contains into the sheared memory
        self.Param[self.Str_P['x_min']] = self.TCParam['x_min']
        self.Param[self.Str_P['x_max']] = self.TCParam['x_max']
        self.Param[self.Str_P['y_min']] = self.TCParam['y_min']
        self.Param[self.Str_P['y_max']] = self.TCParam['y_max']
        # Update the shm
        self.Shm_P.set_data(self.Param)
        # Verify if coherent with the size of the last image saved into the shm
        dim_x = (self.TCParam['x_max'] - self.TCParam['x_min']) + 1
        dim_y = (self.TCParam['y_max'] - self.TCParam['y_min']) + 1
        if self.get_image_shape() == [dim_x,dim_y]:
            # Read the vector who contains the four parameters used to define 
            # the (sub)images
            crop  = [self.TCParam['x_min'],self.TCParam['x_max']
                    ,self.TCParam['y_min'],self.TCParam['y_max']] 
            return crop
        else:
            # Print error message if self.verbose == True
            if self.verbose:
                print('Crop parameters are not coherent with the last image.')
            return False
            
    # =========================================================================
    def get_image_shape(self):
        ''' -------------------------------------------------------------------
        Description:
            This function get and return the shape of the last image saved into
            the sheared memory.
            
        Returns:
        - im_shape = shape of the image [x direction, y direction] 
        ------------------------------------------------------------------- '''
        im_shape = np.shape(self.get_data())
        self.dim_x = im_shape[0] 
        self.dim_y = im_shape[1]
        return [self.dim_x,self.dim_y]
        
    # =========================================================================
    def get_temp(self,):
        ''' -------------------------------------------------------------------
        Description:
            Function used to get the temperature of the detector.
        
        Returns: 
        - temp 	= temperature of the detector in degree Celcius    - keyword #7
        ------------------------------------------------------------------- '''
        # Query the FPS value from camera and update ircamconf shm
        self.tmux("gtemp") 
        # Wait a second
        time.sleep(1)
        
        # Index of the temperature of the detector parameter in keywords
        ii0 = 7
        # Read the keyword
        self.read_keyword(ii0)
        # Update the local value of the ndr
        self.TCParam['temp'] = round(self.kwds[ii0]['value'],3)
        
        # If temperature not read properly
        i = 0
        while self.TCParam['temp'] == 0 and i < 10:
            # Query the temperature of the detector and update ircamconf shm
            self.tmux("gtemp")
            # Wait a second
            time.sleep(1)
            # Read the keyword
            self.read_keyword(7)
            # Read the temperature keyword and update the local value
            self.TCParam['temp'] = round(self.kwds[7]['value'],3)
            i += 1
        
        # Get data contains into the parameter shm
        self.Param = self.Shm_P.get_data()
        # Update the parameters contains into the sheared memory
        self.Param[self.Str_P['temp']] = self.TCParam['temp']
        # Update the shm
        self.Shm_P.set_data(self.Param) 
                   
        # Return the temperature of the detector in degree Celcius
        return self.TCParam['temp']
        
    # =========================================================================
    def get_all_parameters(self,):
        ''' -------------------------------------------------------------------
        Description:
            Function used to get all the parameter of the detector.
            
        Returns:
        - tint	= exposure time of the detector in microsecond     - keyword #0
        - fps	= number of frame acquired per second              - keyword #1
        - ndr	= number of non-destructive read per image         - keyword #2
        - x0 	= X position of the first pixel of the (sub)images - keyword #3
        - x1 	= X position of the last  pixel of the (sub)images - keyword #4
        - y0 	= Y position of the first pixel of the (sub)images - keyword #5
        - y1 	= Y position of the last  pixel of the (sub)images - keyword #6
        - temp 	= temperature of the detector                      - keyword #7
        - time  = time associated to the last image. Not updated here.
        ------------------------------------------------------------------- '''
        # Query exposure time from camera and update ircamconf shm
        self.tmux("gtint") 
        # Query the FPS value from camera and update ircamconf shm
        self.tmux("gfps")
        # Query the NDR value from camera and update ircamconf shm
        self.tmux("gNDR")
        # Query crop values from camera and update ircamconf shm
        self.tmux("gcrop_cols")
        self.tmux("gcrop_rows")
        
        # Wait a second
        time.sleep(1)
        
        # Get the temperature of the detector.
        self.get_temp()
        
        # Read the keywords and update there local values
        for i in np.arange(np.int(np.size(self.names)-1)):
            self.read_keyword(i)
            tmp = self.names[i]
            if i == 0: self.TCParam[tmp] = round(self.kwds[i]['value'],7)
            elif i == 7: self.TCParam[tmp] = round(self.kwds[i]['value'],3)
            else: self.TCParam[tmp] = self.kwds[i]['value']

        # Get data contains into the parameter shm
        self.Param = self.Shm_P.get_data()
        # Update the parameters contains into the sheared memory
        self.Param[self.Str_P['tint' ]] = self.TCParam['tint' ]
        self.Param[self.Str_P['fps'  ]] = self.TCParam['fps'  ]
        self.Param[self.Str_P['ndr'  ]] = self.TCParam['ndr'  ]
        self.Param[self.Str_P['temp' ]] = self.TCParam['temp' ]
        self.Param[self.Str_P['x_min']] = self.TCParam['x_min']
        self.Param[self.Str_P['x_max']] = self.TCParam['x_max']
        self.Param[self.Str_P['y_min']] = self.TCParam['y_min']
        self.Param[self.Str_P['y_max']] = self.TCParam['y_max']
        self.Param[self.Str_P['time' ]] = time.time()
        # Update the shm
        self.Shm_P.set_data(self.Param)
            	
        return self.TCParam
        
    # =========================================================================
    def status(self,):
        ''' -------------------------------------------------------------------
        Description:
            Function used to get the status of the camera.
        
        Notes: 
            - This function is based on get_all_parameters status.
        Arguments:
            - None
        Returns:
            - None	
        ------------------------------------------------------------------- '''
        # Update shm elements
        tmp = self.get_all_parameters()
        
        # Print all parameters
        print('##########################################')
        print('Current parameters of the Tracking Camera:')
        print('- Integration time   = %08.6f s' %tmp['tint'])
        print('- Number of frame read per second = %05.0d' %tmp['fps'])
        print('- Number of non-destruction reads = %02.0d' %tmp['ndr'])
        print('- Temperature of the detector = %04.1f C' %tmp['temp'])
        print('- Columns read = [%03.0d,%03.0d]' %(tmp['x_min'],tmp['x_max']))
        print('- Rows read    = [%03.0d,%03.0d]' %(tmp['y_min'],tmp['y_max']))
        print('##########################################')
        
        # Do not return anything
        return
        
    # =========================================================================
    def set_temp(self, degC):
        ''' -------------------------------------------------------------------
        Description:
            Function used to set camera temperature.
            
        Notes: 
            - This funct. has 1 sec sleep to ensure current value is set/read.
            
        Arguments:
            - degC    	: new temperature setpoint [in Celsius]
                        -> must be a number.
                        -> minimum value = -40
                        -> maximum value =  20
        Returns:
            - Status	: True if temperature set properly, False otherwise.	
        ------------------------------------------------------------------- '''
        try:
            # Verify if degC is a number
            if isinstance(degC,(int,float)):
                # Verify if degC is into the range of values allowed
                if -40 <= degC <= 20:
                    # Set the temperature
                    self.tmux("stemp %f" %(degC))
                    # Wait a second
                    time.sleep(1)
                    # Returns True: the temperature has been set properly. 
                    return True
                else:
                    # Print error message if self.verbose == True
                    if self.verbose: 
                        print('The temperature provided is out of range.')
                        print('  - Min temperature = -40 degree C.')
                        print('  - Max temperature =  20 degree C.')
                    # Returns False: the temperature has not been set.
                    return False
            else:
                # Print error message if self.verbose == True
                if self.verbose: 
                    print('The temperature provided must be a number.')
                # Returns False: the temperature has not been set. 
                return False
        except:
            # Print error message if self.verbose == True
            if self.verbose: 
                print('An error apears. The temperature has not beed set.')
            # Returns False: the temperature has not been set. 			
            return False
            
    # =========================================================================
    def set_fps(self, fps):
        ''' -------------------------------------------------------------------
        Description:
            Set the frame rate of the detector, reads the new fps setting 
            and report it in the sheared memory structure.
        
        Notes: 
            - This funct. has 1 sec sleep to ensure current value is set/read.
        
        Arguments:
            - fps		:  new fps setting [in Hz]
                        -> must be a number.
                        -> value constrains by the crop parameter.
                        -> value constrains by the exposure time + readout.
        Returns:
            - Status	: True if fps set properly, False otherwise
        ------------------------------------------------------------------- '''
        try:
            # Verify if fps is a number
            if isinstance(fps,(int,float)):
                # --- Verify if the frame rate provided is valide

                # -- Verify if the frame rate is compatible with the exp time
                # and readout time.
                # Compute the time needed to expose and read an image.
                TotalTime = np.floor(1./(self.get_tint()+self.get_readout()))
                if not fps <= TotalTime:
                    # Print error message if self.verbose == True
                    if self.verbose:
                        text  = 'The frame rate provided is not compatible ' 
                        text += 'with the current exposure and readout time.'
                        print(text)
                        print('  - Must be lower than: %04.0f Hz' %TotalTime)
                    # Returns False: the frame rate has not been set.
                    return False
                
                # -- Verify if the frame rate is compatible with the max frame
                # rate posible.
                # Get the maximum frame rate 
                max_fps = self.get_max_fps()   
                if not fps <= max_fps:
                    # Print error message if self.verbose == True
                    if self.verbose:
                        text  = 'The frame rate provided is not compatible ' 
                        text += 'with the maximum framerate.'
                        print(text)
                        print('  - Must be lower than: %04.0f Hz' %max_fps)
                    # Returns False: the frame rate has not been set.
                    return False
                
                # -- Verify if the frame rate is compatible with the min frame
                # rate posible.
                # The minimum frame rate can be found in the Cred2 user manual 
                # version 190109 section 7.1
                min_fps = 0.001   
                if not fps >= min_fps:
                    # Print error message if self.verbose == True
                    if self.verbose:
                        text  = 'The frame rate provided is not compatible ' 
                        text += 'with the minimum framerate.'
                        print(text)
                        print('  - Must be higher than: %04.2f Hz' %min_fps)
                    # Returns False: the frame rate has not been set.
                    return False
                
                # Set the frame rate
                self.tmux("sfps %f" %(fps))
                # Wait a second
                time.sleep(1)
                # Read the current frame rate and update TCParam.
                self.get_fps()
                # Returns True: the frame rate has been set properly. 
                return True			
            else:
                # Print error message if self.verbose == True
                if self.verbose: 
                    print('The frame rate provided must be a number.')
                # Returns False: the frame rate has not been set. 
                return False
        except:
            # Print error message if self.verbose == True
            if self.verbose: 
                print('An error apears. The frame rate has not beed set.')
            # Returns False: the frame rate has not been set. 			
            return False
    
    # =========================================================================
    def set_tint(self, tint):
        ''' -------------------------------------------------------------------
        Description:
            Set the exposure time of the detector, reads the new exposure time  
            setting and report it in the sheared memory structure.
        Notes: 
            - This funct. has 1 sec sleep to ensure current value is set/read.
            - The value you set may not be the actual value taken by the 
              camera; the camera automatically pushes your value to fit within 
              its bounds. However, the function update the TCParam with the 
              actual tint setting
        Arguments:
            - tint		: new exposure time setting [in second]
                        -> must be a number.
                        -> value constrains by the frame rate.
        Returns:
            - Status	: True if exposure time set properly, False otherwise.
        ------------------------------------------------------------------- '''
        try:
            # Verify if tint is a number
            if isinstance(tint,(int,float)):
                 
                # Compute the Total exposure time (Integration time + readout)
                T = tint + self.get_readout()
                
                # Verify if the exp time is compatible with the frame rate. 
                if not T < 1./self.get_fps():
                    # Print error message if self.verbose == True
                    if self.verbose:
                        tint_max = 1./self.get_fps()-self.get_readout()
                        text  = 'The exposure time provided is not compatible '
                        text += 'with the current frame rate.' 
                        print(text)
                        print('  - Must be lower than: %f sec' %tint_max)
                    # Returns False: the exposure time has not been set.
                    return False	
                
                # Verify if the exp time is compatible with the minimum tint.
                # The minimum exposure time (not degraded perf) is provided 
                # in the Cred2 user manual version 190109 section 7.1 
                tint_min = 0.00005
                if not tint >= tint_min:
                    # Print error message if self.verbose == True
                    if self.verbose: 
                        text  = 'The exposure time provided is not compatible '
                        text += 'with the minimum integration time.'
                        print(text) 
                        print('  - Must be higer than: %f sec' %tint_min)
                    # Returns False: the exposure time has not been set.
                    return False	
                 
                # Set the exposure time
                self.tmux("stint %f" %(tint))
                # Wait a second
                time.sleep(1)
                # Read the current exposure time and update TCParam.
                self.get_tint()
                # Returns True: the frame rate has been set properly. 
                return True
            
            else:
                # Print error message if self.verbose == True
                if self.verbose: 
                    print('The exposure time provided must be a number.')
                # Returns False: the exposure time has not been set. 
                return False
        except:
            # Print error message if self.verbose == True
            if self.verbose: 
                print('An error apears. The exposure time has not beed set.')
            # Returns False: the exposure time has not been set. 			
            return False
    
    # =========================================================================
    def change_setup(self, setup_num):
        ''' -------------------------------------------------------------------
        Description:
            Set the exposure time and FPS based on pre-defined setting.
        Notes: 
            - If exposure time or FPS settings fail, both revert to previous setting.
        Arguments:
            - setup_num      : pre-defined setting
                        -> must be a number (1-15).
        Returns:
            - Status    : True if exposure time and FPS set properly, False otherwise.
        ------------------------------------------------------------------- '''

        init_tint = self.get_tint
        init_fps = self.get_fps

        new_tint = self.setup_tint[setup_num-1]
        new_fps = self.setup_fps[setup_num-1]

        if new_tint < init_tint:
            tint_check = self.set_tint(new_tint)
            if not tint_check: return False
            fps_check = self.set_fps(new_fps)
            if fps_check: return True
            self.set_tint(init_tint)
            return False
        else:
            fps_check = self.set_fps(new_fps)
            if not fps_check: return False
            tint_check = self.set_tint(new_tint)
            if tint_check: return True
            self.set_fps(init_fps)
            return False

    # =========================================================================
    def set_ndr(self, ndr):
        ''' -------------------------------------------------------------------
        Description:
            Function used to set the number of non destructive read.
        Notes: 
            - This funct. has 1 sec sleep to ensure current value is set/read.
        
        Arguments:
            - ndr    	: number of non destructive read
                        -> must be a number.
                        -> minimum value = 1
                        -> maximum value = 64
        Returns:
            - Status	: True if ndr set properly, False otherwise.	
        ------------------------------------------------------------------- '''
        try:
            # Verify if the ndr value provided is a number
            if isinstance(ndr,(int,float)):
                # Verify if ndr is into the range of values allowed
                if 1 <= ndr <= 64:
                    # Set the ndr
                    self.tmux("sNDR %f" %(ndr))
                    # Wait a second
                    time.sleep(1)
                    # Read the current ndr and update TCParam.
                    self.get_ndr()
                    # Returns True: the number of ndr has been set properly. 
                    return True
                else:
                    # Print error message if self.verbose == True
                    if self.verbose: 
                        print('The ndr value provided is out of range.')
                        print('  - Min = 1')
                        print('  - Max = 64')
                    # Returns False: the ndr has not been set.
                    return False
            else:
                # Print error message if self.verbose == True
                if self.verbose: 
                    print('The number of ndr provided must be a number.')
                # Returns False: the temperature has not been set. 
                return False
        except:
            # Print error message if self.verbose == True
            if self.verbose: 
                print('An error apears. The ndr has not beed set.')
            # Returns False: the ndr has not been set. 			
            return False

    # =========================================================================
    def set_subim_parameters(self, SubIm_Param):
        ''' -------------------------------------------------------------------
        Description:
            Function to set camera crop mode.
        
        Notes: 
            - This function takes > 12 seconds to complete.
            - It will block execution until it is done.
            - If the user provide a custom sub window parameter, they will 
              automatically converted to integer.
        
        Arguments:
            - Crop_Param: This argument can be: 
                            - A vector containing 4 values:
                                - SubIm_Param[0] = x_min
                                - SubIm_Param[1] = x_max
                                - SubIm_Param[2] = y_min
                                - SubIm_Param[3] = y_max
                              Those parameters are in pixels.
                              They define the sub frame.
                              - A string:
                                - if in ['full','full_frame','full frame']
                                  set the detector in full frame mode.
                                - if in ['64x64 centered','64c']
                                  set a sub window of 64x64 pixels centered
                                - if in ['128x128 centered','128c']
                                  set a sub window of 128x128 pixels centered
                                - if in ['256x256 centered','256c']
                                  set a sub window of 256x256 pixels centered
                                - if in ['512x512 centered','512c']
                                  set a sub window of 512x512 pixels centered		
        Returns:
            - Status	: True if crop parameters set properly, False otherwise

        ------------------------------------------------------------------- '''
        # --- Verify if SubIm_Param argument is valid. Return False if not.
        
        # Return False if unexpected kind.
        if not isinstance(SubIm_Param,(str,list,tuple,np.ndarray)):
            if self.verbose: 
                print('Error: The (sub) image parameter provided is not valid')
            return False
        
        # If the user provide a pre-defined crop mode, update SubIm_Param.
        if isinstance(SubIm_Param,str):
            # Case #01: Full Frame mode
            if SubIm_Param.lower() in ['full','full_frame','full frame']: 
                SubIm_Param = [0,639,0,511]
            elif SubIm_Param.lower() in ['64x64 centered','64c']:
                SubIm_Param = [288,351,224,287]
            elif SubIm_Param.lower() in ['128x128 centered','128c']: 
                SubIm_Param = [256,383,192,319]
            elif SubIm_Param.lower() in ['256x256 centered','256c']: 
                SubIm_Param = [192,447,128,383]
            elif SubIm_Param.lower() in ['512x512 centered','512c']: 
                SubIm_Param = [64,575,0,511]
            elif SubIm_Param.lower() in ['64x64 scf2','64scf2']:
                SubIm_Param = [224,287,192,255]				
            # Return False if pre-defined sub image required is unknown
            else:
                if self.verbose:
                    text = 'The pre-defined sub image required is unknown.' 
                    print('Error: ' + text)
                return False
        
        # Verify if the shape of the custom SubIm parameter provided is valid.
        if isinstance(SubIm_Param,(list,tuple,np.ndarray)):
            if not np.shape(SubIm_Param) == (4,):
                if self.verbose:
                    text = 'The shape of the parameter provided is not valid' 
                    print('Error: ' + text)
                return False
            else:
                # Extract the sub image parameters and convert them as integer.
                x_min = np.int(SubIm_Param[0])
                x_max = np.int(SubIm_Param[1])
                y_min = np.int(SubIm_Param[2])
                y_max = np.int(SubIm_Param[3])
                
                # Verify if the sub image parameters are valid.
                
                # Initialize a flag 
                Flag  = True
                
                # Verify if x_min is valid
                if not (x_min%32 == 0)  or not (0 <= x_min < 639):
                    if self.verbose:
                        print('x_min must be a multiple of 32 and in [0,640[')
                    Flag = False
                # Verify if y_min is valid
                if not (y_min%4 == 0)   or not (0 <= y_min < 511):
                    if self.verbose:
                        print('y_min must be a multiple of 4 and in [0,512[')
                    Flag = False
                # Verify if x_max is valid
                if not (x_max%32 == 31) or not (0 < x_max <= 639):
                    if self.verbose:
                        print('x_max must be a multiple of 32 and in [0,640[')
                    Flag = False
                # Verify if y_min is valid
                if not (y_max%4 == 3)   or not (0 < y_max <= 511):
                    if self.verbose:
                        print('y_max must be a multiple of 4 and in [0,512[')
                    Flag = False
                # Verify if x_max > x_min
                if not (x_max > x_min):
                    if self.verbose:
                        print('x_max must be higher than x_min')
                    Flag = False
                # Verify if y_max > y_min
                if not (y_max > y_min):				
                    if self.verbose:
                        print('y_max must be higher than y_min')
                    Flag = False
                # Return False if one or several parameter(s) is/are not valid.
                if not Flag: return False
                		
        # --- Verify if FPS will still be valid after crop.
        
        # Compute the new dimensions of the (sub) image
        tmp = [np.int(np.abs(x_max-x_min)),np.int(np.abs(y_max-y_min))]
        
        # Get the max FPS possible to set assuming the new dimensions of the 
        # (sub) image.
        max_fps = self.get_max_fps(dimensions=tmp)
        # Get the current fps
        current_fps = self.get_fps()
        
        # Verify if the current fps can be use with the crop image required.
        if current_fps > max_fps:
            if self.verbose:
                print('Error: The current frame rate is too high.')
                print('Adjust the frame rate before to crop the image.')
                text  = 'The maximum frame rate possible to set for crop image'
                text += 'required is: %f' %max_fps 
                print(text)
            return False
        
        # --- Apply the sub image parameters required by the user.
        
        # -- Stop image aquisition 
        if self.verbose: print('-- Stopping Capture')
        self.tmux("stop")
        time.sleep(2)
        
        # -- Turn crop mode on or off depending of user request
        if self.verbose: print('-- Editing Crop Settings')
        # Turn it off if full frame mode required
        if SubIm_Param == [0,639,0,511]: self.tmux("cropOFF")
        # Trun it on if sub image required 
        else: self.tmux("cropON")
        time.sleep(2)
        
        # -- Update crop parameters
        self.tmux("scrop_cols %d %d" %(x_min,x_max)) 
        time.sleep(2)
        self.tmux("scrop_rows %d %d" %(y_min,y_max)) 
        time.sleep(2)
        
        # -- Restart aquisition
        if self.verbose: print('-- Starting Capture Temporarily')
        self.tmux("start")
        time.sleep(5)
        if self.verbose: print('-- Stopping Capture To Flush')
        self.tmux("stop")
        time.sleep(2)
        if self.verbose: print('-- Restarting Capture')
        self.tmux("start")
        time.sleep(5) 
        if self.verbose: print('-- Full Crop Mode Set')			
        
        # Re-load python shm structure to match new settings
        if self.verbose: print('-- Reinitializing shm structure')
        self.__init__(fname=self.fname)
        
        # Update shm elements
        self.get_all_parameters()
        
        # Update image dim parameters
        tmp = self.get_image_shape()
        
        return True
        
    # =========================================================================
    def take_images(self, nb_im = 1, reduced = False):
        ''' -------------------------------------------------------------------
        Description:
            Function to get one or several image(s) with the time stamp for
            each frame and the detector parameters during aquisition.
        Notes: 
            - The parameters are not updated in this function. 		
        Arguments:
            - nb_im		: number of images expected by the user.
                        -> must be a number.
                        -> will be automatically converted as an int
                        -> min = 1.
                        -> max = 1000.
        Returns:
        Nominal Case: 
            - im_cube	: Cube of image registered by the detector.
            - time_vec	: vector of time values associated to each image.
            - TCParam	: Parameter of the detector at the end of aquisition.
        If Reduced  :
            - redu_im   : image reduced. 
        In case of error:
            - False
        ------------------------------------------------------------------- '''
        #try:
        if True:
            # Verify if the dimensions of the image are known 
            if self.dim_x == -1: self.get_image_shape()
            
            # Update the local parameters    
            self.updateTCParam()            
            
            # Verify if the number of image(s) is a number
            if isinstance(nb_im,(int,float)):
                # Convert nb_im as an int if needed 
                if isinstance(nb_im,(float)): nb_im = np.int(nb_im)
            else:
                # Print error message if self.verbose == True
                if self.verbose: 
                    print('The number of image must be a number')
                # Returns False: the images have not been acquired.
                return False, False, False
            
            # Case #1: user required reduced images.                    
            if reduced:
                # Verify if nb_im is into the range of values allowed
                if nb_im == 1:
                    tmp_im = self.get_data(check=True) - self.Calib_im
                    # Return the image, the associated time and the Param
                    return tmp_im, time.time(), self.TCParam
                # The size of the cube of image cannot be biger than 
                # 327,680,000 bytes. It correspond to 1000 full frames
                elif nb_im <= 1000.:
                    for i in np.arange(nb_im):
                        if i == 0: 
                            im_cube    = np.zeros([nb_im,self.dim_x,self.dim_y])
                            time_vec   = np.zeros([nb_im])
                        # Acquire an image
                        im_cube[i,:,:] = self.get_data(check=True)
                        # Get time associated to the image 
                        time_vec[i]    = time.time()
                    # Reduce the image
                    im_redu = np.median(im_cube,0) - self.Calib_im
                    # Return the images, the associated times and the Param
                    return im_redu, time_vec, self.TCParam

                else:
                    # Print error message if self.verbose == True
                    if self.verbose: 
                        nb_im_max = 1000.
                        print('The number of image is out of range.')
                        print('  - Min = 1')
                        print('  - Max = 1000')
                    # Returns False: the images have not been acquired.
                    return False, False, False

            # Case #2: user does not required reduced images.                    
            else:
                # Verify if nb_im is into the range of values allowed
                if nb_im == 1:
                    tmp_im = self.get_data(check=True)
                    # Update the local parameters    
                    self.updateTCParam()
                    # Return the image, the associated time and the Param
                    return tmp_im, time.time(), self.TCParam
                # The size of the cube of image cannot be biger than 
                # 327,680,000 bytes. It correspond to 1000 full frames
                elif nb_im*self.dim_x*self.dim_y <= 327680000*3:
                    for i in np.arange(nb_im):
                        if i == 0: 
                            im_cube = np.zeros([nb_im,self.dim_x,self.dim_y])
                            time_vec = np.zeros([nb_im])
                        im_cube[i,:,:] = self.get_data(check=True)
                        time_vec[i]    = time.time()

                    # Return the images, the associated times and the Param
                    return im_cube, time_vec, self.TCParam
                else:
                    # Print error message if self.verbose == True
                    if self.verbose: 
                        nb_im_max = np.floor(327680000/(self.dim_x*self.dim_y))
                        print('The number of image is out of range.')
                        print('  - Min = 1')
                        print('  - Max = %d' %nb_im_max )
                    # Returns False: the images have not been acquired.
                    return False, False, False

        #except:
        #    # Print error message if self.verbose == True
        #    if self.verbose: 
        #        print('An error apears. The acquisition failed.')
        #    # Returns False: Failed to acquire images. 			
        #    return False,False,False
    					
    # =========================================================================
    def save_images(self, nb_im=1, nb_cube=1, filename='',overwrite = False):
        ''' -------------------------------------------------------------------
        Description:
            Function to save Cred2 images.
            
        Notes: 
            - The parameters of the detector are not saved for the moment.  
        
        Arguments:
            - nb_im		: (optional) Number of images per cube.
                        -> must be a number.
                        -> will be automatically converted as an int
                        -> min = 1.
                        -> max = 1000.
            - nb_cube	: (optional) Number of cube of images to save.
                        -> must be a number.
                        -> will be automatically converted as an int
                        -> min = 1.
                        -> max = 100.
            - filename  : (optional) common part of the name of all files saved
                          by the function. If not provided filename will be  
                          based on time.
                        -> Must be a string.
                        -> Cannot contains the following characters:
                            ! ? / @ # $ % ^ & * ( ) > < } { + ~ `
            - overwire	: (optional) Boolean to overwrite data
            
        Returns:
        Nominal Case: 
            - path		: path and part of the name common to all files saved.
        In case of error:
            - False
        ------------------------------------------------------------------- '''
        # try:
        if True:
            # Verify if parameters have been updated
            if self.TCParam['tint'] == 0.: self.get_all_parameters()
            # Get the path where images will be saved.
            Path, tmp = get_path('Cred2')
            
            # If no filename provided, use the one provide by get_path().
            if filename == '': filename = tmp
            # If the user provided a filename, verify if valid.
            else:
                # Verify if filename is a string
                if not isinstance(filename,(str)):
                    if self.verbose: 
                        print('The filename must be a string.')
                    return False
                    
                # Remove unexpected / at the beginning if needed
                if filename[0] == '/': filename = filename[1:]
                
                # Verify if filename contains only valid characters
                tmp = set(filename)
                if not tmp.intersection(set('!?/@#$%^&*()><}{+~`')) == set():
                    if self.verbose: 
                        print('The filename contains unexpected character(s).')
                    return False

            # Verify if filename has already been used
            if not overwrite:
                if os.path.isfile(Path + filename + '_data_00.fits'):
                    if self.verbose: 
                        print('The filename provided has alredy been used.')
                    return False						
                    
            # Verify if the number of cube(s) is a number
            if isinstance(nb_cube,(int,float)):
                # Convert nb_cube as an int if needed 
                if isinstance(nb_im,(float)): nb_cube = np.int(nb_cube)
                # Verify if nb_cube is into the range of values allowed 
                if not 1 <= nb_cube <= 100:
                    if self.verbose: 
                        print('The number of cube must be in [1,100].')
                    return False								
            else:
                if self.verbose: 
                    print('The number of cubes must be a number.')
                return False			
            
            # If number of cube and filename valid, start aquisition.				
            for i in np.arange(nb_cube):
                # Take a cube of images
                im,timestamps,info = self.take_images(nb_im)
                # Verify if aquisition succed.
                if isinstance(im,bool):
                    if self.verbose: 
                        print('An error apears when aquiered images.')
                    return False

                # -- Save parameters
                # Define the name of the file
                fullname = Path + filename + '_param_%02d.fits' %(i)
                
                # -- Save data
                # Define the name of the file
                fullname = Path + filename + '_data_%02d.fits' %(i)
                # Create a Header Data Unit (HDU) based on the data to save.
                hdu = fits.PrimaryHDU(im)
                # Extract the header
                hdr = hdu.header
                # add an empty line to the header
                hdr.append(('','',''), end=True)
                time_B = timestamps if nb_im == 1 else timestamps[0]
                time_E = timestamps if nb_im == 1 else timestamps[-1] 
                # Add time associated to the first image to the header
                tmp_cmt = 'Time when first im acquired (end)  - dbl - sec'
                hdr.append(('FIRST_T',time_B,tmp_cmt), end=True)
                # Add time associated to the last image to the header
                tmp_cmt = 'Time when last im acquired  (end)  - dbl - sec'
                hdr.append(('LAST_T' ,time_E,tmp_cmt), end=True)
                # Query telecope keywords using keyheader
                hdr = self.pullKeys(hdr)
                # Add the CRED2 parameters to the header
                hdr = self.header(hdr)
                # Add Keck II metrology to the header
                hdu.header = met2.Keck_II_Metrology_header(hdr)

                # Save the image
                hdu.writeto(fullname, overwrite = overwrite)
                
                # -- Save time
                # Define the name of the file
                fullname = Path + filename + '_time_%02d.fits' %(i)
                # Create a Header Data Unit (HDU) based on the data to save.
                hdu = fits.PrimaryHDU(timestamps) 
                # Save the timestamps associated to the image
                hdu.writeto(fullname, overwrite = overwrite)		
                
            return Path,filename			
            
        # except:
        #    # Print error message if self.verbose == True
        #    if self.verbose: 
        #        print('An error apears. The acquisition failed.')
        #    # Returns False: Failed to acquire images. 			
        #    return False

    # =========================================================================
    def open(self, path, filename, cube_number = 0):
        ''' -------------------------------------------------------------------
        Description: 
        
        Notes: 
        
        Arguments:
        
        Returns:
        
        ------------------------------------------------------------------- '''        
        # TODO Verify if cube_number and path are valid.
        
        # Prepare path where data are contained
        datapath  = path + filename + '_data_%02d.fits' %(cube_number)
        # Prepare path where timestamps are contained
        timepath  = path + filename + '_time_%02d.fits' %(cube_number)

        # Read the image cube
        im  = fits.open(datapath)
        hdr = im[0].header
        im  = im[0].data
        
        # Read the associated time stamps
        timestamps = fits.open(timepath)
        timestamps = timestamps[0].data
        
        P = {}
        P['tint']  = hdr['TC_TINT']
        P['fps']   = hdr['TC_FPS' ]
        P['ndr']   = hdr['TC_NDR' ]
        P['x_min'] = hdr['TC_XMIN']
        P['x_max'] = hdr['TC_XMAX']
        P['y_min'] = hdr['TC_YMIN']
        P['y_max'] = hdr['TC_YMAX']
        P['temp']  = hdr['TC_TEMP']
        
        # Return the cube of image(s), the timestamps associated and the 
        # parameters of the detector when image aquired.
        
        return im, timestamps, P
        
    # =========================================================================
    def pullKeys(self,hdr,confile = KEYCONFPTH):
        ''' -------------------------------------------------------------------
        Description: Function for updating a fits header with keywords from 
                     other services
        
        Notes: 
        - Uses the 'keyheader' script to query the services.
        - Appends entries to the END of the provided header
        
        Arguments:
        - hdr     (fits.header.Header) a fits header to which the new values 
        will be appended.
        - confile (str) full path to the conf file defining which keywords to 
        pull.
        Returns:
        - hdr     (fits.header.Header) the updated fits header.
        ------------------------------------------------------------------- '''
        
        res = sp.run(["keyheader","-t","now","-c",confile,"-m"],stdout=sp.PIPE,stderr=sp.PIPE) 
        if res.returncode != 0:
            # An error occurred when calling keyheader. 
            #This is where error handling would occur (throw error, etc.)
            # For now, just return hdr immediately
            return hdr
        
        hdStr = res.stdout.decode().split('\n')
        for key in hdStr:
            key = key.split('\t')
            if key[0].lower() == 'double':
                key[2] = float(key[2])
            tup = tuple(key[1:])
            hdr.append(tup, end=True)
        return hdr

    # =========================================================================
    def updateTCParam(self,):
        ''' -------------------------------------------------------------------
        Description: 
        - Function used to update the local TC parameters.
        Notes: 
        - None.
        Arguments:
        - None.
        Returns:
        - None.
        ------------------------------------------------------------------- '''
        # Get data contains into the parameter shm
        self.Param = self.Shm_P.get_data()
        # Update the local copy of the parameters
        self.TCParam['tint' ] = self.Param[self.Str_P['tint'  ]] 
        self.TCParam['fps'  ] = self.Param[self.Str_P['fps'   ]] 
        self.TCParam['ndr'  ] = self.Param[self.Str_P['ndr'   ]] 
        self.TCParam['x_min'] = self.Param[self.Str_P['x_min' ]] 
        self.TCParam['x_max'] = self.Param[self.Str_P['x_max' ]] 
        self.TCParam['y_min'] = self.Param[self.Str_P['y_min' ]] 
        self.TCParam['y_max'] = self.Param[self.Str_P['y_max' ]] 
        self.TCParam['temp' ] = self.Param[self.Str_P['temp'  ]]
        self.dim_y = np.int(self.TCParam['x_max'] - self.TCParam['x_min'] + 1)
        self.dim_x = np.int(self.TCParam['y_max'] - self.TCParam['y_min'] + 1)
        # Does not return anything
        return

    # =========================================================================
    def get_last_parameters(self,):
        ''' -------------------------------------------------------------------
        Description: 
        - This function return the parameters contain into the sheared memory.
        Notes: 
        - These parameters may not be updated.
        Arguments:
        - None.
        Returns:
        - TCParam.
        ------------------------------------------------------------------- '''
        # updated the local parameters based on parameters saved into the shm.
        updateTCParam(self,)
        # Return the Tracking camera parameters
        return self.TCParam

    # =========================================================================
    def header(self,hdr):
        ''' -------------------------------------------------------------------
        Description: 
        - Function used to update the local TC parameters.
        Notes: 
        - None.
        Arguments:
        - None.
        Returns:
        - None.
        ------------------------------------------------------------------- '''
        #
        P = np.zeros([np.size(self.names)+1])
        P[0] = self.Param[self.Str_P['tint' ]]
        P[1] = self.Param[self.Str_P['fps'  ]]
        P[2] = self.Param[self.Str_P['ndr'  ]]
        P[3] = self.Param[self.Str_P['x_min']]
        P[4] = self.Param[self.Str_P['x_max']]
        P[5] = self.Param[self.Str_P['y_min']]
        P[6] = self.Param[self.Str_P['y_max']]
        P[7] = self.Param[self.Str_P['temp' ]]
        P[8] = np.floor(self.Param[self.Str_P['time' ]])
        # Add Tracking cam parameters to the provided header
        hdr.append(('','',''), end=True)
        hdr.append(('','- Cred2 Parameters -',''), end=True)
        hdr.append(('','',''), end=True)
        hdr.append(('TC_TINT' ,P[0],'Tracking Camera exposure time      - dbl - sec' ), end=True)
        hdr.append(('TC_FPS'  ,P[1],'Number of frame read per second    - dbl - fps' ), end=True)
        hdr.append(('TC_NDR'  ,P[2],'Number of non-destructive read     - int - None'), end=True)
        hdr.append(('TC_XMIN' ,P[3],'Tracking Camera first column read  - int - pix' ), end=True)
        hdr.append(('TC_XMAX' ,P[4],'Tracking Camera last column read   - int - pix' ), end=True)
        hdr.append(('TC_YMIN' ,P[5],'Tracking Camera first row read     - int - pix' ), end=True)
        hdr.append(('TC_YMAX' ,P[6],'Tracking Camera last row read      - int - pix' ), end=True)
        hdr.append(('TC_TEMP' ,P[7],'Temperature of the Tracking Camera - int - degC'), end=True)
        hdr.append(('TC_TIME' ,P[8],'Time associated to the last update - dbl - sec' ), end=True)
        # return the updated version of the header
        return hdr

    # =========================================================================
    def take_calibration_images(self, nb_im=100, overwrite = True):
        ''' -------------------------------------------------------------------
        Description:
            Function to save Cred2 calibration images.
        Arguments:
            - nb_im		: (optional) Number of images per cube.
                        -> must be a number.
                        -> will be automatically converted as an int
                        -> min = 1.
                        -> max = 1000.
            - filename  : (optional) common part of the name of all files saved
                          by the function. If not provided filename will be  
                          based on time.
                        -> Must be a string.
                        -> Cannot contains the following characters:
                            ! ? / @ # $ % ^ & * ( ) > < } { + ~ `
            - overwire	: (optional) Boolean to overwrite data
            
        Returns:
        Nominal Case: 
            - path		: path and part of the name common to all files saved.
        In case of error:
            - False
        ------------------------------------------------------------------- '''
        #try:
        if True:
            # Update TCParam
            self.updateTCParam()
            # Verify if parameters have been updated
            if self.TCParam['tint'] == 0.: self.get_all_parameters()
            # Get the path where images will be saved.
            Path, tmp = get_path('Cred2/Calib')

            # Define the filename
            filename  = 'Tint_' 
            filename += '%08d' %(np.round(self.TCParam['tint'],6)*1e6)
            filename += 'us_NDR_' + '%02d' %(np.int(self.TCParam['ndr']))

            # Temperature of the detector has to be < -35 deg C.
            if self.TCParam['temp'] > -35:
                #if self.verbose:
                print('The temperature of the detector must be < -35C.')
                #return False
            
            # Detector must be in full frame mode -- TODO modify it
            if self.get_image_shape() != [512,640]:
                if self.verbose:
                    print('The detector must be in full frame mode.')
                return False
            
            # Take a cube of images
            im,timestamps,info = self.take_images(nb_im)
            # Compute the median of the calibration images
            if nb_im > 1: im = np.median(im,0)
            # Verify if aquisition succed.
            if isinstance(im,bool):
                if self.verbose: 
                    print('An error apears when aquiered images.')
                return False
                
            # -- Save data
            # Define the name of the file
            fullname = Path + filename + '.fits'
            # Create a Header Data Unit (HDU) based on the data to save.
            hdu = fits.PrimaryHDU(im)
            # Extract the header
            hdr = hdu.header
            # add an empty line to the header
            hdr.append(('','',''), end=True)
            time_B = timestamps if nb_im == 1 else timestamps[0]
            time_E = timestamps if nb_im == 1 else timestamps[-1]
            # Add time associated to the first image to the header
            tmp_cmt = 'Time when first im acquired (end)  - dbl - sec'
            hdr.append(('FIRST_T', time_B ,tmp_cmt), end=True)
            # Add time associated to the last image to the header
            tmp_cmt = 'Time when last im acquired  (end)  - dbl - sec'
            hdr.append(('LAST_T' , time_E ,tmp_cmt), end=True)
            # Query telecope keywords using keyheader
            hdr = self.pullKeys(hdr)
            # Add the CRED2 parameters to the header
            hdr = self.header(hdr)
            # Add Keck II metrology to the header
            hdu.header = met2.Keck_II_Metrology_header(hdr)

            # Save the image
            hdu.writeto(fullname, overwrite = overwrite)	
            
            # Update local calibration parameters
            self.Calib_im   = im
            self.Calib_tint = self.TCParam['tint']
            self.Calib_ndr  = self.TCParam['ndr']

            self.Calib_time = timestamps if nb_im == 1 else timestamps[0]

            return Path,filename			
            
        #except:
        #    # Print error message if self.verbose == True
        #    if self.verbose: 
        #        print('An error apears. The acquisition failed.')
        #    # Returns False: Failed to acquire images. 			
        #    return False

    # =========================================================================
    def load_calibration_images(self,):
        ''' -------------------------------------------------------------------
        Description:
            Load in the local memory the calibration images associated to the 
            current configuration of the detector.

        Arguments:
            - None
            
        Returns: 
            - None
        ------------------------------------------------------------------- '''
        # Update TCParam
        self.updateTCParam()
        # Verify if parameters have been updated
        if self.TCParam['tint'] == 0.: self.get_all_parameters()
        # Get the path where calibration images are saved.
        Path, tmp = get_path('Cred2/Calib')
        # Define the filename based on the current TC parameters
        filename  = 'Tint_' 
        filename += '%08d' %(np.round(self.TCParam['tint'],6)*1e6)
        filename += 'us_NDR_' + '%02d' %(np.int(self.TCParam['ndr']))

        try:
            # Try to read the file where calibration data are saved.
            hdu             = fits.open(Path + filename + '.fits')
            # Extract the header
            hdr             = hdu[0].header
            # Extract the number of images
            #self.Calib_nb   = np.int(hdr['NAXIS3'])
            # Extract the data
            self.Calib_im   = hdu[0].data
            # Extract the time when first calibration images acquired
            self.Calib_time = np.double(hdr['FIRST_T'])
            # Extract tint associated to the calibration images
            self.Calib_tint = np.double(hdr['TC_TINT'])
            # Extract ndr associated to the calibration images
            self.Calib_ndr  = np.double(hdr['TC_NDR' ])
        except:
            # No data saved today (UT) 
            print('\033[91m Calibration data Not valid.\033[0m')
            # Reset all Calib parameters
            self.Calib_im   = np.zeros([self.dim_x,self.dim_y])
            self.Calib_time = 0.
            self.Calib_tint = 0.
            self.Calib_ndr  = 0.         

    # =========================================================================
    def get_calibration_images(self,):
        ''' -------------------------------------------------------------------
        Description:
            Return the calibration images associated to the current setup if
            valid.

        Arguments:
            - None
            
        Returns: 
            if calibration image are valid:
            - Calib images   + number of images + True 
            if calibration image are not valid:
            - Array of zeros + number of images + False 
        ------------------------------------------------------------------- '''
        # Case #1: if calibration data valid, return calib images and True
        if self.calibration_valid(): 
            return self.Calib_im, True
        # Case #2: if not valid,
        else:
            # Load Calibration images
            self.load_calibration_images()
            # Case 2-A: if still not valid return array of zeros and False
            if self.Calib_ndr == 0.: 
                return self.Calib_im, False
            # Case 2-B: if valid return calib images and True
            else: 
                return self.Calib_im, True

    # =========================================================================
    def calibration_valid(self,):
        ''' -------------------------------------------------------------------
        Description:
            Verify if calibration data loaded are valid.

        Arguments:
            - None
            
        Returns: 
            - True : if calibration data loaded are valid.
            - False: if not
        ------------------------------------------------------------------- '''
        # Update TCParam
        self.updateTCParam()
        # Prepare a Flag
        Flag = True
        # Check if time associated to calibration image match the current one.
        if   self.Calib_tint != self.TCParam['tint']: Flag = False
        # Check if ndr associated to calibration image match the current one.
        elif self.Calib_ndr != self.TCParam['ndr']: Flag = False
        # Check if the temperature of the TC is lower than - 35 deg C
        elif self.TCParam['temp'] > -35: 
            if self.verbose: print('Temperature >-35degC')
            # Flag = False
        # Check if detector in full frame mode
        elif  [self.dim_x,self.dim_y] != [512,640]: Flag = False
        # if reach this point the calibration data loaded are valid
        else: Flag = True
        # update calib parameters if not valid.
        if not Flag:
            # Reset all Calib parameters
            self.Calib_im   = np.zeros([self.dim_x,self.dim_y])
            self.Calib_time = 0.
            self.Calib_tint = 0.
            self.Calib_ndr  = 0.  
        return Flag

    # =========================================================================
    def print_calibration_age(self,):
        if self.calibration_valid():
            # Compute in sec the time spend since calib images acquired.
            tmp = time.time() - self.Calib_time
            # Prepare the text to print
            s =  np.floor(tmp)%60
            m = (np.floor(tmp-s)%3600)/60
            h =  np.floor(tmp-m*60.-s)/3600 
            print('Time elapsing since calibration image acquisition:')
            print(' - %02d hours %02d minutes %02d seconds.' %(h,m,s))
        else:
            print('Calibration images currently load are not valid.')
            


    # =========================================================================
    def save_reduced_image(self,nb_im=100,nb_cube=1,filename='',overwrite = False):
        ''' -------------------------------------------------------------------
        Description:
            Function to save Cred2 images reduced by using calibration images.  
        
        Arguments:
            - nb_im		: (optional) Number of images per cube.
                        -> must be a number.
                        -> will be automatically converted as an int
                        -> min = 1.
                        -> max = 1000.
            - nb_cube	: (optional) Number of cube of images to save.
                        -> must be a number.
                        -> will be automatically converted as an int
                        -> min = 1.
                        -> max = 100.
            - filename  : (optional) common part of the name of all files saved
                          by the function. If not provided filename will be  
                          based on time.
                        -> Must be a string.
                        -> Cannot contains the following characters:
                            ! ? / @ # $ % ^ & * ( ) > < } { + ~ `
            - overwire	: (optional) Boolean to overwrite data
            
        Returns:
        Nominal Case: 
            - path		: path and part of the name common to all files saved.
        In case of error:
            - False
        ------------------------------------------------------------------- '''
        try:
            # Verify if parameters have been updated
            if self.TCParam['tint'] == 0.: self.get_all_parameters()
            # Verify if calibration images are valid
            if not self.calibration_valid(): 
                if self.verbose: 
                    print('Calibration images are not valid.')
                return False
            # Get the path where images will be saved.
            Path, tmp = get_path('Cred2')
            
            # If no filename provided, use the one provide by get_path().
            if filename == '': filename = tmp
            # If the user provided a filename, verify if valid.
            else:
                # Verify if filename is a string
                if not isinstance(filename,(str)):
                    if self.verbose: 
                        print('The filename must be a string.')
                    return False
                    
                # Remove unexpected / at the beginning if needed
                if filename[0] == '/': filename = filename[1:]
                
                # Verify if filename contains only valid characters
                tmp = set(filename)
                if not tmp.intersection(set('!?/@#$%^&*()><}{+~`')) == set():
                    if self.verbose: 
                        print('The filename contains unexpected character(s).')
                    return False

            # Verify if filename has already been used
            if not overwrite:
                if os.path.isfile(Path + filename + '_redu_00.fits'):
                    if self.verbose: 
                        print('The filename provided has already been used.')
                    return False						
                    
            # Verify if the number of cube(s) is a number
            if isinstance(nb_cube,(int,float)):
                # Convert nb_cube as an int if needed 
                if isinstance(nb_im,(float)): nb_cube = np.int(nb_cube)
                # Verify if nb_cube is into the range of values allowed 
                if not 1 <= nb_cube <= 100:
                    if self.verbose: 
                        print('The number of cube must be in [1,100].')
                    return False								
            else:
                if self.verbose: 
                    print('The number of cubes must be a number.')
                return False			
            
            # If number of cube and filename valid, start aquisition.				
            for i in np.arange(nb_cube):
                # Take a cube of images
                im,timestamps,info = self.take_images(nb_im,True)
                # Verify if aquisition succed.
                if isinstance(im,bool):
                    if self.verbose: 
                        print('An error apears when aquiered images.')
                    return False
                
                # -- Save data
                # Define the name of the file
                fullname = Path + filename + '_redu_%02d.fits' %(i)
                # Create a Header Data Unit (HDU) based on the data to save.
                hdu = fits.PrimaryHDU(im)
                # Extract the header
                hdr = hdu.header
                # add an empty line to the header
                hdr.append(('','',''), end=True)
                time_B = timestamps if nb_im == 1 else timestamps[0]
                time_E = timestamps if nb_im == 1 else timestamps[-1]
                # Add time associated to the first image to the header
                tmp_cmt = 'Time when first im acquired (end)  - dbl - sec'
                hdr.append(('FIRST_T',time_B ,tmp_cmt), end=True)
                # Add time associated to the last image to the header
                tmp_cmt = 'Time when last im acquired  (end)  - dbl - sec'
                hdr.append(('LAST_T' ,time_E,tmp_cmt), end=True)
                # Query telecope keywords using keyheader
                hdr = self.pullKeys(hdr)
                # Add the CRED2 parameters to the header
                hdr = self.header(hdr)
                # Add Keck II metrology to the header
                hdu.header = met2.Keck_II_Metrology_header(hdr)

                # Save the image
                hdu.writeto(fullname, overwrite = overwrite)		
                
            return Path,filename			
            
        except:
            # Print error message if self.verbose == True
            if self.verbose: 
                print('An error apears. The acquisition failed.')
            # Returns False: Failed to acquire images. 			
            return False

    # =========================================================================
    def print_config_info(self,Name = 'All'):
        ''' -------------------------------------------------------------------
        Description:
            This fonction print into the terminal all tracking camera 
            predifined configurations available.  
        
        Arguments:
            None
            
        Returns:
            None
        ------------------------------------------------------------------- '''
        # If user provided a config Name, check if valid. 
        if Name != 'All' and not Name in self.Config_List:
            print('Configuration name provided not defined.')
            return
        
        # Prepare text to print.
        Break_line  = '---------------------------------------------'
        Break_line += '--------------------------------------------'
        First_line  = '|   Name   |  FPS  | Tint sec | NDR | Temp C |'
        First_line += '    Frame Size     |  Magnitudes  | Laser |'
        
		# Print first lines
        print(Break_line + '\n' + First_line + '\n' + Break_line)
        
        for n in self.Config_List:
            t     = self.Config[n]
            text  = '| ' + n + ' | %05.0d | %08.6f '   %(t[0],t[1])
            text += '| %03.0d | %04.2f '               %(t[2],t[3])
            text += '| [%03.0d,%03.0d:%03.0d,%03.0d] ' %(t[4],t[5],t[6],t[7])
            text += '| %04.1f -- %04.1f | %03.0d '     %(t[8],t[9], t[10]*100.)
            text += '% |'
            if Name == 'All' or Name == n: print(text + '\n' + Break_line)
        # This function does not return anything           
        return

    # =========================================================================
    def set_config(self,config):
        ''' -------------------------------------------------------------------
        Description:
            Function use to set a predefined or custom configuration.  
        
        Arguments:
            None
            
        Returns:
            None
        ------------------------------------------------------------------- '''
        # If user provided a config Name, check if valid. 
        if config in self.Config_List:
            local_fps  = self.Config[config][0]
            local_tint = self.Config[config][1] 
            local_ndr  = self.Config[config][2]
            local_temp = self.Config[config][3]
            local_crop = self.Config[config][4:8]
            Flag = True
        else:
            return False
        # Update parameters
        self.TCParam = self.get_all_parameters()
        
        # Check if fps has to be modified 
        if local_fps != self.TCParam['fps']:
            # Request FPS limits
            fps_limits  = self.get_fps_limits()
            # Case #1: FPS can be modified.
            if fps_limits[0] <= local_fps <= fps_limits[-1]:
                Flag = self.set_fps(local_fps)
            # Case #2: FPS will be modified later.

        # Check if tint has to be modified 
        if local_tint != self.TCParam['tint']:
            # Request tint limits
            tint_limits  = self.get_tint_limits()
            # Case #1: Tint can be modified.
            if tint_limits[0] <= local_tint <= tint_limits[-1]:
                Flag = self.set_tint(local_tint)
            # Case #2: Tint cannot be modified.
            else:
               print('Tint and FPS provided are not compatible.') 
               return False

        # Check if the fps has been updated.
        if local_fps != self.TCParam['fps']:
            Flag = self.set_fps(local_fps)
            if not Flag: return False

        # Check if ndr has to be modified.
        if local_ndr != self.TCParam['ndr']:
            Flag = self.set_ndr(local_ndr)
            if not Flag: return False
        
        # Check if temperature has to be modified.
        if np.abs(local_temp - self.TCParam['temp']) > 2.:
            Flag = self.set_temp(local_temp)
            if not Flag: return False
            
        #Check if Crop parameters has to be modified
        if local_crop != self.get_crop():
            Flag = self.set_subim_parameters(local_crop)
            if not Flag: return False
            
        return Flag


    # =========================================================================
    def take_all_calib(self,config_end = 'conf_015'):
        ''' -------------------------------------------------------------------
        Description:
            Function use to set a predefined or custom configuration.  
        
        Arguments:
            None
            
        Returns:
            None
        ------------------------------------------------------------------- '''
        #
        for n in self.Config_List:
            # Change the configuration. return False if failed
            if not self.set_config(n): return False
            # Take calibration images
            tmp_path, tmp_filename = self.take_calibration_images()

        return True
