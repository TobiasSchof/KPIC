'''
Library to fake NPS support on the AOSE machine.
'''

def ConnectionError(Exception):
    """A connection to be thrown on connection error"""
    pass

class NPS_cmds(object):
    '''--------------------------------------------------------------
    Class for controlling the pulizzi NPS.
    
    * NOTE: This class is currently only setup up to handle 
        IPC34XX type controllers.
    * Does not currently throw any errors
    -------------------------------------------------------------- '''
    TIMEOUT = 3.0

    # =========================================================================
    def __init__(self, conf=""):
        ''' -------------------------------------------------------------------
        ------------------------------------------------------------------- '''

        # pretend everything is off to start
        self.alive = {port:False for port in range(1, 9)}

    # =========================================================================
    def readConf(self):
        pass

    # =========================================================================
    def __getPath(self) -> str:
        pass

    # =========================================================================
    def getStatusAll(self) -> dict:

        return self.alive

    # =========================================================================
    def turnOn(self, outlets):
        '''Sets the provided outlets to ON
       
        Arguments:        
            outlets (list of ints) 
                      List indicating which outlets to activate.
                      Values should be between 1 and 8
                *** NOTE: 'outlets' can also be a single integer

        Returns:
            dict of booleans reporting if outlet was succesfully changed
                 True if change was successful, False if timeout occurred
        
        Example:
            turnOn(5) 
                This will turn on only outelt 5
            turnOn([2,5,8])
                This will turn on outlets 2, 5, and 8
        '''
     
        # Cast outlets to a list since it is likely a single integer
        if not type(outlets) is list: outlets = [outlets]
         
        for port in outlets: self.alive[port] = True

        return {port:True for port in outlets}

    # =========================================================================
    def turnOff(self, outlets):
        # Cast outlets to a list since it is likely a single integer
        if not type(outlets) is list: outlets = [outlets]
         
        for port in outlets: self.alive[port] = False

        return {port:True for port in outlets}