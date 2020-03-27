############################## Import Libraries ###############################

## Math Library
import numpy as np
## import time library 
import time
## Config files library
import configparser
## Datatime Library
import datetime as dt
## Import OS information
import os
## import system library
import sys
## import library used to manipulate fits files
from astropy.io import fits
## Import subprocess library used for making making sys call
import subprocess as sp

# Location of the tracking camera control library
sys.path.append('/kroot/src/kss/nirspec/nsfiu/dev/lib/cred2New/')
## Import the camera control class
from cred2Control_lib import cred2

################################# Parameters ##################################

# Location of all .ini files
configpath = '/kroot/src/kss/nirspec/nsfiu/dev/config/'
# Format for time-based filename
FNMTFORMAT = '%H_%M_%S.%f'
# Format for UTC-named directories
DIRTFORMAT = '%Y%m%d'
# Default path for saving images
dfltPath   = '/nfiudata/'

### CRED2 ###
# Location of the shared memory used by the Cred2
SHMNAME = '/tmp/ircam0.im.shm'
# Instantiate Cred2 class and open access to the shared memory
cam = cred2(SHMNAME)

######################### Commands to control Scan.py #########################

class TC_cmds():
	'''
	Class for controlling the FIU script Scan.py via the sheared memory.
	'''
	def __init__(self):
		''' -------------------------------------------------------------------
		------------------------------------------------------------------- '''
		# Create self.verbose variable
		self.verbose = False

	
	def save_images(self,nb_images = 100.,nb_cubes = 1.):
		''' -------------------------------------------------------------------
		Function used to save tracking camera images.
		-----------------------------------------------------------------------
		Keywords:
		- nb_images	= number of images to save per cube.
		- nb_cubes  = number of cube to save.
		-----------------------------------------------------------------------
		Return:
		- [True]  = if images save properly.
		or:	
		- [False] = otherwise
		------------------------------------------------------------------- '''	
		try:
			# Verify if nb_images and nb_cubes are numbers and if the script
			# TC_Calibration.py is in standby mode.
			cdt_1 = isinstance(nb_images,(int,float))
			cdt_2 = isinstance(nb_cubes,(int,float))
			# Case #1: these two conditions are True.
			if cdt_1 and cdt_2:
				# Verify if the number of images and cubes are valid.
				cdt_4 = (1 <= nb_images <= 1000.)
				cdt_5 = (1 <= nb_cubes <= 100.)
				cdt_6 = (nb_images * nb_cubes <= 10000.)
				# Case #A: these three conditions are True.
				if cdt_4 and cdt_5 and cdt_6:
					# Make sure nb_images and nb_cubes are int numbers
					nb_images = np.int(nb_images)
					nb_cubes  = np.int(nb_cubes)					
					# --- Check/create UTC date directory for data
					tmpdate   = dt.datetime.utcnow()
					# UTC date for dir
					timestamp = tmpdate.strftime(DIRTFORMAT)
					# Main path for save
					mainPath  = dfltPath + timestamp + '/Cred2/'
					# Get path in system 
					ospath    = os.path.dirname(mainPath)
					# Path did not exist before; create it now
					if not os.path.exists(ospath):
						os.makedirs(ospath)

					# --- Get TC image dimensions
					tmp_im, TCParam = cam.getNumpyImage(Param = True)
					dim_x = np.int(TCParam['y1'] - TCParam['y0'] + 1.)
					dim_y = np.int(TCParam['x1'] - TCParam['x0'] + 1.)

					# Initialize the Cube and Time variable
					Cube = np.zeros([nb_images,dim_x,dim_y])
					Time = np.zeros([nb_images])

					# --- Start aquisition
					for i in np.arange(nb_cubes):
						# Start Cube #i aquisition
						for j in np.arange(nb_images):
							# Aquire an image
							Cube[j,:,:] = cam.getNumpyImage()
							Time[j]     = time.time()
						# --- Save Cube #i
						# get current date 
						tmpdate   = dt.datetime.utcnow().strftime(FNMTFORMAT)
						# define the names of the files
						filename_1 = mainPath + tmpdate + '_data.fits'
						filename_2 = mainPath + tmpdate + '_time.fits'

						# Create a Header Data Unit (HDU) based on the Cube.
						hdu_1 = fits.PrimaryHDU(Cube)
						# Save the data
						hdu_1.writeto(filename_1)

						# Create a Header Data Unit (HDU) based on the Time.
						hdu_2 = fits.PrimaryHDU(Time)
						# Save the data
						hdu_2.writeto(filename_2)

					return filename_1
				
				# Case #B: One of the conditions is False.
				else:
					if not cdt_4:
						print('The number of images must be in [1,1000].')
					if not cdt_5:
						print('The number of cubes must be in [1,100].')
					if not cdt_6:
						print('Total number of images must be <= 10000.')
					return False

			# Case #2: One of the condition is False.
			else:
				if not cdt_1:
					print('The number of images must be a number.')
				if not cdt_2:
					print('The number of cubes must be a number.')
				return False
		except:
			return False
