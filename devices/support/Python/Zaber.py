# python standard library
from telnetlib import Telnet
from time import sleep
import struct, logging

# vendor library
from zaber.serial import BinaryCommand, BinaryReply, BinaryDevice, BinarySerial

# set up logger like zaber serial
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
debug = logging.debug

"""
This is an extension of the Zaber library to add telnet communication to the binary protocol,
    as well as more user-friendly functions
"""

class BinaryTelnet():
    """A class for interacting with Zaber devices via telnet using the Binary protocol.

    This class is modifiedd from BinarySerial
    """

    def __init__(self, host:str, port:int, timeout = 5):
        """Creates a new instance of the BinarySerial class.

        Args:
            host: the hostname for the telnet connection
            port: the port to connect to <host> on
            timeout: A number representing the number of seconds to wait
                for a reply. Fractional numbers are accepted and can be
                used to specify times shorter than a second.

        Notes:
            This class will open the port immediately upon
            instantiation. This follows the pattern set by PySerial,
            which this class uses internally to perform serial
            communication.

        Raises:
            TypeError: The port argument passed was not an int.
            TypeError: The host argument passed was not a string.
        """
        if not isinstance(port, int):
            raise TypeError("port must be an int.")
        if not isinstance(host, str):
            raise TypeError("host must be a str.")

        self.host = host
        self.port = port
        self.timeout = timeout
        self._tel = Telnet()
        self._tel.open(self.host, self.port, 3)

    def write(self, *args):
        """Writes a command to the port.

        This function accepts either a BinaryCommand object, a set
        of integer arguments, a list of integers, or a string. 
        If passed integer arguments or a list of integers, those
        integers must be in the same order as would be passed to the
        BinaryCommand constructor (ie. device number, then command
        number, then data, and then an optional message ID).

        Args:
            *args: A BinaryCommand to be sent, or between 2 and 4
                integer arguements, or a list containing between 2 and
                4 integers, or a string representing a 
                properly-formatted Binary command.
                
        Notes:
            Passing integers or a list of integers is equivalent to
            passing a BinaryCommand with those integers as constructor
            arguments.

            For example, all of the following are equivalent::

                >>> write(BinaryCommand(1, 55, 1000))
                >>> write(1, 55, 1000)
                >>> write([1, 55, 1000])
                >>> write(struct.pack("<2Bl", 1, 55, 1000))
                >>> write('\x01\x37\xe8\x03\x00\x00')

        Raises:
            TypeError: The arguments passed to write() did not conform
                to the specification of ``*args`` above.
            ValueError: A string of length other than 6 was passed.
        """
        if len(args) == 1:
            message = args[0]
            if isinstance(message, list):
                message = BinaryCommand(*message)
        elif 1 < len(args) < 5:
            message = BinaryCommand(*args)
        else:
            raise TypeError("write() takes at least 1 and no more than 4 "
                    "arguments ({0:d} given)".format(len(args)))

        if isinstance(message, str):
            logger.debug("> %s", message)
            if len(message) != 6:
                raise ValueError("write of a string expects length 6.")

            # pyserial doesn't handle hex strings.
            if sys.version_info > (3, 0):
                data = bytes(message, "UTF-8") 
            else:
                data = bytes(message) 

        elif isinstance(message, BinaryCommand):
            data = message.encode()
            logger.debug("> %s", message)

        else:
            raise TypeError("write must be passed several integers, or a "
                    "string, list, or BinaryCommand.")

        self._tel.write(data)

    def read(self, message_id = False):
        """Reads six bytes from the port and returns a BinaryReply.

        Args:
            message_id: True if the response is expected to have a 
                message ID. Defaults to False.

        Returns:
            A BinaryCommand containing all of the information read from
            the serial port.

        Raises: 
            zaber.serial.TimeoutError: No data was read before the 
                specified timeout elapsed.
        """
        reply = b''
        # TODO: add a timeout so this doesn't block infinitely
        for idx in range(0, 6):
            reply += self._tel.rawq_getchar()

        if len(reply) != 6:
            logger.debug("< Receive timeout!")
            raise TimeoutError("read timed out.")

        parsed_reply = BinaryReply(reply, message_id)
        logger.debug("< %s", parsed_reply)
        return parsed_reply

    def flush(self):
        """Flushes the buffers of the underlying serial port."""
        self._tel.read_eager()

    def open(self):
        """Opens the serial port."""
        self._tel.open(self.host, self.port, self.timeout)

    def close(self):
        """Closes the serial port."""
        self._tel.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._tel.close()

