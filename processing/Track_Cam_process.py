# standard library
from configparser import ConfigParser
from subprocess import Popen, PIPE
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
        is_medfilt
        get_avg_cnt
        is_using_track
        is_minus_bias
        is_minus_bkgrd
        is_minus_ref
        is_minus_calib
        get_error
    Command:
        grab_n
        set_processing
        set_range
        clear_scale
        use_log_scale
        use_sqrt_scale
        use_medfilt
        use_track
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

        # load visualizer shms
        config = ConfigParser()
        config.read(RELDIR + "/data/Track_Cam_vis_process.ini")

        # get file paths for shms
        self.Vis_Scale = config.get("Shm Info", "Scale").split(",")[0]
        self.Vis_Avg_cnt = config.get("Shm Info", "Scale").split(",")[0]
        self.Vis_Stat = config.get("Shm Info", "Stat").split(",")[0]
        self.Vis_Ref = config.get("Shm Info", "Ref").split(",")[0]
        self.Vis_Bkgrd = config.get("Shm Info", "Bkgrd").split(",")[0]
        self.Vis_Proc = config.get("Shm Info", "Proc").split(",")[0]
        self.Vis_Error = config.get("Shm Info", "Error").split(",")[0]

        # load command to start visualizer processing
        self.tmux_ses  = config.get("Environment", "session")
        self.tmux_win  = config.get("Environment", "window")
        self.tmux_ctrl = config.get("Environment", "ctrl_s")

        self._handle_shms()

    def is_active(self):
        """Method to tell if control script is active or not

        NOTE: this method checks whether Stat shms exists. As such, if control
            script was last killed without a chance to cleanup, it may falsely
            report that a control script is active

        Returns:
            bool = True if control script is active, False otherwise
        """

        self._handle_shms()

        return type(self.Vis_Stat) is Shm

    def is_processing(self, vis:bool = False):
        """Method to determine whether the control script is processing images

        Args:
            vis  = will return True only if visualizer process control script is processing
        Returns:
            bool = True if processing is on, False otherwise
        """

        # either way, we need visualizer script on
        self._check_alive()

        return bool(self.Vis_Stat.get_data()[0] & 1)

    def is_log_scale(self):
        """A method to check whether a log scale is being used for visualizer processing
        
        Returns:
            bool = True if log scale is active, False otherwise
        """

        self._check_alive_and_processing()

        return self.Vis_Scale.get_data()[0] == 1

    def is_sqrt_scale(self):
        """A method to check whether a square root scale is being used
        
        Returns:
            bool = True if square root scale is active, False otherwise
        """

        self._check_alive_and_processing()

        return self.Vis_Scale.get_data()[0] == 2

    def is_medfilt(self):
        """Checks whether a median filter is being applied

        Return:
            bool = True if a median filter is being applied, False otherwise
        """

        self._check_alive_and_processing()

        return bool(self.Vis_Stat.get_data()[0] & 4)


    def get_avg_cnt(self):
        """Return the number of frames being averaged

        Returns:
            int = the number of frames in the rolling average
        """

        self._check_alive_and_processing()

        return self.Vis_Avg_cnt.get_data()[0]

    def is_using_track(self):
        """Checks whether visualizer processing is using tracking processing

        Returns:
            bool = True if vis process is using tracking processing, False otherwise
        """

        self._check_alive_and_processing()

        return bool(self.Vis_Stat.get_data()[0] & 2)

    def is_minus_bias(self):
        """Checks whether a bias is being subtracted

        Returns:
            bool = True if a bias is being subtracted, False otherwise
        """

        self._check_alive_and_processing()

        return bool(self.Vis_Stat.get_data()[0] & 8)

    def is_minus_bkgrd(self):
        """Checks whether a background is being subtracted

        Returns:
            bool = True if a background is being subtracted, False otherwise
        """

        self._check_alive_and_processing()

        return bool(self.Vis_Stat.get_data()[0] & 16)

    def is_minus_ref(self):
        """Checks whether a reference image is being subtracted

        Returns:
            bool = True if a reference image is being subtracted, False otherwise
        """

        self._check_alive_and_processing()

        return bool(self.Vis_Stat.get_data()[0] & 32)

    def get_error(self):
        """A method to return the current error.

        NOTE: for error codes, check Track_Cam_vis_process.ini

        Returns:
            int = an error code from Track_Cam_vis_process.ini
        """

        if type(self.Vis_Error) is str:
            self._handle_shms()

        try: return self.Vis_Error.get_data()[0]
        except: raise ShmError("Error shm for visualizer processing script is missing.")

    def grab_n(self, n:int, which:str, path:str=None, end_header:bool=True, header_per:int=0):
        """A mathod to grab a cube of frames and save them as a fits

        Args:
            n          = the number of frames to capture
            which      = what kind of images to pull (should be one of 'raw', 'vis', 'visualizer')
            path       = if not None, the filename to save the data at
            end_header = if True, puts a header on the last slice as well as the first,
                            if False, only puts a header on the first slice
            header_per = will put in a header every header_per frame. If header_per
                            is 0, will only put in starting and ending headers
        Returns:
            fits.HDUList    = the fits cube
        """

        if n <= 0: return

        if which.lower() not in ["raw", "vis", "visualizer"]:
            raise ValueError("'which' must be one of: 'raw', 'vis', 'visualizer")
            
        # decide which image shm to pull from
        if which == 'raw':
            self.tc._check_alive_and_connected()
            img_shm = self.tc.Img
        else:
            self._check_alive_and_processing(vis = True)
            img_shm = self.Vis_Proc

        # format numpy arrays as fits
        block = fits.HDUList()
        # grab first image with header
        block.append(fits.PrimaryHDU(img_shm.get_data(True, reform=True), self._get_header(which)))
        # grab remaining images
        if n > 1:
            for idx in range(1, n-1):
                # add header if needed
                if header_per != 0 and idx % header_per == 0:
                    block.append(fits.PrimaryHDU(img_shm.get_data(True, reform=True), self._get_header(which)))
                else:
                    block.append(fits.PrimaryHDU(img_shm.get_data(True, reform=True)))
            # check whether to include header with last frame
            if end_header or (header_per != 0 and n-1 % header_per == 0): block.append(fits.PrimaryHDU(img_shm.get_data(True, reform=True), self._get_header(which)))
            else: block.append(fits.PrimaryHDU(img_shm.get_data(True, reform=True)))

        if path is not None: block.writeto(path)

        return block

    def set_processing(self):
        """A method to set processing on or off"""

        self._check_alive()

        # get last stat so we don't change any other parameters
        stat = self.Vis_Stat.get_data()
        # set processing bit as desired
        if vis: stat[0] = stat[0] | 1
        else: stat[0] = stat[0] & ~1
        # set new stat
        self.Vis_Stat.set_data(stat)

    def clear_scale(self):
        """A method to turn off log/sqrt scale"""

        self._check_alive()

        self.Vis_Scale.set_data(np.array([0], self.Vis_Scale.npdtype))

    def use_log_scale(self, use:bool=True):
        """A method to set scale to use log scale
        
        Args:
            use = if True, sets to log scale, if False clears scale if scale
                is log scale, does nothing otherwise
        """

        self._check_alive()

        if use: self.Vis_Scale.set_data(np.array([1], self.Vis_Scale.npdtype))
        elif self.Vis_Scale.get_data()[0] == 1:
            self.Vis_Scale.set_data(np.array([0], self.Vis_Scale.npdtype))

    def use_sqrt_scale(self, use:bool=True):
        """A method to set scale to use sqrt scale
        
        Args:
            use = if True, sets to sqrt scale, if False clears scale if scale
                is log scale, does nothing otherwise
        """

        self._check_alive()

        if use: self.Vis_Scale.set_data(np.array([2], self.Vis_Scale.npdtype))
        elif self.Vis_Scale.get_data()[0] == 2:
            self.Vis_Scale.set_data(np.array([0], self.Vis_Scale.npdtype))

    def use_medfilt(self, use:bool=True):
        """A method to set scripts to use a median filter

        Args:
            use = if True, sets a median filter, if False sets to not 
                use a median filter, otherwise does nothing
        """

        if type(use) is not bool: return

        self._check_alive_and_processing()

        stat = self.Vis_Stat.get_data()
        
        if use:
            stat[0] = stat[0] | 4
        else:
            stat[0] = stat[0] & ~4

        self.Vis_Stat.set_data(stat)

    def use_track(self, use:bool=True):
        """A method to set whether to use the tracking processed image
            or a raw image

        Args:
            use = True to use track proc, False to use a raw image
        """

        self._check_alive()

        stat = self.Vis_Stat.get_data()
        if use: stat[0] = stat[0] | 2
        else: stat[0] = stat[0] & ~2

        self.Vis_Stat.set_data(stat)
    
    def set_avg(self, cnt:int):
        """Sets the number of frames that should be averaged

        NOTE: to turn off averaging, set value to 1

        Args:
            cnt   = the number of frames to average
        """

        self._check_alive_and_processing()

        self.Vis_Avg_cnt.set_data(np.array([cnt], self.Vis_Avg_cnt.npdtype))

    def use_minus_bias(self, use:bool=True):
        """Turns bias subtraction on/off

        NOTE: if turning bias on, will turn off background and reference subtraction

        Args:
            use   = subtract bias if True, don't if False
        """

        self._check_alive_and_processing()

        # set minus bias bit
        _ = self.Vis_Stat.get_data()
        if use:
            _[0] = _[0] | 8
            _[0] = _[0] & ~(48)
        else:
            _[0] = _[0] & ~8

        self.Vis_Stat.set_data(_)

    def use_minus_bkgrd(self, use:bool=True, fname:str=None):
        """Turns background subtraction on/off

        NOTE: if turning background on, will turn off bias and reference subtraction
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
        _ = self.Vis_Stat.get_data()
        if use:
            _[0] = _[0] | 16
            _[0] = _[0] & ~40
        else:
            _[0] = _[0] & ~16

        self.Vis_Stat.set_data(_)

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
                    self.Vis_Error.set_data(np.array([2], self.Vis_Error.npdtype))
                    raise BkgrdParams("Loaded background parameters don't match current settings.")

                # load bias into shm
                self.Vis_Bkgrd.set_data(np.array(f[0].data, self.Vis_Bkgrd.npdtype))
        else:
            self.Vis_Bkgrd.set_data(self.tc.Img.get_data(reform = True))

    def use_minus_ref(self, use:bool=True, fname:str=None):
        """Turns reference image subtraction on/off

        NOTE: if turning background on, will turn off bias and reference subtraction
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
        _ = self.Vis_Stat.get_data()
        if use:
            _[0] = _[0] | 32
            _[0] = _[0] & ~24
        else:
            _[0] = _[0] & ~32

        self.Vis_Stat.set_data(_)

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
                    self.Vis_Error.set_data(np.array([3], self.Vis_Error.npdtype))
                    raise RefParams("Loaded reference image parameters don't match current settings.")
                # load bias into shm
                self.Vis_Ref.set_data(np.array(f[0].data, self.Vis_Ref.npdtype))
        else:
            self.Vis_Ref.set_data(self.Vis_Proc.get_data())

    def activate_control_script(self):
        """A method to start the control script for Tracking Camera processing"""

        if self.is_active():
            raise ScriptAlreadyActive("Visualizer Processing script already active.")

        # check if sessions already exists
        out = Popen(["tmux", "ls", "-F", "'#S'"], stdout=PIPE, stderr=PIPE).communicate()
        # if not, make it
        if str(out[0]).find("'{}'".format(self.tmux_ses)) == -1:
            out = Popen(["tmux", "new", "-d", "-s", self.tmux_ses, "-n", self.tmux_win],
                stdout=PIPE, stderr=PIPE).communicate()
            if out[1] != b'':
                msg = "TMUX error: {}".format(str(out[1]))
                raise TMUXError(msg)

        # check if window already exists
        out = Popen(["tmux", "lsw", "-t", self.tmux_ses, "-F", "'#W'"], stdout=PIPE,
            stderr=PIPE).communicate()
        # if not, make it
        if str(out[0]).find("'{}'".format(self.tmux_win)) == -1:
            out = Popen(["tmux", "new-window", "-t", self.tmux_ses, "-n", self.tmux_win],
                stdout=PIPE, stderr=PIPE).communicate()
            if out[1] != b'':
                msg = "TMUX error: {}".format(str(out[1]))
                raise TMUXError(msg)

        # Start Control script
        out = Popen(["tmux", "send-keys", "-t", "{}:{}".format(self.tmux_ses, self.tmux_win),
            "'{}'".format(self.tmux_ctrl), "Enter"], stdout=PIPE, stderr=PIPE).communicate()
        # check if there was an error
        if out[1] != b'':
            msg = "TMUX error: {}".format(str(out[1]))
            raise TMUXError(msg)

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
        #   (as long as a vis control has existed since last reboot, they should exist)
        if type(self.Vis_Scale) is str:
            if os.path.isfile(self.Vis_Scale):
                self.Vis_Scale = Shm(self.Vis_Scale)
                self.Vis_Avg_cnt = Shm(self.Vis_Avg_cnt)
                self.Vis_Ref = Shm(self.Vis_Ref)
                self.Vis_Bkgrd = Shm(self.Vis_Bkgrd)
                self.Vis_Proc = Shm(self.Vis_Proc)
                self.Vis_Error = Shm(self.Vis_Error)
        elif not os.path.isfile(self.Vis_Scale.fname):
            self.Vis_Scale = self.Vis_Scale.fname
            self.Vis_Avg_cnt = self.Vis_Avg_cnt.fname
            self.Vis_Ref = self.Vis_Ref.fname
            self.Vis_Bkgrd = self.Vis_Bkgrd.fname
            self.Vis_Proc = self.Vis_Proc.fname
            self.Vis_Error = self.Vis_Error.fname

        # This shm only exists as long as a vis control script is active
        if type(self.Vis_Stat) is str:
            if os.path.isfile(self.Vis_Stat):
                self.Vis_Stat = Shm(self.Vis_Stat)
        elif not os.path.isfile(self.Vis_Stat.fname):
            self.Vis_Stat = self.Vis_Stat.fname

    def _get_header(self, which:str):
        """A method to get a header of an image.

        This header will include all the information from Track_Cam_cmds header plus (if which is not raw)
            medfilt  = whether a median filter is applied

            baseproc = whether visualizer processor is using base processing
            vissubt  = logical for whether a frame is subtracted 
            visavg   = the number of images averaged for one frame in vis process
                    (NOTE: these are rolling averages and only used if starting from the raw image)
            scale    = what kind of scale, if any, was used (None, log, sqrt)
        Args:
            which = which kind of frame to make a header for (one of 'raw', 'vis', or 'visualizer)
        Returns:
            fits.Header = a fits header representing the current system parameters
        """ 

        if which.lower() not in ['raw', 'vis', 'visualizer']:
            raise ValueError("which can be one of: 'raw', ''vis', 'visualizer'.")

        if which == "raw":
            return self.tc._get_header()

        self._check_alive(vis=True, base=True)

        medfilt = "N/A"
        baseproc = "N/A"
        vissubt = "N/A"
        visavg = "N/A"
        scl = "N/A"

        vis_stat     = self.Vis_Stat.get_data()[0]
        baseproc = bool(vis_stat & 2)
        medfilt  = bool(vis_stat & 4)
        if vis_stat & 56:
            vissubt = True
        else:
            vissubt = False 
        visavg       = self.Vis_Avg_cnt.get_data()[0]
        scl          = self.Vis_Scale.get_data()[0]
        # convert scale to readable value
        if scl == 0:
            scl = "None"
        elif scl == 1:
            scl = "Log"
        elif scl == 2:
            scl = "Sqrt"

        proc_info = fits.Header({"medfilt":medfilt, "baseproc":baseproc, "vissubt":vissubt,
            "visavg":visavg, "scale":scl})

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

class BkgrdParams(Exception):
    """An exception to be raised if the parameters for a background don't match the current
        settings of the camera"""
    pass

class RefParams(Exception):
    """An exception to be raised if the parameters for a reference image don't match the 
        current settings of the camera"""
    pass