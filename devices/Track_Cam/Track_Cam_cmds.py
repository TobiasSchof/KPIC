# standard library
from configparser import ConfigParser
from subprocess import Popen
from time import sleep
from numpy import array
from time import gmtime
import os

# installs
import numpy as np
from astropy.io import fits

# nfiuserver libraries
from KPIC_shmlib import Shm
from dev_Exceptions import *

######## Camera interface class ########
 
class TC_cmds:
    """Class for controlling the CRED2 Tracking Camera and getting raw data

    method list:
    Queries:
        is_active
        is_connected
        is_fan_on
        is_led_on
        get_tint
        get_fps
        get_ndr
        get_crop
        get_temp
        grab_n
    Commands:
        save_dark
        set_fan
        set_led
        set_tint
        set_fps
        set_ndr
        set_crop
        set_temp
        connect_camera
        turn_off_camera
        activate_control_script
    Internal methods:
        _check_alive
        _check_alive_and_connected
        _handle_shms
        _get_header
    """

    def __init__(self):
        """Constructor for TC_cmds class"""

        RELDIR = os.environ.get("RELDIR")
        if RELDIR == "": raise Exception("$RELDIR not found")
        if RELDIR[-1] == "/": RELDIR = RELDIR[:-1]

        self.config = ConfigParser()
        self.config.read(RELDIR + "/data/Track_Cam.ini")

        # get file paths for shms
        self.Stat_D = self.config.get("Shm Info", "Stat_D").split(",")[0]
        self.Stat_P = self.config.get("Shm Info", "Stat_P").split(",")[0]
        self.Error  = self.config.get("Shm Info", "Error").split(",")[0]
        self.Img    = self.config.get("Shm Info", "IMG").split(",")[0]
        self.Crop_D = self.config.get("Shm Info", "Crop_D").split(",")[0]
        self.Crop_P = self.config.get("Shm Info", "Crop_P").split(",")[0]
        self.NDR_D  = self.config.get("Shm Info", "NDR_D").split(",")[0]
        self.NDR_P  = self.config.get("Shm Info", "NDR_P").split(",")[0]
        self.FPS_D  = self.config.get("Shm Info", "FPS_D").split(",")[0]
        self.FPS_P  = self.config.get("Shm Info", "FPS_P").split(",")[0]
        self.Exp_D  = self.config.get("Shm Info", "Exp_D").split(",")[0]
        self.Exp_P  = self.config.get("Shm Info", "Exp_P").split(",")[0]
        self.Temp_D = self.config.get("Shm Info", "Temp_D").split(",")[0]
        self.Temp_P = self.config.get("Shm Info", "Temp_P").split(",")[0]
        
    def is_active(self):
        """Method to tell if control script is active or not

        NOTE: this method checks 1) whether there is a D_Stat shm and 2) whether
            the script bit in the D_Stat shm is 1. This means that if a script ends
            in a way to prevent cleanup, this method could return true despite no script
            being active until D_Stat is fixed or deleted.

        Returns:
            bool = True if control script is active, False otherwise
        """

        self._handle_shms()

        if type(self.Stat_D) is str:
                return False
        
        return bool(self.Stat_D.get_data()[0] & 1)

    def is_connected(self):
        """Method to check whether the control script is connected to the camera

        NOTE: the control script does not reflect that a camera is connected until
            after the boot up sequence is finished. This can take upwards of 30
            seconds from a powered off state

        Returns:
            bool = True if camera is connected, False otherwise
        """

        self._check_alive()

        try: return bool(self.Stat_D.get_data()[0] & 2)
        except: raise ShmError("Stat D shm may be corrupted. Please kill control script, delete shm, and start again.")

    def is_fan_on(self):
        """Method to check whether the fan is on "automatic" setting

        Returns
            bool = True if fan is set to automatic, False otherwise
        """

        self._check_alive_and_connected()

        try: return bool(self.Stat_D.get_data()[0] & 4)
        except: raise ShmError("Stat D shm may be corrupted. Please kill control script, delete shm, and start again.")

    def is_led_on(self):
        """Method to check whether the led is on

        Returns
            bool = True if led is on, False otherwise
        """

        self._check_alive_and_connected()

        try: return bool(self.Stat_D.get_data()[0] & 8)
        except: raise ShmError("Stat D shm may be corrupted. Please kill control script, delete shm, and start again.")

    def get_tint(self):
        """Method to return the exposure time

        Returns:
            float = the exposure time in seconds
        """

        self._check_alive_and_connected()

        try: return float(self.Exp_D.get_data()[0])
        except: raise ShmError("Exp D shm may be corrupted. Please kill control script, delete shm, and start again.")

    def get_fps(self):
        """Method to return the current frames per second

        Returns:
            int = the FPS setting
        """

        self._check_alive_and_connected()

        try: return int(self.FPS_D.get_data()[0])
        except: raise ShmError("FPS D shm may be corrupted. Please kill control script, delete shm, and start again.")

    def get_ndr(self):
        """Method to return the current NDR setting

        NOTE: an NDR setting of 0 indicates that NDR is off

        Returns:
            int = the NDR setting
        """

        self._check_alive_and_connected()

        try: return int(self.NDR_D.get_data()[0])
        except: raise ShmError("NDR D shm may be corrupted. Please kill control script, delete shm, and start again.")

    def get_crop(self):
        """Method to get the current crop window of the camera

        NOTE: 0, 0, 0, 0 means that subwindowing is off

        Returns:
            a four element list where:
                index   0 = left bound (col min)
                        1 = right bound (col max)
                        2 = upper bound (row min)
                        4 = lower bound (row max)
        """

        self._check_alive_and_connected()

        try: return list(self.Crop_D.get_data())
        except: raise ShmError("Crop D shm may be corrupted. Please kill control script, delete shm, and start again.")

    def get_temp(self, all:bool=False):
        """Method to get the current temperature of the camera

        Args:
            all = whether to return all 6 temperatures (Mother board,
                front end, power board, sensor, peltier, heatsink) or
                just the sensor temperature
        Returns:
            float = the temperature (C) of the sensor (if all is False)
            list  = temperatures (C) of the following components:
                index   0 = mother board
                        1 = front end
                        2 = power board
                        3 = sensor
                        4 = peltier
                        5 = heatsink
        """

        self._check_alive_and_connected()

        # make sure input is a boolean
        if not type(all) is bool:
            raise ValueError("All must be of type bool")

        try:
            if all: return list(self.Temp_D.get_data())
            else: return float(self.Temp_D.get_data()[3])
        except: raise ShmError("Temp D shm may be corrupted. Please kill control script, delete shm, and start again.")

    def grab_n(self, n:int, path:str=None):
        """Grabs a block of images.

        Puts camera parameters into the first and the last header of the cube
            as described in _get_header

        Args:
            n    = the number of images to grab
            path = if not None, the path to store the images
        Returns:
            fits.HDUList
        """

        try:
            assert type(n) is int
            assert path is None or type(path) is str
        except AssertionError:
            raise ValueError("n must be int, path must be str.")

        # grab N images with a header on either side
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

    def save_dark(self, num:int=50, avg:str="mean"):
        """A method used to save dark images

        The path to save the cube of raw images is:
        /nfiudata/YYMMDD/bias_HHMMSS_####_#####_##_#####_###_###_###_###_block.fits
        where YYMMDD and HHMMSS are gmt at start of acquisition and numbered fields are (in order): 
            fps, tint, ndr, temp setpoint, crop left bound, crop right bound, crop upper bound, crop lower bound

        the combined frame is stored with the same name minus block in the same directory as well as
            the same name minus block and the time in the directory specified in bias_dir in Track_Cam.ini
        Args:
            num           = the number of references to take, will appear in header of combined file
            avg           = the means to combine reference images, will appear in header of combined file
        """

        if avg.lower() not in ["mean", "media"]:
            raise ValueError("Unexpected value of 'avg'. Choices are 'mean' or 'median'.")

        gmt = gmtime()
        date = "{}{:02d}{:02d}".format(str(gmt.tm_year)[-2:], gmt.tm_mon, gmt.tm_mday)
        time = "{:02d}{:02d}{:02d}".format(gmt.tm_hour, gmt.tm_min, gmt.tm_sec)
        if not os.path.isdir("/nfiudata"):
            raise FileNotFoundError("No '/nfiudata' folder.")
        if not os.path.isdir("/nfiudata/{}".format(date)):
            os.mkdir("/nfiudata/{}".format(date))
        if not os.path.isdir("/nfiudata/{}/TCReferences".format(date)):
            os.mkdir("/nfiudata/{}/TCReferences".format(date))

        crop = self.get_crop()
        block_path = "/nfiudata/{date}/TCReferences/bias_{time}_{fps:04d}_{tint:0.5f}_{ndr:02d}_{temp:0.5f}_"\
            +"{lb:03d}_{rb:03d}_{ub:03d}_{bb:03d}_block.fits"
        block_path = block_path.format(date=date, time=time, fps = self.get_fps(), tint = self.get_tint(), 
            ndr = self.get_ndr(), temp = self.Temp_P.get_data()[0], lb = crop[0], rb = crop[1], 
            ub = crop[2], bb = crop[3])

        block = self.grab_n(num, block_path)

        # grab a header to pull just the relevant areas of first and last header
        tmp_h = self._get_header()
        # store number of images and avg method
        c_header = {"num":num, "avg":avg}
        # append header data from start frame
        c_header.update({"s{}".format(field):block[0].header[field] for field in tmp_h})
        # append header data from end frame
        c_header.update({"e{}".format(field):block[-1].header[field] for field in tmp_h})

        if avg.lower() == "mean":
            combined = fits.PrimaryHDU(np.mean([im.data for im in block], 0), fits.Header(c_header))
        elif avg.lower() == "median":
            combined = fits.PrimaryHDU(np.median([im.data for im in block], 0), fits.Header(c_header))

        # find file extension
        idx = block_path.rfind(".")
        # prepend combined_ to file name
        combined_path = block_path[:idx-6] + block_path[idx:]
        combined.writeto(combined_path)

        # make filename for bias to be saved in bias folder
        b_dir = self.config.get("Data", "bias_dir")
        if b_dir[-1] != "/": b_dir += "/"
        # get the file name of the combined file already saved
        fname = combined_path[combined_path.rfind("/")+1:]
        # delete HHMMSS from fname
        fname = fname[:5] + fname[12:]
        # save file in darks directory
        combined.writeto(b_dir + fname, overwrite = True)

    def set_fan(self, on:bool):
        """Method to set the on status of the fan

        NOTE: 'on' means automatic, 'off' means manual with a fan speed of 0

        Args:
            on = True to use fan, False to not
        Returns:
            None
        """

        self._check_alive_and_connected()

        # make sure input is a boolean, indicating that user knows what the parameter is
        if not type(on) is bool:
            raise ValueError("on must be of type bool")

        # get current status to avoid changing any other parameters
        try: _ = self.Stat_D.get_data()
        except: raise ShmError("Stat D shm may be corrupted. Please kill control script, delete shm, and start again.")

        # change fan bit to requested value
        if on: _[0] = _[0] | (1 << 2)
        else: _[0] = _[0] & ~(1 << 2)

        # set new status
        try: self.Stat_P.set_data(_)
        except: raise ShmError("Stat P shm may be corrupted. Please kill control script, delete shm, and start again.")

    def set_led(self, on:bool):
        """Method to set the on status of the led

        Args:
            on = True to for led on, False for off
        Returns:
            None
        """

        self._check_alive_and_connected()

        # make sure input is a boolean, indicating that user knows what the parameter is
        if not type(on) is bool:
            raise ValueError("on must be of type bool")

        # get current status to avoid changing any other parameters
        try: _ = self.Stat_D.get_data()
        except: raise ShmError("Stat D shm may be corrupted. Please kill control script, delete shm, and start again.")

        # change led bit to requested value
        if on: _[0] = _[0] | (1 << 3)
        else: _[0] = _[0] & ~(1 << 3)

        # set new status
        try: self.Stat_P.set_data(_)
        except: raise ShmError("Stat P shm may be corrupted. Please kill control script, delete shm, and start again.")

    def set_tint(self, tint:float):
        """Method to set the exposure time of the camera.

        NOTE: any exposure time > 1/fps will result in an error
            (this error is safe, and does not need to be avoided)

        Args:
            tint = the desired exposure time in seconds
        Returns:
            None
        """

        self._check_alive_and_connected()

        # validate input
        try: tint = float(tint)
        except ValueError: raise ValueError("tint must be a float")

        # update error counter to check for updates later
        try: self.Error.get_counter()
        except: raise ShmError("Error shm may be corrupted. Please kill control script, delete shm, and start again.")

        # try to set exposure time
        try: self.Exp_P.set_data(array([tint], self.Exp_P.npdtype))
        except: raise ShmError("Exp P shm may be corrupted. Please kill control script and start again.")

        # give control script time to react
        sleep(.001)

        # check for error update
        if self.Error.mtdata["cnt0"] != self.Error.get_counter():
            err = self.Error.get_data()[0]
            if err == 0: return
            elif err == 2: raise ShmError("Tint invalid.")

    def set_fps(self, fps:int):
        """Method to set the FPS of the camera

        Args:
            fps = the frames per second that the camera should be set at
        Returns:
            None
        """

        self._check_alive_and_connected()

        # validate input
        try: fps = int(fps)
        except ValueError: raise ValueError("fps must be an int")

        # update error counter to check for updates later
        try: self.Error.get_counter()
        except: raise ShmError("Error shm may be corrupted. Please kill control script, delete shm, and start again.")

        # try to set fps
        try: self.FPS_P.set_data(array([fps], self.FPS_P.npdtype))
        except: raise ShmError("FPS P shm may be corrupted. Please kill control script and start again.")

        # give control script time to react
        sleep(.001)

        # check for error update
        if self.Error.mtdata["cnt0"] != self.Error.get_counter():
            err = self.Error.get_data()[0]
            if err == 0: return
            elif err == 2: raise ShmError("FPS Invalid.")

    def set_ndr(self, ndr:int):
        """Method to set the number of non-destructive reads

        Args:
            ndr = the number of non-destructive reads
        Returns:
            None
        """

        self._check_alive_and_connected()

        # validate input
        try: ndr = int(ndr)
        except ValueError: raise ValueError("ndr must be an int")

        # update error counter to check for updates later
        try: self.Error.get_counter()
        except: raise ShmError("Error shm may be corrupted. Please kill control script, delete shm, and start again.")

        # try to set fps
        try: self.NDR_P.set_data(array([ndr], self.NDR_P.npdtype))
        except: raise ShmError("NDR P shm may be corrupted. Please kill control script and start again.")

        # give control script time to react
        sleep(.001)

        # check for error update
        if self.Error.mtdata["cnt0"] != self.Error.get_counter():
            err = self.Error.get_data()[0]
            if err == 0: return
            elif err == 2: raise ShmError("NDR Invalid.")

    def set_crop(self, col_min:int, col_max:int, row_min:int, row_max:int):
        """A method to set the sub-window cropping on the camera

        NOTE: to turn off subwindowing, pass 0, 0, 0, 0

        Args:
            col_min = the min collumn index to use (0 = full frame)
            col_max = the max collumn index to use (639 = full frame)
            row_min = the min collumn index to use (0 = full frame)
            row_max = the max collumn index to use (511 = full frame)
        Returns:
            None
        """

        self._check_alive_and_connected()

        # validate input
        try: 
            col_min = int(col_min)
            col_max = int(col_max)
            row_min = int(row_min)
            row_max = int(row_max)
        except ValueError: raise ValueError("crop bounds must be ints")

        # update error counter to check for updates later
        try: self.Error.get_counter()
        except: raise ShmError("Error shm may be corrupted. Please kill control script, delete shm, and start again.")

        # try to set fps
        try: self.Crop_P.set_data(array([col_min, col_max, row_min, row_max], self.Crop_P.npdtype))
        except: raise ShmError("Crop P shm may be corrupted. Please kill control script and start again.")

        # give control script time to react
        sleep(.001)

        # check for error update
        if self.Error.mtdata["cnt0"] != self.Error.get_counter():
            err = self.Error.get_data()[0]
            if err == 0: return
            elif err == 2: raise ShmError("Crop Invalid.")

    def set_temp(self, temp:float, rate:float=5):

        """A method to set the target temp of the camera's sensor

        NOTE: temperatures in Temp_D are updated every <rate> seconds

        Args:
            temp = the target temp in Celcius
            rate = the poll rate (in s) to update the Temp D shm
        Returns:
            None
        """

        self._check_alive_and_connected()

        # validate input
        try: 
            temp = float(temp)
            rate = float(rate)
        except ValueError: raise ValueError("temp and rate must be floats")

        # update error counter to check for updates later
        try: self.Error.get_counter()
        except: raise ShmError("Error shm may be corrupted. Please kill control script, delete shm, and start again.")

        # try to set fps
        try: self.Temp_P.set_data(array([temp, rate], self.Temp_P.npdtype))
        except: raise ShmError("Temp P shm may be corrupted. Please kill control script and start again.")

        # give control script time to react
        sleep(.001)

        # check for error update
        if self.Error.mtdata["cnt0"] != self.Error.get_counter():
            err = self.Error.get_data()[0]
            if err == 0: return
            elif err == 2: raise ShmError("Temp Invalid.")

    def connect_camera(self, wait:bool=True):
        """A method to tell the control script to connect to the camera

        Args:
            wait = whether this method should block until either the camera has booted up
                or an error has been encountered.
        Returns:
            None
        """

        self._check_alive()

        try: self.Stat_P.set_data(array([3], self.Stat_P.npdtype))
        except: raise ShmError("Stat P shm may be corrupted. Please kill control script and start again.")

        # make a counter to cap wait time at 2 min
        cnt = 0
        # update Error counter
        self.Error.get_counter()
        # wait for Stat_D to reflect that the camera is on or for error to be updated
        while not self.is_connected():
            if cnt >= 120:
                raise TimeoutError("Timeout on camera connection.")
            if self.Error.mtdata["cnt0"] != self.Error.get_counter():
                err = self.Error.get_data()[0]
                if err == 3: raise FliError("Fli Error during startup.")
                elif err == 4: raise MissingCamera("No camera found by SDK.")
                elif err == 5: raise MissingGrabber("No frame grabber found by SDK.")
            cnt += 1
            sleep(1)

        self.set_fan(True)

    def turn_off_camera(self, wait:bool=True):
        """A method to tell the control script to disconnect from and turn off the camera

        Args:
            wait = whether this method should block until either the camera has turned off
                or an error has been encountered
        Returns:
            None
        """

        self._check_alive_and_connected()

        try: self.Stat_P.set_data(array([1], self.Stat_P.npdtype))
        except: raise ShmError("Stat P shm may be corrupted. Please kill control script and start again.")

        # make a counter to cap wait time at 2 min
        cnt = 0
        # update Error counter
        self.Error.get_counter()
        # wait for Stat_D to reflect that the camera is off or for error be updated
        while self.is_connected():
            if cnt >= 120:
                raise TimeoutError("Timeout on camera connection.")
            if self.Error.mtdata["cnt0"] != self.Error.get_counter():
                err = self.Error.get_data()[0]
                if err == 3: raise FliError("Fli Error during startup.")
                elif err == 4: raise MissingCamera("No camera found by SDK.")
                elif err == 5: raise MissingGrabber("No frame grabber found by SDK.")
            cnt += 1
            sleep(1)

    def activate_control_script(self=None):
        """A method to start the control script for the Tracking Camera"""

        if self.is_active():
            raise ScriptAlreadActive("Tracking camera control script already alive.")

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
        """A method to throw an exception if control script is not alive"""

        if not self.is_active():
            raise ScriptOff("No active control script. Please use 'TC.activate_control_script()'.")

    def _check_alive_and_connected(self):
        """A method to throw an exception if control script is not alive
            or if camera is not connected"""

        self._check_alive()

        if not self.is_connected():
            raise CameraOff("Camera is not connected. Please use 'TC.connect_camera'.")

    def _handle_shms(self):
        """Connect to any shms that need to be connected to, disconnect from any
            P shms that need to be disconnected from."""

        # P shms created in control script
        if type(self.Stat_P) is str:
            if os.path.isfile(self.Stat_P):
                try:
                    self.Stat_P = Shm(self.Stat_P)
                    self.Crop_P = Shm(self.Crop_P)
                    self.NDR_P  = Shm(self.NDR_P)
                    self.FPS_P  = Shm(self.FPS_P)
                    self.Temp_P = Shm(self.Temp_P)
                    self.Exp_P  = Shm(self.Exp_P)
                except: raise ShmError("Please restart python session. If issue persists, disconnect from and reconnect to camera.")
        else:
            if not os.path.isfile(self.Stat_P.fname):
                try:
                    self.Stat_P = self.Stat_P.fname
                    self.Crop_P = self.Crop_P.fname
                    self.NDR_P  = self.NDR_P.fname
                    self.FPS_P  = self.FPS_P.fname
                    self.Temp_P = self.Temp_P.fname
                    self.Exp_P  = self.Exp_P.fname
                except: raise ShmError("A P shm may have been deleted. Please disconnect from and reconnect to camera.")

        # D shms created in observer (when camera connects)
        if type(self.Img) is str:
            # D shms created in control script
            if type(self.Stat_D) is str: 
                if os.path.isfile(self.Stat_D):
                    try:
                        self.Stat_D = Shm(self.Stat_D)
                        self.Temp_D = Shm(self.Temp_D)
                        self.Error  = Shm(self.Error)
                    except: raise ShmError("Please restart python session. If issue persists, restart control script.")
            if os.path.isfile(self.Img):
                try:
                    self.Img    = Shm(self.Img)
                    self.FPS_D  = Shm(self.FPS_D)
                    self.Exp_D  = Shm(self.Exp_D)
                    self.NDR_D  = Shm(self.NDR_D)
                    self.Crop_D = Shm(self.Crop_D)
                except: raise ShmError("Please restart python session. If issue persists, restart control script.")

    def _get_header(self):
        """Returns a dictionary of camera parameters that can be used as a fits header
        
            contains the following info:
                fps           = the fps of the camera
                tint          = the exposure time (in s) of the camera
                ndr           = the number of non-destructive reads of the camera
                temp_MB       = the last reported temperature of the mother board
                temp_FE       = the last reported temperature of the front end
                temp_PB       = the last reported temperature of the power board
                temp_se       = the last reported temperature of the sensor
                temp_pe       = the last reported temperature of the peltier
                temp_he       = the last reported temperature of the heatsink
                t_setp        = the sensor temperature setpoint
                crop_LB       = the left bound of the subwindow (0 indexed)
                crop_RB       = the right bound of the subwindow (0 indexed)
                crop_UB       = the upper bound of the subwindow (0 indexed)
                crop_BB       = the lower (bottom) bound of the subwindow (0 indexed)
        """

        self._check_alive_and_connected()

        fps     = self.get_fps()
        tint    = self.get_tint()
        ndr     = self.get_ndr()
        temps   = self.get_temp(True)
        temp_sp = self.Temp_P.get_data()[1]
        crop    = self.get_crop()

        return fits.Header({"fps":fps, "tint":tint, "ndr":ndr, "temp_MB":temps[0], "temp_FE":temps[1],
            "temp_PB":temps[2], "temp_se":temps[3], "temp_pe":temps[4], "temp_he":temps[5], "t_setp":temp_sp,
            "crop_LB":crop[0], "crop_RB":crop[1], "crop_UB":crop[2], "crop_BB":crop[3]})

######## Errors ########

class CameraOff(Exception):
    """An error to be thrown when a command is sent and the camera is off"""
    pass

class FliError(Exception):
    """An error to be thrown when there's an error with the 
    First Light library"""
    pass

class MissingCamera(Exception):
    """An error to be thrown when no camera can be found"""
    pass

class MissingGrabber(Exception):
    """An error to be thrown when no frame grabber can be found"""
    pass