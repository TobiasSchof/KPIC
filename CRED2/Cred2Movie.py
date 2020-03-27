'''==========================================================
Script for capturing and displaying images from the CRED2 
  *Functionality:
    Linear/Log mode
    -Automatic log scale 
    Dark Subtracts
  
  *NOTE: Does not use shared mem. 

  *Assumes darks have already been saved and the path has 
      been defined correctly below.
 
  *Uses lock files to prevent system crashes

Changelog:__________________________________________________

  __04/23/2018__
  * Added section to catch qt error for ssh
    *!!TODO!!: @DAN: need to finalize so that loop still prints 
    ***This section is currently commented out since it is not done
  
  __04/27/2018__
  * Added lock file handling:
    * The script checks if the vlviewer or our lock file exists, 
      exits if so, and warns the user accordingly
    * A descriptive error, which includes the script PID as well
      as our lock file's name, is displayed to aid with user debugging. 
    * This is is crucial to preventing system reboots due to 
      threads stepping on each other.
  
  * Call edt.close() at end of script
    * This is important for closing the reader thread as expected

  __05/01/2018__
  * Replaced miscellaneous code with new libraries/library functions
    * all lock file stuff now covered by edtlib_standalone

  __05/01/2018__
  * Added sys.path.append([..]) to point to new path within SVN

  * In main while loop:
    * numpy array comparison changed from != to np.array_equal

Dependencies:_______________________________________________
  Custom:
  - edtlib            python wrapper for CRED2 control  

  Native:
  - numpy             --
  - matplotlib        --
  - astropy           --
  - time              --
  - sys               --

Control Parameters:_________________________________________
  - darkPath          path to the fits cube for darks
  - darkName          name of the fits cube for darks
  - isLog             Flag for log mode
  - isLgSclAuto       Flag for automatic log scale bounds
  - isDarkSubt        Flag for dark subtraction
  - imMin, imMax      min, max for manual log scale bounds


To Call:  kpython -i demoReadShm_Inf.py 
=============================================================
Author:        Dan Echeverri (dechever@caltech.edu)
Origin Date:   04/20/2018
Last Mod:      05/01/2018
'''
 
#------------Imports and Initialization------------------#
import sys
sys.path.append('/home/kpic_fiu/kroot/src/kss/nirspec/nsfiu/dev/lib')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
from edtlib_standalone import EdtIF
import time
from astropy.io import fits

#------------Parameters to Change------------------#
# Location of fits file of the dark cube
darkPath  = "/home/kpic_fiu/Documents/Darks/"
darkName  = "cred2_dark_0019996_-15.fits"

#Flag to Activate Log mode
isLog = True

#Flag to set your own log scale bounds
  #NOTE: make sure to tune imMin/imMax if this is set to False!!!
isLgSclAuto = True

#When isLogSclAuto == False, you can define your log bounds here:
imMin = 1
imMax = 2**14 - 1

#Flag to Activate Dark Subtract Mode
isDarkSubt = False

#------------Imports and Initialization------------------#
#--Instantiate camera
edt = EdtIF()
time.sleep(0.5)
imv = edt.getNumpyImage(wait=True)[0];  #read image (tuple of (img vect, time))
im = imv    #Variable used later in for loop top prevent plotting timeouts

print('---Drawing Visualizer---')
#--Instantiate other variables
#Read Dark
if isDarkSubt:
    hdul   = fits.open(darkPath+darkName)    #Header data unit list (fits handle)
    imDark = hdul[0].data
    #Average cube
    imDark = np.mean(imDark, axis=0)
    im -= imDark
if isLog:
    im = im.clip(min=1)
    if isLgSclAuto:
        imMax = np.max(im)
        imMin = np.median(im)
    imgPlt = plt.imshow(im, norm=LogNorm(), vmin=imMin, vmax=imMax); 
else:
    imgPlt = plt.imshow(im)
plt.ion()
plt.colorbar()
plt.show()

##--Catch qt error so that pyplot can still draw the image in ssh
#input('Catching qt error for ssh users:\r\n')
##send enter to allow text display in terminal
#sys.stdin.write('\r\n')   
#sys.stdin.flush()

print('\n---Starting Loop---')
#------------Main Loop-------------------#
k = 0
try:
    while 1:
        imv = edt.getNumpyImage(wait=True)[0];  #read image
        if not np.array_equal(imv, []):
            im  = imv
            sys.stdout.write('\rNew Image %d \t' %k)
            sys.stdout.flush()
            k   += 1
        else:
            print('WARNING::: Timeout likely occurred')
        if isDarkSubt and k%5 ==0:
            im -= imDark
        if isLog is True:
            im = im.clip(min=1)
            if isLgSclAuto:
                imMax = np.max(im)
                imMin = np.median(im)
        imgPlt.set_data(im)
        plt.draw()
except KeyboardInterrupt:
    edt.close()
    print('Exited due to KeyboardInterrupt')
