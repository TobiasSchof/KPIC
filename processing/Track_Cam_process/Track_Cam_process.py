# standard library
from configparser import ConfigParser
from subprocess import Popen
import os

# installs
import numpy as np
from time import sleep
from astropy.io import fits

# nfiuserver libraries
from KPIC_shmlib import Shm
from Track_Cam_cmds import TC_cmds
from dev_Exceptions import *

class TC_process:
    """A class to get pocessed images from the raw Tracking Camera feed
    
    Method list:
    Queries:
        is_active
        is_processing
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
        set_range
        clear_scale
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
        _check_header
    """

    def __init__(self):
        """Constructor for TC_process"""

        self.tc = TC_cmds()

        RELDIR = os.environ.get("RELDIR")
        if RELDIR == "": raise Exception("$RELDIR not found")
        if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

        self.config = ConfigParser()
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

    def is_processing(self):
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

    def set_range(self, min:int="no change", max:int="no change"):
        """Sets the min and/or max values for clipping

        NOTE: None as a value indicates to just use min/max value in frame (turn off 
            custom range), 'no change' as a value indicates to keep current settings

        Args:
            min = an int to set a minimum pixel value, 
                  None to use frame's minimum,
                  or 'no change' (default) to keep current settings
            max = an int to set a maximum pixel value,
                  None to use frame's maximum,
                  or 'no change' (default) to keep current settings
        """

        self._check_alive_and_processing()

        rng = self.PRng.get_data()

        if str(min) != "no change":
            if min is None: rng[0] = 0
            else:
                try:
                    rng[1] = int(min)
                    rng[0] = 1
                except ValueError: raise ValueError("min must be an int, None, or 'no change'.")
        if str(max) != "no change":
            if max is None: rng[2] = 0
            else:
                try:
                    rng[3] = int(max)
                    rng[2] = 1
                except ValueError: raise ValueError("max must be an int, None, or 'no change'.")

        self.PRng.set_data(rng)

    def set_processing(self, proc:bool=True):
        """A method to set processing on or off

        NOTE: sets all subtraction bits to off

        Args:
            set = True for on, False for off
        """

        self._check_alive()

        self.Set.set_data(np.array([int(proc)], self.Set.npdtype))

    def clear_scale(self):
        """A method to turn off log/sqrt scale"""

        self._check_alive()

        self.Scale.set_data(np.array([0], self.Scale.npdtype))

    def use_log_scale(self, use:bool=True):
        """A method to set scale to use log scale
        
        Args:
            use = if True, sets to log scale, if False clears scale if scale
                is log scale, does nothing otherwise
        """

        self._check_alive()

        if use: self.Scale.set_data(np.array([1], self.Scale.npdtype))
        elif self.Scale.get_data()[0] == 1:
            self.Scale.set_data(np.array([0], self.Scale.npdtype))

    def use_sqrt_scale(self, use:bool=True):
        """A method to set scale to use sqrt scale
        
        Args:
            use = if True, sets to sqrt scale, if False clears scale if scale
                is log scale, does nothing otherwise
        """

        self._check_alive()

        if use: self.Scale.set_data(np.array([2], self.Scale.npdtype))
        elif self.Scale.get_data()[0] == 2:
            self.Scale.set_data(np.array([0], self.Scale.npdtype))
    
    def use_custom_range(self, min:int=None, max:int=None):
        """A method to set a custom scale (min and max clip)

        Args:
            min = the minimum value to clip the image to
                (or None to not clip)
            max = the maximum value to clip the image to
                (or None to not clip)
        """

        self._check_alive_and_processing()

        # pull current range settings
        _ = self.PRng.get_data()

        # handle min
        if min is None:
            _[0] = 0
        else:
            _[0] = 1
            _[1] = min
        if max is None:
            _[2] = 0
        else:
            _[2] = 1
            _[3] = max

        # set new values
        self.PRng.set_data(_)

    def set_rolling_avg(self, cnt:int):
        """Sets the number of frames that should be averaged on a rolling basis

        NOTE: to turn off averaging, set value to 1

        Args:
            cnt = the number of frames to average
        """

        self._check_alive_and_processing()

        self.Avg_cnt.set_data(np.array([cnt], Avg_cnt.npdtype))

    def use_minus_bias(self, use:bool=True, fname:str=None):
        """Turns bias subtraction on/off

        NOTE: if fname is not none but use is False, the bias will still
            be loaded, but not subtracted

        Args:
            use   = subtract bias if True, don't if False
            fname = the path to a bias to load. If None, a bias file
                with the current camera parameters will be looked for.
        """

        self._check_alive_and_processing()

        if fname is None:
            # get bias name for matching parameters
            fname = "/nfiudata/darks/bias_{fps:04d}_{tint:0.5f}_{ndr:02d}_{temp:0.5f}_"\
                +"{lb:03d}_{rb:03d}_{ub:03d}_{bb:03d}.fits"
            crop = self.tc.get_crop()
            fname = fname.format(fps = self.tc.get_fps(), tint = self.tc.get_tint(), 
                ndr = self.tc.get_ndr(), temp = self.tc.Temp_P.get_data()[0], lb = crop[0], rb = crop[1], 
                ub = crop[2], bb = crop[3])
            # if no bias with current settings is found, raise error
            if not os.path.isfile(fname):
                raise FileNotFoundError("No bias file to match current camera parameters.")
            # otherwise load bias
            with fits.open(fname) as f:
                self.Bias.set_data(np.array(f[0].data, self.Bias.npdtype))
        else:
            # load bias into shm
            self.load_bias(fname)

        # set minus bias bit
        _ = self.Set.get_data()
        if use: _[0] = _[0] | 2
        else:   _[0] = _[0] & ~2

        self.Set.set_data(_)

    def load_bias(self, fname:str=None):
        """Loads the bias at the destination into the shm

        Args:
            fname = the path to a fits file. The first frame will be loaded as
                the bias
                (if None, the current frame of raw img will be taken as the bias)
        """

        if fname is not None:
            # check that file exists
            if not os.path.isfile(fname):
                raise FileNotFoundError()
            with fits.open(fname) as f:
                # confirm that fps, temp, tint, ndr, and crop match
                if not self._check_header(f[0].header):
                    self.Error.set_data(np.array([1], self.Error.npdtype))
                    raise BiasParams("Loaded Bias parameters don't match current settings.")

                # load bias into shm
                self.Bias.set_data(np.array(f[0].data, self.Bias.dtype))
        else:
            self.Bias.set_data(self.tc.Img.get_data())

    def use_minus_bkgrd(self, use:bool=True, fname:str=None):
        """Turns background subtraction on/off

        NOTE: if fname is not none but use is False, the background will still
            be loaded, but not subtracted

        Args:
            use   = subtract background if True, don't if False
            fname = the path to a background to load. If None, the currently
                loaded background will be subtracted.
        """

        self._check_alive_and_processing()

        if not fname is None:
            # load bias into shm
            self.load_bkgrd(fname)

        # set minus bias bit
        _ = self.Set.get_data()
        if use: _[0] = _[0] | 4
        else:   _[0] = _[0] & ~4

        self.Set.set_data(_)

    def load_bkgrd(self, fname:str=None):
        """Loads the background at the destination into the shm

        Args:
            fname = the path to a fits file. The first frame will be loaded as
                the background
                (if None, the current frame of proc img will be taken as the background)
        """

        if fname is not None:
            # check that file exists
            if not os.path.isfile(fname):
                raise FileNotFoundError()
            with fits.open(fname) as f:
                # confirm that fps, temp, tint, ndr, and crop match
                if not self._check_header(f[0].header):
                    self.Error.set_data(np.array([2], self.Error.npdtype))
                    raise BkgrdParams("Loaded background parameters don't match current settings.")

                # load bias into shm
                self.Bkgrd.set_data(np.array(f[0].data, self.Bkgrd.npdtype))
        else:
            self.Bkgrd.set_data(self.Proc.get_data())

    def use_minus_ref(self, use:bool=True, fname:str=None):
        """Turns reference image subtraction on/off

        NOTE: if fname is not none but use is False, the reference image will still
            be loaded, but not subtracted

        Args:
            use   = subtract reference image if True, don't if False
            fname = the path to a reference image to load. If None, the currently
                loaded reference image will be subtracted.
        """

        self._check_alive_and_processing()

        if not fname is None:
            # load bias into shm
            self.load_ref(fname)

        # set minus bias bit
        _ = self.Set.get_data()
        if use: _[0] = _[0] | 8
        else:   _[0] = _[0] & ~8

        self.Set.set_data(_)

    def load_ref(self, fname:str=None):
        """Loads the reference image at the destination into the shm

        Args:
            fname = the path to a fits file. The first frame will be loaded as
                the reference image
                (if None, the current frame of proc img will be taken as the reference)
        """

        if fname is not None:
            # check that file exists
            if not os.path.isfile(fname):
                raise FileNotFoundError()
            with fits.open(fname) as f:
                # confirm that fps, temp, tint, ndr, and crop match
                if not self._check_header(f[0].header):
                    self.Error.set_data(np.array([3], self.Error.npdtype))
                    raise RefParams("Loaded reference image parameters don't match current settings.")
                # load bias into shm
                self.Ref.set_data(np.array(f[0].data, self.Ref.npdtype))
        else:
            self.Ref.set_data(self.Proc.get_data())

    def activate_control_script(self):
        """A method to start the control script for Tracking Camera processing"""

        if self.is_active():
            raise ScriptAlreadActive("Tracking camera processing control script already alive.")

        command = self.config.get("Environment", "start_command").split("|")
        for cmd in command:
            # an array to hold the processed command
            proc_cmd = []
            # split by " to get command to send
            tmp = cmd.split('"')
            for idx, word in enumerate(tmp):
                # if index is 1 mod 2, this was in quotes
                if idx % 2 == 1: proc_cmd += [word]
                else: proc_cmd += word.split(" ")

            Popen(proc_cmd)
            # add a sleep to give tmux time to initialize after new commands
            sleep(.1)

    def _check_alive(self):
        """A method to raise an error if the control script is not active"""

        if not self.is_active():
            raise ScriptOff("No active control script. Use activate_control_script().")

    def _check_alive_and_processing(self):
        """A method to raise an error if the control script is not processing images"""

        self._check_alive()
        
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

    def _check_header(self, header:fits.Header):
        """A method to check that the values in the header match current camera parameters
        
        Args:
            header = the fits header to check
        Returns:
            bool = True if header matches, False otherwise
        """

        # fields to check for equality
        f2c = ("fps", "tint", "ndr", "t_setp", "crop_LB", "crop_RB",
            "crop_UB", "crop_BB")

        current_settings = self.tc._get_header()

        for field in f2c:
            if not current_settings[field] == header[field]: return False

        return True

######## Errors ########

class ProcessingOff(Exception):
    """An exception to be raised when processing is off and user tries to change settings."""
    pass

class BiasParams(Exception):
    """An exception to be raised if the parameters for a bias don't match the current
        settings of the camera"""
    pass

class BkgrdParams(Exception):
    """An exception to be raised if the parameters for a background don't match the current
        settings of the camera"""
    pass

class RefParams(Exception):
    """An exception to be raised if the parameters for a reference image don't match the 
        current settings of the camera"""
    pass