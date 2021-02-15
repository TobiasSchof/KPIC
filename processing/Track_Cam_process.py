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
        is_medfilt
        get_avg_cnt
        is_using_base
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
        use_base
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
        self.vis_on_cmd = config.get("Environment", "start_command")

        # load bas processing shms
        config = ConfigParser()
        config.read(RELDIR + "/data/Track_Cam_base_process.ini")

        # get base processing shms
        self.Base_Avg_cnt = config.get("Shm Info", "Avg_cnt").split(",")[0]
        self.Base_Stat = config.get("Shm Info", "Stat").split(",")[0]
        self.Base_Calib = config.get("Shm Info", "Calib").split(",")[0]
        self.Base_proc = config.get("Shm Info", "Base_proc").split(",")[0]
        self.Base_Error = config.get("Shm Info", "Error").split(",")[0]

        # load command to start base processing
        self.base_on_cmd = config.get("Environment", "start_command")

    def is_active(self, base:bool = True, vis:bool = True):
        """Method to tell if control script is active or not

        NOTE: this method checks whether Stat shms exists. As such, if control
            script was last killed without a chance to cleanup, it may falsely
            report that a control script is active

        Args:
            base = returns True only if base process control script is on
            vis  = returns True only if visualizer process control script is running
        Returns:
            bool = True if control script(s) is(are) active, False otherwise
                if both base and vis are False, this method will always return True
        """

        self._handle_shms()

        ret = True
        if base: ret = ret and (type(self.Base_Stat) is Shm) 
        if vis: ret = ret and (type(self.Vis_Stat) is Shm)

        return ret

    def is_processing(self, base:bool = False, vis:bool = False):
        """Method to determine whether the control script is processing images

        NOTE: if both base and vis are False, this method will return True if and
            only if images are being processed. I.e. if visualizer script is processing
            and either visualizer is using raw images or base process control script
            is processing.

        Args:
            base = will return True only if base process control script is processing
            vis  = will return True only if visualizer process control script is processing
        Returns:
            bool = True if processing is on, False otherwise
        """

        # either way, we need visualizer script on
        self._check_alive(vis = True)

        # if default, assign vis and base values to check the correct setup
        if not base and not vis:
            vis = True
            base = bool(self.Vis_Stat.get_data()[0] & 2)
            
        if base: self._check_alive(base = True)

        ret = True
        if base: ret = ret and bool(self.Base_Stat.get_data()[0] & 1)
        if vis:  ret = ret and bool(self.Vis_Stat.get_data()[0] & 1)

        return ret

    def is_log_scale(self):
        """A method to check whether a log scale is being used for visualizer processing
        
        Returns:
            bool = True if log scale is active, False otherwise
        """

        self._check_alive_and_processing(vis = True)

        return self.Vis_Scale.get_data()[0] == 1

    def is_sqrt_scale(self):
        """A method to check whether a square root scale is being used
        
        Returns:
            bool = True if square root scale is active, False otherwise
        """

        self._check_alive_and_processing(vis = True)

        return self.Vis_Scale.get_data()[0] == 2

    def is_medfilt(self, vis=True):
        """Checks whether a median filter is being applied

        Args:
            vis = if True, checks for median filter in visualizer processing,
                if False, checks in base processing
        Return:
            bool = True if a median filter is being applied, False otherwise
        """

        self._check_alive_and_processing(vis = vis, base = True)

        if not vis:
            return bool(self.Base_Stat.get_data()[0] & 4)
        else:
            # option 1: visualizer processing is using base processing
            if self.Vis_Stat.get_data()[0] & 2:
                return bool(self.Vis_Stat.get_data()[0] & 4) or bool(self.Base_Stat.get_data()[0] & 4)
            # option 2: visualizer processing is using a raw image
            else:
                return bool(self.Vis_Stat.get_data()[0] & 4)


    def get_avg_cnt(self, vis:bool = True):
        """Return the number of frames being averaged

        Args:
            vis = True to get average count for the visualizer
                processor, False to get average count for the base
                processor
        Returns:
            int = the number of frames in the rolling average
        """

        self._check_alive_and_processing(vis = vis, base = not vis)

        if vis: return self.Vis_Avg_cnt.get_data()[0]
        else: return self.Base_Avg_cnt.get_data()[0]

    def is_using_base(self):
        """Checks whether visualizer processing is using base processing

        Returns:
            bool = True if vis process is using base processing, False otherwise
        """

        self._check_alive_and_processing(vis = True)

        return bool(self.Vis_Stat.get_data()[0] & 2)

    def is_minus_bias(self):
        """Checks whether a bias is being subtracted (in visualizer processing)

        Returns:
            bool = True if a bias is being subtracted, False otherwise
        """

        self._check_alive_and_processing(vis = True)

        return bool(self.Vis_Stat.get_data()[0] & 8)

    def is_minus_bkgrd(self):
        """Checks whether a background is being subtracted (in visualizer processing)

        Returns:
            bool = True if a background is being subtracted, False otherwise
        """

        self._check_alive_and_processing(vis = True)

        return bool(self.Vis_Stat.get_data()[0] & 16)

    def is_minus_ref(self):
        """Checks whether a reference image is being subtracted (in visualizer processing)

        Returns:
            bool = True if a reference image is being subtracted, False otherwise
        """

        self._check_alive_and_processing(vis = True)

        return bool(self.Vis_Stat.get_data()[0] & 32)

    def is_minus_calib(self):
        """Checks whether a calibration image is being subtracted (in base processing)

        Return:
            bool = True if a calibration image is being subtracted, False otherwise
        """

        self._check_alive_and_processing(base = True)

        return bool(self.Base_Stat.get_data()[0] & 2)

    def get_error(self):
        """A method to return the current error.

        NOTE: for error codes, check Track_Cam_process.ini

        Returns:
            int, int = an error code from Track_Cam_base_process.ini, 
                an error code from Track_Cam_vis_process.ini
        """

        if type(self.Vis_Error) is str or type(self.Base_error) is str:
            self._handle_shms()

        try: return self.Base_Error.get_data()[0], self.Vis_Error.get_data()[0]
        except: raise ShmError("Error shm for one of the processing scripts is missing.")

    def grab_n(self, n:int, which:str, path:str=None, end_header:bool=True, header_per:int=0):
        """A mathod to grab a cube of frames and save them as a fits

        Args:
            n          = the number of frames to capture
            which      = what kind of images to pull (should be one of 'raw', 'base', 'vis', 'visualizer')
            path       = if not None, the filename to save the data at
            end_header = if True, puts a header on the last slice as well as the first,
                            if False, only puts a header on the first slice
            header_per = will put in a header every header_per frame. If header_per
                            is 0, will only put in starting and ending headers
        Returns:
            fits.HDUList    = the fits cube
        """

        if n <= 0: return

        if which.lower() not in ["raw", "base", "vis", "visualizer"]:
            raise ValueError("'which' must be one of: 'raw', 'base', 'vis', 'visualizer")
            
        # decide which image shm to pull from
        if which == 'raw':
            self.tc._check_alive_and_connected()
            img_shm = self.tc.Img
        elif which == 'base':
            self._check_alive_and_processing(base = True)
            img_shm = self.Base_proc
        else:
            self._check_alive_and_processing(vis = True)
            img_shm = self.Vis_Proc

        # grab N images with a header on either side
        
        # format numpy arrays as fits
        block = fits.HDUList()
        # grab first image with header
        block.append(fits.PrimaryHDU(img_shm.get_data(True, reform=True), self._get_header(which)))
        if n > 1:
            for idx in range(1, n-1):
                if header_per != 0 and idx % header_per == 0:
                    block.append(fits.PrimaryHDU(img_shm.get_data(True, reform=True), self._get_header(which)))
                else:
                    block.append(fits.PrimaryHDU(img_shm.get_data(True, reform=True)))
            # check whether to include header with last frame
            if end_header or (header_per != 0 and n-1 % header_per == 0): block.append(fits.PrimaryHDU(img_shm.get_data(True, reform=True), self._get_header(which)))
            else: block.append(fits.PrimaryHDU(img_shm.get_data(True, reform=True)))

        if path is not None: block.writeto(path)

        return block

    def set_processing(self, vis:bool=None, base:bool=None):
        """A method to set processing on or off

        Args:
            vis  = True to turn visualizer processing on, False to turn it off,
                None to do nothing
            base = True to turn base processing on, False to turn it off,
                None to do nothing
        """

        self._check_alive(vis = (vis is not None), base = (base is not None))

        if vis is not None:
            # get last stat so we don't change any other parameters
            stat = self.Vis_Stat.get_data()
            # set processing bit as desired
            if vis: stat[0] = stat[0] | 1
            else: stat[0] = stat[0] & ~1
            # set new stat
            self.Vis_Stat.set_data(stat)
        if base is not None:
            # get last stat so we don't change any other parameters
            stat = self.Base_Stat.get_data()
            # set processing bit as desired
            if base: stat[0] = stat[0] | 1
            else: stat[0] = stat[0] & ~1
            # set new stat
            self.Base_Stat.set_data(stat)

    def clear_scale(self):
        """A method to turn off log/sqrt scale"""

        self._check_alive(vis = True)

        self.Vis_Scale.set_data(np.array([0], self.Vis_Scale.npdtype))

    def use_log_scale(self, use:bool=True):
        """A method to set scale to use log scale
        
        Args:
            use = if True, sets to log scale, if False clears scale if scale
                is log scale, does nothing otherwise
        """

        self._check_alive(vis = True)

        if use: self.Vis_Scale.set_data(np.array([1], self.Vis_Scale.npdtype))
        elif self.Vis_Scale.get_data()[0] == 1:
            self.Vis_Scale.set_data(np.array([0], self.Vis_Scale.npdtype))

    def use_sqrt_scale(self, use:bool=True):
        """A method to set scale to use sqrt scale
        
        Args:
            use = if True, sets to sqrt scale, if False clears scale if scale
                is log scale, does nothing otherwise
        """

        self._check_alive(vis = True)

        if use: self.Vis_Scale.set_data(np.array([2], self.Vis_Scale.npdtype))
        elif self.Vis_Scale.get_data()[0] == 2:
            self.Vis_Scale.set_data(np.array([0], self.Vis_Scale.npdtype))

    def use_medfilt(self, use:bool=True):
        """A method to set scripts to use a median filter

        Args:
            use = if True, sets a median filter, if False sets to not 
                use a median filter, otherwise does nothing
        """

        self._check_alive_and_processing(vis = True)

        stat = self.Vis_Stat.get_data()
        
        if use:
            stat[0] = stat[0] | 4
        else:
            stat[0] = stat[0] & ~4

        self.Vis_Stat.set_data(stat)

    def use_base(self, use:bool=True):
        """A method to set whether to use the base processed image
            or a raw image

        Args:
            use = True to use base proc, False to use a raw image
        """

        self._check_alive(vis=True, base=use)

        stat = self.Vis_Stat.get_data()
        if use: stat[0] = stat[0] | 2
        else: stat[0] = stat[0] & ~2

        self.Vis_Stat.set_data(stat)
    
    def set_avg(self, cnt:int, which:str):
        """Sets the number of frames that should be averaged

        NOTE: to turn off averaging, set value to 1

        Args:
            cnt   = the number of frames to average
            which = which average to set. Should be one of 'vis', 'visualizer',
                or 'base'
        """

        if which.lower() not in ["base", "vis", "visualizer"]:
            raise ValueError("'which' must be one of: 'base', 'vis', 'visualizer")

        self._check_alive_and_processing(base = which.lower() == "base", vis = which.lower() in ["vis", "visualizer"])

        if which == "base":
            self.Base_Avg_cnt.set_data(np.array([cnt], self.Base_Avg_cnt.npdtype))
        else:
            self.Vis_Avg_cnt.set_data(np.array([cnt], self.Vis_Avg_cnt.npdtype))

    def use_minus_bias(self, use:bool=True):
        """Turns bias subtraction on/off

        NOTE: if turning bias on, will turn off background and reference subtraction

        Args:
            use   = subtract bias if True, don't if False
        """

        self._check_alive_and_processing(vis = True)

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

        self._check_alive_and_processing(vis = True)

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

        self._check_alive_and_processing(vis = True)

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

    def activate_control_script(self, base:bool=False, vis:bool=False):
        """A method to start the control script for Tracking Camera processing"""

        if base and not self.is_active(base = True, vis = False):
            command = self.base_on_cmd.split("|")
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

        if vis and not self.is_active(base = False, vis = True):
            command = self.vis_on_cmd.split("|")
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

    def _check_alive(self, base:bool=False, vis:bool=False):
        """A method to raise an error if the control script is not active"""

        if not (base or vis):
            raise ValueError("Base or vis should be True.")
        if not self.is_active(base=base, vis=vis):
            raise ScriptOff("No active control script. Use activate_control_script().")

    def _check_alive_and_processing(self, base:bool=False, vis:bool=False):
        """A method to raise an error if the control script is not processing images"""

        if not (base or vis):
            raise ValueError("Base or vis should be True.")

        self._check_alive(base=base, vis=vis)
        
        if not self.is_processing(base=base, vis=vis):
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

        # all of these shms should be persistent
        #   (as long as a base control has existed since last reboot, they should exist)
        if type(self.Base_Avg_cnt) is str:
            if os.path.isfile(self.Base_Avg_cnt):
                self.Base_Avg_cnt = Shm(self.Base_Avg_cnt)
                self.Base_Calib = Shm(self.Base_Calib)
                self.Base_proc = Shm(self.Base_proc)
                self.Base_Error = Shm(self.Base_Error)
        elif not os.path.isfile(self.Base_Avg_cnt.fname):
            self.Base_Avg_cnt = self.Base_Avg_cnt.fname
            self.Base_Calib = self.Base_Calib.fname
            self.Base_proc = self.Base_proc.fname
            self.Base_Error = self.Base_Error.fname

        # This shm only exists as long as a vis control script is active
        if type(self.Vis_Stat) is str:
            if os.path.isfile(self.Vis_Stat):
                self.Vis_Stat = Shm(self.Vis_Stat)
        elif not os.path.isfile(self.Vis_Stat.fname):
            self.Vis_Stat = self.Vis_Stat.fname
        # This shm only exists as long as a base control script is active
        if type(self.Base_Stat) is str:
            if os.path.isfile(self.Base_Stat):
                self.Base_Stat = Shm(self.Base_Stat)
        elif not os.path.isfile(self.Base_Stat.fname):
            self.Base_Stat = self.Base_Stat.fname

    def _get_header(self, which:str):
        """A method to get a header of an image.

        This header will include all the information from Track_Cam_cmds header plus (if which is not raw)
            medfilt  = whether a median filter is applied

            baseproc = whether visualizer processor is using base processing
            vissubt  = logical for whether a frame is subtracted 
            visavg   = the number of images averaged for one frame in vis process
                    (NOTE: these are rolling averages and only used if starting from the raw image)
            scale    = what kind of scale, if any, was used (None, log, sqrt)
  
            baseavg  = the number of images averaged for one frame in base process
            basesubt = whether a calibration image is being subtracted in base processing
        Args:
            which = which kind of frame to make a header for (one of 'raw', 'base', 'vis', or 'visualizer)
        Returns:
            fits.Header = a fits header representing the current system parameters
        """ 

        if which.lower() not in ['raw', 'base', 'vis', 'visualizer']:
            raise ValueError("which can be one of: 'raw', 'base', 'vis', 'visualizer'.")

        if which == "raw":
            return self.tc._get_header()

        self._check_alive(vis=True, base=True)

        medfilt = "N/A"
        baseproc = "N/A"
        vissubt = "N/A"
        visavg = "N/A"
        scl = "N/A"
        basesubt = "N/A"
        baseavg = "N/A"

        if which.lower() in ["vis", "visualizer"]:
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

        if which.lower() == "base" or (which.lower() in ["vis", "visualizer"] and vis_stat & 1):
            base_stat = self.Base_Stat.get_data()[0]
            medfilt  = base_stat & 4
            basesubt = base_stat & 2
            baseavg  = self.Base_Avg_cnt.get_data()[0]

        proc_info = fits.Header({"medfilt":medfilt, "baseproc":baseproc, "vissubt":vissubt,
            "visavg":visavg, "scale":scl, "basesubt":basesubt, "baseavg":baseavg})

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