#!/usr/bin/env kpython3

# standard library
from configparser import ConfigParser
from atexit import register, unregister
from time import sleep
from signal import signal, SIGHUP, SIGTERM
from subprocess import Popen
from argparse import ArgumentParser
import sys, os, logging

# installs
import numpy as np
from scipy.signal import medfilt
import nair

# nfiuserver libraries
from KPIC_shmlib import Shm
from FIU_TTM_cmds import FIU_TTM_cmds as TTM
from Track_Cam_cmds import Track_Cam_cmds as TC
from ktl import Service

def get_atmospheric_dispersion(wl1 = 1.60, wl2 = 2.19):
    ''' -------------------------------------------------------------------
    Description:
        - This function return the atmospheric dispersion between two
        wavelength.
    Arguments:
        - wl1       = First wavelength
        - wl2       = Second wavelength
    Returns:
        - Atmospheric  dispersion between the two provided wavelengths.
    ------------------------------------------------------------------- '''
    # Get the pressure at the summit
    pressure  = np.float(met2['pressure']) * 100.
    # Get the tempertature in the Keck II Dome
    temp_K    = np.float(met2['dometemp']) + 273.15
    # Get the humidity in the Keck II Dome
    humidity  = np.float(met2['domehumd'])
    # Get the elevation of the telescope in degree
    tel_elev  = np.float(dcs2['el'])

    # Compute the zenith angle
    zen_angle = 90.-tel_elev
    # Compute the index of refraction for both wavelength
    n = nair.nMathar(np.array([wl1, wl2]), pressure, temp_K, humidity)
    # Compute the dispersion for both wavelength
    dispersions = (n**2 - 1)/(2 * n**2) * np.tan(np.radians(zen_angle))
    # Compute offset between wavelenght #1 and wavelength #2
    diff_disp = dispersions[1] - dispersions[0] 
    # Converte in mas
    diff_disp *= 206265 * 1000
    # The dispersion is position when comparing longer wavelengths to
    # shorter wavelenghts. Thus we need to negate this numbers.
    diff_disp *= - 1
    # Returns difference of dispersion in mas between the two wavelengths
    # provided
    return diff_disp

def main():
    """Holds the body of the script"""

    # get info on script status, tracking loop, and whether to reduce
    stat = Stat_P.get_data()
    # if script should be off, return
    if not stat & 1: return

    # if TC calibration data isn't valid, load new images
    if not cam.calibration_valid():
        cam.load_calibration_images()
        sleep(1)

        # if TC calibration data still isn't valid, set error and try again
        if not cam.calibration_valid():
            Error.set_data()
            continue
    
    # acquire images
    

    # medfilt image if requested

    # compute median and std of image

    # if subimage option selected, crop image

    # try to find PSF (error, continue if invalid) and update shm

    # if subimage option NOT selected, or if "PSF moved more than 1/4
    # of the width of the subwindow" (if PSF is not in center 1/4?), 
    # compute new subwindow and update shm

    # pull mastopix and instangle from cam

    # pull cropping info from cam

    # pull goal info
        # if goal is not custom, get x,y from reference shm

    # get user offsets

    # get thee bundle drift

    # get sep, pa

    # convert sep to pix

    # computer atmo. disp., convert to pix

    # update disp. offset

    # get observation mode, rotposn, and parantel from ktl

    # 3 cases to calculate disp offset, astrometric x/y:
    #    case 1: position angle
    #    case 2: vertical angle
    #    case 3: stationary
    
    # compute new PSF position

    # verify that it's not too close to edge of image

    # compute required TTM shifts

    # multiply shifts by gain

    # apply TTM shifts if all required conditions were met