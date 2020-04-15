class ShmError(Exception):
    """An exception to be thrown when necessary shared memory is not alive."""
    pass

class MovementRange(Exception):
    """An exception to be thrown when a movement outside of the device's limits
    is requested"""
    pass

class UnreferencedAxis(Exception):
    """An exception to be thrown when a move is requested but stage is
    unreferenced."""
    pass

class MovementTimeout(Exception):
    """An exception to be thrown when the control script stops motion because
    of a timeout"""
    pass

class StageOff(Exception):
    """An exception to be thrown when a command is sent but the stage is off"""
    pass

class ScriptOff(Exception):
    """An exception to be thrown when a command is sent but the script is off"""
    pass

class ScriptAlreadActive(Exception):
    """An exception to be thrown if control script activation is attempted when
    there's already an active script."""
    pass

class LoopOpne(Exception):
    """An exception too be thrown if movement is requested while the loop is
    open on a stage without open loop movement support."""
    pass
