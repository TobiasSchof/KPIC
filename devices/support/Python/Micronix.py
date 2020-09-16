from serial import Serial
from time import sleep
from telnetlib import Telnet
from logging import debug

class TimeoutError(Exception):
    """An error to be thrown for a movement timeout"""
    pass

# TODO: Can I check which axis are connected in open_x?

class Micronix_Device():
    """Class for controlling Micronex stages"""

    def __init__(self):
        """Constructor
        
        Args:
            precision = how far a controller can report a stage as being
                from target before it is considered on target
        """

        # a variable to keep track of what kind of connection is open
        self.con_type = None

    def open_Serial(self, devnm:str, baud:int):
        """Opens a serial connection to a device

        Does nothing if a connection is already open
        Args:
            devnm = the device name to connect to
            baud = the baudrate
        """

        # if connection is already open, return
        if not self.con_type is None:
            debug("Device is already open. Cannot open {}".format(devnm))
            return

        debug("Connecting to serial: {}:{}...".format(devnm, baud))
        self.con = Serial()
        self.con.port = devnm
        self.con.baudrate = baud
        self.con.timeout = 1
        self.con.open()
        self.con_type = "serial"

    def open_Telnet(self, host:str, port:int):
        """Opens a telnet connection to device

        Does nothing if a connection is already open
        Args:
            host = the hostname of the telnet connection
            port = the port to connect to
        """

        # if connection is already open, return
        if not self.con_type is None:
            debug("Device is already opeen. Cannot open {}".format(host))
            return
        
        debug("Connecting to telnet: {}:{}...".format(host, port))
        self.con = Telnet()
        self.con.timeout = 1
        self.con.open(host, port)
        self.con_type = "telnet"

        #TODO: check: is first message ignored?

    def close_Connection(self):
        """Closes whatever connection is currently open"""

        # if there is no connection, return
        if self.con_type is None:
            debug("Connection is not open, doing nothing.")
            return

        debug("Closing {} connection".format(self.con_type))
        self.con.close()
        self.con_type = None

    def close(self):
        """Closes the device connection if open"""

        if self.con_type is None:
            debug("Cannot close device connection. Already closed.")
        else:
            self.con.close()
            self.con_type = None

    def move(self, newPOS:dict, isBlocking:bool = False):
        """Moves this device to the given position

        Args:
            newPOS = a dict where keys correspond to axis, values to positions
            isBlocking = a boolean that will block the program until the move is
                done.
        """

        debug("Performing the following moves: {}".format(newPOS))

        # for each axis, prep a syncronous move
        msg = ""
        for axis in newPOS:
            msg += "{}MSA{};".format(axis, newPOS[axis])

        # get rid of last semicolon
        msg = msg[:-1]

        # add run command to execute
        msg += "\n0RUN"

        # send command
        self._write(msg)

        # if program execution should be blocked, sleep until position is within precision
        # block for no more than 5 seconds
        cnt = 0
        if isBlocking:
            for axis in newPOS:
                while self.isMoving(axis)[axis] and cnt < 500:
                    sleep(.01)
                    cnt += 1

    def isMoving(self, axes:list) -> dict:
        """A method to check whether the given axes are moving

        Args:
            axes = a list of axes to check
        Returns:
            dict = keys as axes, values as True/False for moving/not
        """

        # if axes is a singleton, make it a list
        if type(axes) is int: axes = [axes]

        # for each axis, get status and check bit 3
        ret = {axis:(self._query("{}STA?".format(axis) & 8)) for axis in axes}

        # return values
        return ret

    def isConnected(self) -> bool:
        """Returns whether this device is connected

        Returns:
            bool = True if device is connected, False otherwise
        """

        return self.con_type is not None

    def home(self, axes:list, isBlocking:bool = False):
        """A method to home the given axes

        Args:
            axes = the axes to home. Also accepts an int
            isBlocking = whether this method should block execution until all 
                home commands are complete
        """

        debug("Homing the following axes: {}".format(axes))

        # convert axes to list if an int was provided
        if type(axes) is int: axes = [axes]

        # request a home for each axis
        for axis in axes:
            self._write("{}HOM".format(axis))

        # block for no more than 5 seconds
        cnt = 0
        if isBlocking:
            for axis in axes:
                while not self.isHomed(axis)[axis] and cnt < 500:
                    sleep(.01)
                    cnt += 1

    def reset(self, axes:list, isBlocking:bool = False):
        """A method to reset the given axes

        Args:
            axes = the axes to reset. Also accepts an int
            isBlocking = whether this method should block execution until all 
                home commands are complete
        """

        debug("Homing the following axes: {}".format(axes))

        # convert axes to list if an int was provided
        if type(axes) is int: axes = [axes]

        # request a reset for each axis
        for axis in axes:
            self._write("{}RST".format(axis))

        # block for no more than 5 seconds
        cnt = 0
        if isBlocking:
            for axis in axes:
                while self.isHomed(axis)[axis] and cnt < 500:
                    sleep(.01)
                    cnt += 1

    def setLoopState(self, target:dict):
        """A method to set the loop state

        Args:
            target = keys as axes, values as a valid FBK state
        """

        debug("Setting the following loop states: {}".format(target))

        for axis in target: self._write("{}FBK{}".format(axis, target[axis]))

    def getLoopState(self, axes:list) -> dict:
        """A method to change the loop state

        Args:
            axes = list of axes (or axis) to query
        Returns:
            dict = keys as axes, values as ints representing FBK options for controller
        """

        debug("Requesting loop state for the following axes: {}".format(axes))

        # if a single axis was provided, format it as a list
        if type(axes) is int: axes = [axes]

        # check FBK status for each axis
        ret = {axis:self._query("{}FBK?".format(axis)) for axis in axes}

        return ret

    def isHomed(self, axes:list) -> dict:
        """A method to check whether the given axes are homed

        Args:
            axes = which axes (or axis) to query. Also accepts an int
        Returns:
            dict = keys as axis, values as True/False for homed/not
        """

        debug("Checking if the following axes are homed: {}".format(axes))

        # convert axes to list if an int was provided
        if type(axes) is int: axes = [axes]

        # request homed status for each axis
        ret = {axis:self._query("{}HOM?".format(axis)) for axis in axes}

        return ret

    def getPos(self, axes:list) -> dict:
        """A method to return the current position of the device.

        Args:
            axes = the axes to query, also accepts an int
        Returns:
            dict = keys correspond to axes, values to current position
        """

        debug("Getting the current position for the following axes: {}".format(axes))

        # if a single axis was supplied, store it as a list
        if type(axes) is int: axes = [axes]

        # query position for each axis and store results
        # the controller returns position as theoretical,actual
        ret = {axis:self._query("{}POS?".format(axis)).split(",")[1] for axis in axes}

        return ret

    def getError(self, axes:list) -> dict:
        """A method to get the stored error and clear it from controller's memory

        Args:
            axes = the list axes to get errors for, also accepts an int
        Returns:
            dict = keys correspond to axes, values to errors
        """

        debug("Getting stored errors for the following axes: {}".format(axes))

        # if a single axis was supplied, store it as a list
        if type(axes) is int: axes = [axes]

        # if there's no error, we'll get a timeout, so set timeout to a short time
        tmp = self.con.timeout
        self.con.timeout = .1

        # query error for each axis and store results
        ret = {axis:self._query("{}ERR?".format(axis)) for axis in axes}
        ret = {axis:0 if ret[axis] == '' else int(ret[axis].split(" ")[1]) for axis in ret}

        # change timeout back
        self.con.timeout = tmp

        return ret

    def _write(self, MSG:str):
        """Formats a <MSG> to be sent to the stage

        <MSG> should be a normal string and not end in CR\LF
        Args:
            MSG = a string containing a command (e.g. "1VER?")
        """

        # raise an error if MSG isn't a string
        try: assert type(MSG) is str
        except AssertionError as e:
            raise ValueError("Message to send must be a string.")

        # if there is already a carriage return, no need to add one
        if MSG.endswith("\r"):
            debug("Sending message: {}\\r".format(MSG[:-1]))
            self.con.write(MSG.encode())
        else:
            debug("Sending message: {}\\n\\r".format(MSG))
            self.con.write((MSG+"\n\r").encode())

    def _query(self, MSG:str) -> str:
        """Formats query <MSG> to be sent and returns result

        <MSG> should end in a ?
        Args:
            MSG = a string containing a query command
        Returns:
            str = the device's response
        """

        # validate MSG
        try: 
            assert type(MSG) is str
            assert MSG[-1] == "?" or MSG[-2:] == "?\r" or MSG[-3:] == "?\n\r" 
        except AssertionError as e:
            raise ValueError("Message to send must be a string ending in ?.")

        # send query
        self._write(MSG)

        # read response, stripping new line carriage return at end and # at beginning
        return self.con.read_until("\n\r".encode())[1:-2].decode()