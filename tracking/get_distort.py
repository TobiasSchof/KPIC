import sys
from time import sleep

sys.path.insert(1, "/kroot/src/kss/nirspec/nsfiu/dev/lib")
from KPIC_shmlib import Shm

sep = Shm("/tmp/Tracking/SEP.shm", sem = True)
pa  = Shm("/tmp/Tracking/PA.shm", sem = True)

def get_dis_sep():
    """Function to get the distorted sep"""
    return sep.get_data()[1]

def get_dis_pa():
    """Function to get the distorted pa"""
    return pa.get_data()[1]

def get_raw_sep():
    """Function to get the undistorted sep"""
    return sep.get_data()[0]

def get_raw_pa():
    """Function to get the undistorted pa"""
    return pa.get_data()[0]

def set_pa(new_val:float, ret:bool=False):
    """Function to set the undistorted pa
    
    NOTE: this function is not smart about the return. If another program edits the
        undistorted sep, a stale value may be returned
    Args:
        new_val = the undistorted pa
        ret = if true, waits for distorted pa to be updated and then returns it
    """
    data = pa.get_data()
    data[0] = new_val
    pa.set_data(data)
    if ret:
        cnt = pa.mtdata["cnt0"]
        while(pa.get_counter() == cnt): sleep(2)
        return pa.get_data()[1]

def set_sep(new_val:float, ret:bool=False):
    """Function to set the undistorted sep
    
    NOTE: this function is not smart about the return. If another program edits the
        undistorted sep, a stale value may be returned
    Args:
        new_val = the undistorted pa
        ret = if true, waits for distorted sep to be updated and then returns it
    """
    data = sep.get_data()
    data[0] = new_val
    sep.set_data(data)
    if ret:
        cnt = sep.mtdata["cnt0"]
        while(sep.get_counter() == cnt): sleep(2)
        return sep.get_data()[1]
