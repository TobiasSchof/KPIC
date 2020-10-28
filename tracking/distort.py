#!/usr/bin/env kpython3

# inherent python libraries
from time import sleep
import os, sys

# installs
import numpy as np
import astropy.io.fits as fits
import scipy.interpolate as sinterp

# nfiuserver libraries
import ktl
from KPIC_shmlib import Shm
sys.path.insert(1, "/kroot/src/kss/nirspec/nsfiu/dev/lib")
from Star_Tracker_cmds import Tracking_cmds

"""
This script distorts astrophysical sep/pa for the CRED2 tracking camera
"""

if not os.path.isdir("/tmp/Tracking"):
    os.mkdir("/tmp/Tracking")
# open the sep and pa shms
sep = Shm("/tmp/Tracking/SEP.shm", np.array([0,0], np.float))
pa  = Shm("/tmp/Tracking/PA.shm", np.array([0,0], np.float))

# TODO:
# subscribe to ktl service in charge of rotator
# monitor the rotator keyword so we always have the most recent value

# open shm for science fiber location
sf = Tracking_cmds()
serv = ktl.Service("dcs2", populate=True)
serv["rotposn"].monitor()
serv["instangl"].monitor()

# Read the distortion solution
#   NOTE: This script does not allow for changing distortion solution. If a 
#         new solution is found, script must be restarted
distor_file = "/nfiudata/sol/distortion_solution.fits"
with fits.open(distor_file) as hdulist:
    orig_coords = hdulist[0].data[0]
    undistor_coords = hdulist[0].data[1]
    platescale = hdulist[0].header['PS']
    northangle = hdulist[0].header['TN']

# create an interpolant to be used for solution
distort_x = sinterp.LinearNDInterpolator(undistor_coords.T, orig_coords[0])
distort_y = sinterp.LinearNDInterpolator(undistor_coords.T, orig_coords[1])

# create a fake "old" variable so that the first time through the loop, values
#    get updated.
old = [-5000, -5000, -5000, -5000, -5000]

#### Begin conversions #####
while True:
    try:
        # The location of the science fiber, which we are assuming is where we want
        #    the companion to be
        # NOTE: for now, x and y goal are inverted.
        comp_y, comp_x = sf.get_goal()[2:4]

        #### Astrometry of the companion
        # location of the rotator
        try:
            rot_posang = float(serv["rotposn"]) - float(serv["instangl"])
        # If there's not keyword available, wait and restart loop
        except ValueError:
            sleep(20)
            continue
        # undistorted sep
        comp_sep = sep.get_data()[0]
        # undistorted pa
        comp_pa = pa.get_data()[0]
        comp_pa += rot_posang

        # check to see if any values have changed
        new = [comp_x, comp_y, comp_sep, comp_pa, rot_posang]
        if new == old:
            # if there are no new values, we don't have to recalculate anything.
            # store old values so that update time gets changed
            sep.set_data(sep.get_data())
            pa.set_data(pa.get_data())
            # rest
            sleep(30)
            # restart loop
            continue
    
        # convert to pixels and add PA offset to CRED2
        comp_r_undist = comp_sep / platescale # pix
        comp_pa_off = comp_pa - northangle
    
        # convert to offset of star from companion (which is at the location of the
        #    fiber) in undistorted detector frame
        # NOTE: that the CRED2 has x = -RA, so we need to multiply by negative 1
        star_x_undist = comp_x + -(comp_r_undist * np.sin(np.radians(comp_pa_off)))
        star_y_undist = comp_y -(comp_r_undist * np.cos(np.radians(comp_pa_off)))
    
        # distort the star x/y to get the x/y on the detector it should be at
        star_x = distort_x((star_x_undist, star_y_undist))
        star_y = distort_y((star_x_undist, star_y_undist))
    
        # convert to comp separation and PA, but after distortion
        comp_sep_distor = np.sqrt((star_x - comp_x)**2 + (star_y - comp_y)**2)
        comp_pa_distor = np.degrees(np.arctan2((comp_x - star_x),\
            (comp_y - star_y))) + northangle
        comp_sep_distor *= platescale
        comp_pa_distor %= 360
    
        comp_pa_distor -= rot_posang
    
        # store values in shared memory
        _ = sep.get_data()
        _[1] = comp_sep_distor
        sep.set_data(_)
    
        _ = pa.get_data()
        _[1] = comp_pa_distor
        pa.set_data(_)

        # store the values to calculate these values
        old = new

        # constant updates aren't necessary, so sleep to avoid hogging cpu
        sleep(20)
    # if there were any errors
    except:
        # wait 1 second
        sleep(1)
        # then try again
        continue
