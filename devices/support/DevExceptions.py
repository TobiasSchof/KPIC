class NoSharedMemory(Exception):
    """An exception to be thrown when necessary shared memory is not alive."""
    pass

class MovementRange(Exception):
    """An exception to be thrown when a movement outside of the device's limits is requested"""
    pass

class UnreferencedAxis(Exception):
    """An exception to be thrown when a move is requested but stage is unreferenced."""
    pass

class MovementTimeout(Exception):
    """An exception to be thrown when the control script stops motion because of a timeout"""
    pass

class StageOff(Exception):
    """An exception to be thrown when a command is sent but the stage is off"""
    pass

class ScriptOff(Exception):
    """An exception to be thrown when a command is sent but the script is off"""
    pass
