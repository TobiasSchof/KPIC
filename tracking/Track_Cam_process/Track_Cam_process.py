# standard library
from configparser import ConfigParser

# installs

# nfiuserver libraries
from Track_Cam_cmds import TC_cmds
from dev_Exceptions import *

class TC_process:
    """A class to get pocessed images from the raw Tracking Camera feed
    
    Method list:
    Queries:
        is_active
        is_processesing
        is_log_scale
        is_sqrt_scale
        get_range
        get_avg_cnt
        is_minus_ref
        is_minus_bias
        is_minus_bkgrd
        get_error
    Command:
        grab_n
        set_processing
        use_log_scale
        use_sqrt_scale
        use_custom_range
        set_rolling_avg
        use_minus_bias
        load_bias
        use_minus_bkgrd
        load_bkgrd
        use_minus_ref
        load_ref
        activate_control_script
    Internal methods:
        _check_alive
        _check_alive_and_processing
        _handle_shms
        _get_header
    """

    def __init__(self):
        """Constructor for TC_process"""

        self.tc = TC_cmds()

        RELDIR = os.environ.get("RELDIR")
        if RELDIR == "": raise Exception("$RELDIR not found")
        if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

        self.config = ConfigParser
        self.config.read(RELDIR + "/data/Track_Cam_process.ini")

        # get file paths for shms

        self.Scale = self.config.get("Shm Info", "Scale").split(",")[0]
        self.DRng = self.config.get("Shm Info", "DRng").split(",")[0]
        self.PRng = self.config.get("Shm Info", "PRng").split(",")[0]
        self.Avg_cnt = self.config.get("Shm Info", "Scale").split(",")[0]
        self.Set = self.config.get("Shm Info", "Set").split(",")[0]
        self.Ref = self.config.get("Shm Info", "Ref").split(",")[0]
        self.Bkgrd = self.config.get("Shm Info", "Bkgrd").split(",")[0]
        self.Bias = self.config.get("Shm Info", "Bias").split(",")[0]
        self.Proc = self.config.get("Shm Info", "Proc").split(",")[0]
        self.Error = self.config.get("Shm Info", "Error").split(",")[0]

    def is_active(self):
        """Method to tell if control script is active or not

        NOTE: this method checks whether Set shm exists. As such, if control
            script was last killed without a chance to cleanup, it may falsely
            report that a control script is active

        Returns:
            bool = True if control script is active, False otherwise
        """

        self._handle_shms()

        return type(self.Set) is not str

    def is_processesing(self):
        """Method to determine whether the control script is processing images

        Returns:
            bool = True if processing is on, False otherwise
        """

        self._check_alive()

        return bool(self.Set.get_data()[0] & 1)

    def is_log_scale(self):
        """A method to check whether a log scale is being used
        
        Returns:
            bool = True if log scale is active, False otherwise
        """

        self._check_alive_and_processing()

        return self.Scale.get_data()[0] == 1

    def is_sqrt_scale(self):
        """A method to check whether a square root scale is being used
        
        Returns:
            bool = True if square root scale is active, False otherwise
        """

        self._check_alive_and_processing()

        return self.Scale.get_data()[0] == 2

    def get_range(self):
        """A method to get the min and max values in the processed image

        Returns:
            (float, float) = (min, max)
        """

        self._check_alive_and_processing()

        return tuple(self.DRng.get_data())

    def get_avg_cnt(self):
        """Return the number of frames being averaged

        Returns:
            int = the number of frames in the rolling average
        """

        self._check_alive_and_processing()

        return self.Avg_cnt.get_data()[0]

    def is_minus_bias(self):
        """Checks whether a bias is being subtracted

        Returns:
            bool = True if a bias is being subtracted, False otherwise
        """

        self._check_alive_and_processing()

        return bool(self.Set.get_data()[0] & 2)

    def is_minus_bkgrd(self):
        """Checks whether a background is being subtracted

        Returns:
            bool = True if a background is being subtracted, False otherwise
        """

        self._check_alive_and_processing()

        return bool(self.Set.get_data()[0] & 4)

    def is_minus_ref(self):
        """Checks whether a reference image is being subtracted

        Returns:
            bool = True if a reference image is being subtracted, False otherwise
        """

        self._check_alive_and_processing()

        return bool(self.Set.get_data()[0] & 8)

    def get_error(self):
        """A method to return the current error.

        NOTE: for error codes, check Track_Cam_process.ini

        Returns:
            int = an error code from Track_Cam_process.ini
        """

        if type(self.Error) is str:
            self._handle_shms()

        try: return self.Error.get_data()[0]
        except: raise ShmError("No Error shm.")

    def grab_n(self, n:int, path:str=None, raw:bool=False):
        """A mathod to grab a cube of frames and save them as a fits

        NOTE: if a rolling avg is on, and raw is False (default), then the cube
            will be a cube of averaged images.

        Args:
            n    = the number of frames to capture
            path = if not None, the filename to save the data at
            raw  = if True, the cube will consist of raw frames. If False (default),
                the cube will consist of processed images
        Returns:
            if n > 1 : fits.HDUList    = the fits cube
            else     : fits.PrimaryHDU = the fits frame
        """

        # if raw, we can use Track_Cam_cmds to capture cube
        if raw:
            return self.tc.grab_n(n, path)

        # otherwise, grab N images with a header on either side
        head_start = self._get_header()
        images = [self.Img.get_data(True, reform=True) for x in range(0, n)]
        if n > 1: head_end  = self._get_header()
        
        # format numpy arrays as fits
        block = fits.HDUList()
        block.append(fits.PrimaryHDU(images[0], head_start))
        if n > 1:
            for im in images[1:-1]:
                block.append(fits.PrimaryHDU(im))
            block.append(fits.PrimaryHDU(images[-1], head_end))

        if path is not None: block.writeto(path)

        return block

    def set_processing(self):

    def use_log_scale(self):

    def use_sqrt_scale(self):
    
    def use_custom_scale(self, min:int=None, max:int=None):

    def set_rolling_avg(self, cnt:int):

    def use_minus_bias(self, fname:str=None):

    def load_bias(self, fname:str=None):

    def use_minus_bkgrd(self, fname:str=None):

    def load_bkgrd(self, fname:str):

    def use_minus_ref(self, fname:str=None):

    def load_ref(self, fname:str):

    def activate_control_script(self):

    def _check_alive(self):
        """A method to raise an error if the control script is not active"""

        if not self.is_active:
            raise ScriptOff("No active control script. Use activate_control_script().")
    
    def _check_alive_and_processing(self):
        """A method to raise an error if the control script is not processing images"""

        self._check_alive(self)
        
        if not self.is_processing():
            raise ProcessingOff("Processing is off. Please turn on and try again.")

    def _handle_shms(self):
        """A method to connect to shms where appropriate"""

        # all of these shms should be persistent
        #   (as long as a control) has existed since last reboot, they should exist
        if type(self.Scale) is str:
            if os.path.isfile(self.Scale):
                self.Scale = Shm(self.Scale)
                self.DRng = Shm(self.DRng)
                self.PRng = Shm(self.PRng)
                self.Avg_cnt = Shm(self.Avg_cnt)
                self.Ref = Shm(self.Ref)
                self.Bkgrd = Shm(self.Bkgrd)
                self.Bias = Shm(self.Bias)
                self.Proc = Shm(self.Proc)
                self.Error = Shm(self.Error)
        elif not os.path.isfile(self.Scale.fname):
                self.Scale = self.Scale.fname
                self.DRng = self.DRng.fname
                self.PRng = self.PRng.fname
                self.Avg_cnt = self.Avg_cnt.fname
                self.Ref = self.Ref.fname
                self.Bkgrd = self.Bkgrd.fname
                self.Bias = self.Bias.fname
                self.Proc = self.Proc.fname
                self.Error = self.Error.fname

        # This shm only exists as long as a control script is active
        if type(self.Set) is str:
            if os.path.isfile(self.Set):
                self.Set = Shm(self.Set)
        elif not os.path.isfile(self.Set.fname):
            self.Set = self.Set.fname

    def _get_header(self):
        """A method to get a header of an image.

        This header will include all the information from Track_Cam_cmds header plus
            proc    = whether this data is processed (True/False)
            clipmin = the min value that was clipped to (or None)
            clipmax = the max value that was clipped to (or None)
            scale   = what kind of scale, if any, was used (None, log, sqrt)
            avg_cnt = the number of images averaged for one frame (averages taken in a rolling manner)
            bias_s  = whether a bias was subtracted (True/False)
            bkgrd_s = whether a background was subtracted (True/False)
            ref_s   = whether a reference image was subtracted (True/False)

        Returns:
            fits.Header = a fits header representing the current system parameters
        """ 

        self._check_alive()

        _set  = self.Set.get_data()[0]
        # if processing isn't on, we don't need other values
        if not _set & 1:
            proc_info = fits.Header({"proc":False, "clipmin":None, "clipmax":None, "scale":None,
                "avg_cnt":1, "bias_s":False, "bkgrd_s":False, "ref_s":False})
        else:
            ng   = self.PRng.get_data()
            scale = self.Scale.get_data()[0]
            scale = {0:None, 1:"log", 2:"sqrt"}[scale]
            avg   = self.Avg_cnt.get_data()[0]

            proc_info = fits.Header({"proc":bool(_set & 1), "clipmin":None if rng[0] == 0 else rng[1],
                "clipmax":None if rng[2] == 0 else rng[3], "scale":scale, "avg_cnt":avg, 
                "bias_s":bool(_set & 2), "bkgrd_s":bool(_set & 4), "ref_s":bool(_set & 8)})

        return self.tc._get_header() + proc_info

######## Errors ########

class ProcessingOff(Exception):
    """An exception to be raised when processing is off and user tries to change settings."""
    pass