class Zaber_Device():
    """A class to control the zabers"""

    def __init__(self, axis_def:dict = None, mstep2mm:float = None):
        """Initializes the Zaber class

        Args:
            axis_def = a dictionary containing keys that correspond to
                serial numbers and values that correspond to axes as they
                will be interacted with. Defaults to FEU bundle zaber
                values if left None
            mstep2mm = the conversion from microsteps to millimeters.
                Deefaults to the value for T_NA series if None.
        """

        if axis_def is not None: self.AXIS_DEF = axis_def
        else: self.AXIS_DEF = {48810:"x", 48811:"y", 48809:"f"}

        if mstep2mm is not None: self.MSTEP2MM = mstep2mm
        else: self.MSTEP2MM =0.047625/1000 

        self.con_type = None

    ##### Connection methods ##### 

    def open_serial(self, devnm:str, baud:int):
        """Opens connection with a serial Zaber device

        Args:
            devnm = the device name to connect to
            baud  = the baudrate to connect at
        Returns:
            int = an error code if one occurs, if not: 0

        Raises:
            AttributeError if not all axes in self.AXIS_DEF are found
        """

        # create a BinarySerial object for communication
        self.port = BinarySerial(devnm, baud)

        # renumbering axes ensures that they're set up correctly
        self.__renumber()

        # instantiate devices (one per axis)
        axes = [BinaryDevice(self.port, con) for con in [1, 2, 3]]

        self.con_type = "serial"

        ret = self.__setup(axes)

        if ret == 0:
            self.con_type = "serial"

        return ret

    def open_telnet(self, host:str, port:int):
        """Opens connection with a serial Zaber device

        Args:
            devnm = the device name to connect to
            baud  = the baudrate to connect at
        Returns:
            int = an error code if one occurs, if not: 0

        Raises:
            AttributeError if not all axes in self.AXIS_DEF are found
        """

        # create a BinarySerial object for communication
        self.port = BinaryTelnet(host, port)

        # renumbering axes ensures that they're set up correctly
        self.__renumber()

        # instantiate devices (one per axis)
        axes = [BinaryDevice(self.port, con) for con in [1, 2, 3]]


        ret = self.__setup(axes)

        if ret == 0:
            self.con_type = "telnet"

        return ret

    def __setup(self, axes):
        """An internal method to finish the connection process, agnostic of
           connection type
        
        Args:
            axes = a list containing BinaryDevice instances per axis
        Returns:
            int = an error code if one occurs, if not: 0
        """

        # use AXIS_DEF to find which device is which
        self.axes = {}
        for axis in axes:
            # read serial number
            reply = axis.send(63)
            # check for error
            if reply.command_number == 255:
                debug("Error getting SN from device {}.".format(axis))
                return reply.data

            # put device in devs dict with key corresponding to axis
            try: self.axes[self.AXIS_DEF[reply.data]] = axis
            except: pass

        # check that all axes were found
        if not len(self.axes) == len(self.AXIS_DEF):
            self.close()
            msg = "Not all axes could be found. Looking "+\
                "for axes {} and found axes {}.".format(self.AXIS_DEF, self.axes)
            raise AttributeError(msg)

        return 0

    def close(self):
        """Closes connection to the device and parks it (to prepare for shutdown)"""

        # Zabers on nfiuserver have firmware version 5.xx so can't park

        # close connections
        self.port.close()

        self.con_type = None

    ##### Query methods #####

    def getPos(self, axes:list):
        """Returns the current position of the given axes

        Args:
            axes = the axes to query (from keys of self.axes)
                NOTE: "all" can be used to query all
        Returns:
            dict = keys are axes, values are position in mm
            int = error code if an error is encountered
        """

        # check if a singular axis was passed or if "all" was passed
        if type(axes) is str: 
            if axes.lower() == "all": axes = list(self.axes.keys())
            else: axes = [axes]

        ret = {}
        for axis in axes:
            reply = self.axes[axis].send(60)
            
            # if there is an error, return it
            if reply.command_number == 255:
                debug("Error {} encountered on axis {}.".format(reply.data, axis))
                return reply.data

            # convert position to mm
            ret[axis] = reply.data * self.MSTEP2MM

        return ret

    def isMoving(self, axes:list, homing=True):
        """Returns whether the given axes are moving

        Args:
            axes = the axes to query (from keys of self.axes)
                NOTE: "all" can be used to query all
            homing = whether to check if the axes are homing as well
        Returns:
            dict = keys are axes, values True/False for moving/not
            int = error code if an error is encountered
        """

        # check if a singular axis was passed or if "all" was passed
        if type(axes) is str: 
            if axes.lower() == "all": axes = list(self.axes.keys())
            else: axes = [axes]

        ret = {}
        for axis in axes:
            reply = self.axes[axis].send(54)
            
            # if there is an error, return it
            if reply.command_number == 255:
                debug("Error {} encountered on axis {}.".format(reply.data, axis))
                return reply.data

            # 0 is idle, 1 is homing
            ret[axis] = reply.data != 0 if homing else reply.data > 1

        return ret

    def isLEDOn(self, axes:list):
        """Query whether the LEDs on the specified axes are on

        Each axis has two LEDs, this will return whether either is on.

        Args:
            axes = the axes to query (from keys of self.axes)
                NOTE: "all" can be used to query all
        Returns:
            dict = keys are axes, values booleans reflecting LED status
            or 
            int = error code if an error occurred
        """

        # check if a singular axis was passed or if "all" was passed
        if type(axes) is str: 
            if axes.lower() == "all": axes = list(self.axes.keys())
            else: axes = [axes]

        ret = {}
        for axis in axes:
            devmd = self.getDevMode(axis)

            # if devmd is an int, it's an error code
            if type(devmd) is int: return devmd
            else: devmd = devmd[axis]

            # bit 14 is power LED
            # bit 15 is serial LED
            ret[axis] = not devmd & 1 << 14 or not devmd & 1 << 15

        return ret

    def isHomed(self, axes:list):
        """Returns whether the specified axes are homed

        Args:
            axes = the axes to query (from keys of self.axes)
                NOTE: "all" can be used to query all
        Returns:
            dict = keys are axes, values True/False for homed/not homed
            int = error mcode if an error is encountered
        """

        # check if a singular axis was passed or if "all" was passed
        if type(axes) is str: 
            if axes.lower() == "all": axes = list(self.axes.keys())
            else: axes = [axes]

        ret = {}
        for axis in axes:
            devmd = self.getDevMode(axis)

            # if devmd is an int, it's an error code
            if type(devmd) is int: return devmd
            else: devmd = devmd[axis]

            # bit 14 is power LED
            # bit 15 is serial LED
            ret[axis] = bool(devmd & 1 << 7)

        return ret

    def isAntiBacklashOn(self, axes:list):
        """Returns whether antibacklash is enabled for the given axes

        Args:
            axes = the axes to query (from keys of self.axes)
                NOTE: "all" can be used to query all
        Returns:
            dict = keys are axes, values True/False for AB/no AB
            int = error mcode if an error is encountered
        """

        # check if a singular axis was passed or if "all" was passed
        if type(axes) is str: 
            if axes.lower() == "all": axes = list(self.axes.keys())
            else: axes = [axes]

        ret = {}
        for axis in axes:
            devmd = self.getDevMode(axis)

            # if devmd is an int, it's an error code
            if type(devmd) is int: return devmd
            else: devmd = devmd[axis]

            ret[axis] = bool(devmd & 1 << 1)
        
        return ret

    def isAntiSticktionOn(self, axes:list):
        """Returns whether antisticktion is enabled for the given axes

        Args:
            axes = the axes to query (from keys of self.axes)
                NOTE: "all" can be used to query all
        Returns:
            dict = keys are axes, values True/False for AS/no AS
            int = error mcode if an error is encountered
        """

        # check if a singular axis was passed or if "all" was passed
        if type(axes) is str: 
            if axes.lower() == "all": axes = list(self.axes.keys())
            else: axes = [axes]

        ret = {}
        for axis in axes:
            devmd = self.getDevMode(axis)

            # if devmd is an int, it's an error code
            if type(devmd) is int: return devmd
            else: devmd = devmd[axis]

            ret[axis] = bool(devmd & 1 << 2)

        return ret

    def getDevMode(self, axes:list):
        """Returns the Device Mode bits of the specified axes

        Args:
            axes = the axes to query (from keys of self.axes)
                NOTE: "all" can be used to query all
        Returns:
            dict = keys are axes, values ints representing the mode bit
                NOTE: see https://www.zaber.com/manuals/T-NA#m-7-119-set-device-mode-cmd-40 for meaning
            int = error mcode if an error is encountered
        """

        # check if a singular axis was passed or if "all" was passed
        if type(axes) is str: 
            if axes.lower() == "all": axes = list(self.axes.keys())
            else: axes = [axes]

        ret = {}
        for axis in axes:
            # request device mode
            reply = self.axes[axis].send(53, 40)

            # check for error
            if reply.command_number == 255:
                debug("Error {} encountered.".format(reply.data))
                return reply.data

            # otherwise put bit in return dictionary
            ret[axis] = reply.data

        # return list
        return ret

    def getMaxMove(self, axes:list):
        """Returns the maximum position (mm) of each axis

        Args:
            axes = the axes to query (from keys of self.axes)
                NOTE: "all" can be used to query all
        Returns:
            dict = keys are axes, values True/False for AS/no AS
            int = error code if an error is encountered
        """

        # check if a singular axis was passed or if "all" was passed
        if type(axes) is str: 
            if axes.lower() == "all": axes = list(self.axes.keys())
            else: axes = [axes]

        ret = {}
        for axis in self.axes:
            # request information on max move
            reply = self.axes[axis].send(53, 44)

            # if there was an error, return it 
            if reply.command_number == 255:
                debug("Error {} encountered with axis {}.".format(reply.data, axis))
                return reply.data

            # convert microsteps to mm
            ret[axis] = reply.data * self.MSTEP2MM

        return ret

    ##### Command methods #####

    def home(self, axes:list):
        """Homes the given axes

        Args:
            axes = the axes to query (from keys of self.axes)
                NOTE: "all" can be used to query all
        Returns:
            int = error code if error occurs, 0 otherwise
        """

        # check if a singular axis was passed or if "all" was passed
        if type(axes) is str: 
            if axes.lower() == "all": axes = list(self.axes.keys())
            else: axes = [axes]

        for axis in axes:
            reply = self.axes[axis].home()

            # check reply for error
            if reply.command_number == 255:
                debug("Error {} occurred with axis {}.".format(reply.data, axis))
                return reply.data

        return 0

    def reset(self):
        """Resets all axes

        Puts all axes into a not-homed state"""

        self.port.write(0, 0, 0)
        # sleep to allow device time to respond
        sleep(1)
        self.port.flush()
        
    def moveAbs(self, target:dict):
        """Performs requested moves

        Does not check limits before sending command.

        Args:
            target = keys are axes, values are target (in mm)
        Returns:
            int = error codde if an error occured, 0 otherwise
        """

        for axis in target:
            # convert mm to steps
            pos = int(round(target[axis] / self.MSTEP2MM))
            reply = self.axes[axis].move_abs(pos)

            # check for error
            if reply.command_number == 255:
                debug("Error {} occurred with axis {}.".format(reply.data, axis))
                return reply.data

        return 0

    def setAntiBacklash(self, vals:dict):
        """Turns anti backlash for the given axes on/off

        Args:
            vals = keys as axes, values as True/False for on/off
        Returns:
            int = error code if an error occured, 0 otherwise
        """

        for axis in vals:
            # get the current device mode to avoid changing any other bits
            stat = self.getDevMode(axis)

            # check for error
            if type(stat) is int:
                debug("Error {} occurred with axis {}.".format(stat, axis))
                return stat

            stat = stat[axis]

            # set anti-backlash bit
            if vals[axis]:
                stat = stat | (1 << 1)
            else:
                stat = stat & ~(1 << 1)

            # send new device mode
            reply = self.axes[axis].send(40, stat)

            # check for error
            if reply.command_number == 255:
                debug("Error {} occurred with axis {}.".format(reply.data, axis))
                return reply.data

        return 0

    def setAntiSticktion(self, vals:dict):
        """Turns anti sticktion for the given axes on/off

        Args:
            vals = keys as axes, values as True/False for on/off
        Returns:
            int = error code if an error occured, 0 otherwise
        """

        for axis in vals:
            # get the current device mode to avoid changing any other bits
            stat = self.getDevMode(axis)

            # check for error
            if type(stat) is int:
                debug("Error {} occurred with axis {}.".format(stat, axis))
                return stat

            stat = stat[axis]

            # set anti-sticktion bit
            if vals[axis]:
                stat = stat | (1 << 2)
            else:
                stat = stat & ~(1 << 2)

            # send new device mode
            reply = self.axes[axis].send(40, stat)

            # check for error
            if reply.command_number == 255:
                debug("Error {} occurred with axis {}.".format(reply.data, axis))
                return reply.data

        return 0

    def setLED(self, vals:dict):
        """Turns leds for the given axes on/off

        NOTE: Zabers have two LEDs, a serial LED and a power LED, both will be changed

        Args:
            vals = keys as axes, values as True/False for on/off
        Returns:
            int = error code if an error occurred, otherwise 0
        """

        for axis in vals:
            # get the current device mode to avoid changing any other bits
            stat = self.getDevMode(axis)

            # check for error
            if type(stat) is int:
                debug("Error {} occurred with axis {}.".format(stat, axis))
                return stat

            stat = stat[axis]

            # set led bits
            if vals[axis]:
                stat = stat | (1 << 14) | (1 << 15)
            else:
                stat = stat & ~(1 << 15 | 1 << 14)

            # send new device mode
            reply = self.axes[axis].send(40, stat)

            # check for error
            if reply.command_number == 255:
                debug("Error {} occurred with axis {}.".format(reply.data, axis))
                return reply.data

        return 0

    def __renumber(self):
        """Sends the renumber command to all axes"""

        # send renumber to all devices
        self.port.write(0,2,0)
        sleep(1)
        self.port.flush()
        