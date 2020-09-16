# inherent python libraries
from time import localtime

# installed libraries
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import QTimer

# keywords class
from ktl import Service
# module python libraries
from FIU_TTM_cmds import FIU_TTM_cmds
# library to get sep/pa
from get_distort import get_dis_sep, get_raw_sep, get_dis_pa, get_raw_pa
# has various exceptions thrown by python libraries
from dev_Exceptions import *

# for the following sections, we don't want to redefine variables, so we check that a variable either
#   doesn't exist, or is None before assigning a value to it

########## hex values for colors ##########
try:
    assert orange is not None
except:
    orange = "background-color: #ffd494"
try:
    assert red is not None
except:
    red = "background-color: #ffbaba"
try:
    assert green is not None
except:
    green = "background-color: #c1ffba"
try:
    assert grey is not None
except:
    grey = "background-color: #c7c7c7"

########## Subscribe to necessary ktl keywords ##########
try:
    assert type(dcs2) is Service
# in this case, dcs2 isn't defined so we can define it
except NameError:
    dcs2 = Service("dcs2")
# in this case, dcs2 is defined but isn't a ktl service so throw an error
except AssertionError:
    Exception("dcs2 is already defined, but is not a ktl Service. Please free this variable.")

if not dcs2['targname']._getMonitored(): dcs2['targname'].subscribe()
if not dcs2['el']._getMonitored(): dcs2['el'].subscribe()
if not dcs2['airmass']._getMonitored(): dcs2['airmass'].subscribe()

# define default refresh rate (in milliseconds)
refresh = 30000

########## Initiate module libraries ##########
try:
    assert fiu_ttm is FIU_TTM
except NameError:
    fiu_ttm = FIU_TTM_cmds()
except AssertionError:
    Exception("fiu_ttm is already defined but is not an instance of FIU_TTM. Please free this variable.")

########## Target Info ##########

class Target_name(QLabel):
    """A widget to get the name of the current target"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for target name widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super(Target_name, self).__init__(*args, **kwargs)

        # store refresh rate
        self.refresh_rate = refresh_rate

        # create a timer to call update
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """updates the size and text in the widget"""

        # update target name
        self.setText(str(dcs2["targname"]))
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

class Elevation(QLabel):
    """A widget to get the elevation of the current target"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for elevation widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # store refresh rate
        self.refresh_rate = refresh_rate

        # create a timer to call update
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """updates the size and text in the widget"""

        # update elevation
        self.setText(str(dcs2["el"]))
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

class Airmass(QLabel):
    """A widget to get the airmass of the current target"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for airmass widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # store refresh rate
        self.refresh_rate = refresh_rate

        # create a timer to call update
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """updates the size and text in the widget"""

        # update airmass
        self.setText(str(dcs2["airmass"]))
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

class RT(QLabel):
    """A widget to get the RT of the current target"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for RT widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # store refresh rate
        self.refresh_rate = refresh_rate

        # create a timer to call update
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """updates the size and text in the widget"""

        # update RT
        lt = localtime()
        self.setText("{:02}:{:02}:{:02}".format(lt.tm_hour, lt.tm_min, lt.tm_sec))
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

"""
class Hmag(QLabel):

########## Tracking Script ##########

class Track_stat:

class Track_gain:

class Track_valid:

class Track_goal:

class Goal_pos_x:

class Goal_pos_y:

class Track_avg:

class Usr_offset_x:

class Usr_offset_y:
"""
class Astro_raw_pa(QLabel):
    """A widget to get the undistorted PA value"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for raw pa value widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # store refresh rate
        self.refresh_rate = refresh_rate

        # create a timer to call update
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            self.setText("{:06.2f}".format(get_raw_pa()))
            self.setStyleSheet(grey)
        except:
            self.setText("Unknown")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

class Astro_raw_sep(QLabel):
    """A widget to get the undistorted Sep value"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for raw sep value widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # store refresh rate
        self.refresh_rate = refresh_rate

        # create a timer to call update
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            self.setText("{:07.2f}".format(get_raw_sep()))
            self.setStyleSheet(grey)
        except:
            self.setText("Unknown")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

class Astro_dist_pa(QLabel):
    """A widget to get the distorted PA value"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for distorted pa value widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # store refresh rate
        self.refresh_rate = refresh_rate

        # create a timer to call update
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            self.setText("{:06.2f}".format(get_dis_pa()))
            self.setStyleSheet(grey)
        except:
            self.setText("Unknown")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

class Astro_dist_sep(QLabel):
    """A widget to get the distorted Sep value"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for distorted sep value widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # store refresh rate
        self.refresh_rate = refresh_rate

        # create a timer to call update
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            self.setText("{:07.2f}".format(get_dis_sep()))
            self.setStyleSheet(grey)
        except:
            self.setText("Unknown")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

""""
class DAR:

class WL_tc:

class WL_ScF:

########## Tracking Camera ##########

class Track_cam_stat:

class Track_cam_f_l:

class Track_cam_temp:

class Track_cam_tint:

class Track_cam_fps:

class Track_cam_ndr:

class Track_cam_crop:

class Track_cam_crop_x:

class Track_cam_crop_y:

class Track_cam_inst_ang:

class Track_cam_ps:

class Track_cam_dist_map:

########## Error Bar ##########

class Errors:

########## Adaptive Optics ##########

class WFS:

class TTM_loop:

class DM_loop:

class Extinction:

class Rot_mode:

class Rot_pos_val:

########## FIU setup ##########

class NIRSPEC_po:

class KPIC_po:

class PYWFS_po:

class TC_po:

class Calib_src:

class Keck_src:

class SFP:

class Kilo_DM:

class Humid:

class Pup_mask:

class ADC:

class Prism_1:

class Prism_2:
"""
class FIU_TTM_stat(QLabel):
    """A widget to get the status of the FIU TTM"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for FIU TTM status widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # store refresh rate
        self.refresh_rate = refresh_rate

        # create a timer to call update
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """updates the size and text in the widget"""

        # set text and color based on current FIU_TTM stat value
        try:
            if fiu_ttm.is_loop_closed():
                self.setText("Closed")
                self.setStyleSheet(green)
            else:
                self.setText("Open")
                self.setStyleSheet(red)
        except StageOff:
            self.setText("D/C")
            self.setStyleSheet(red)
        except ScriptOff:
            self.setText("Unknown")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

class FIU_TTM_x(QLabel):
    """A widget to get the x value of the FIU TTM"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for FIU TTM x widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # store refresh rate
        self.refresh_rate = refresh_rate

        # create a timer to call update
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """updates the size and text in the widget"""

        # set text and color based on current FIU_TTM x value
        try:
            cur_x = fiu_ttm.get_pos()[0]
            self.setText("{:05d}".format(cur_x))
            if cur_x < 100 or cur_x > 9900:
                self.setStyleSheet(orange)
            else:
                self.setStyleSheet(green)
        except StageOff:
            self.setText("D/C")
            self.setStyleSheet(red)
        except ScriptOff:
            self.setText("Unknown")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

class FIU_TTM_y(QLabel):
    """A widget to get the y value of the FIU TTM"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for FIU TTM y widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # store refresh rate
        self.refresh_rate = refresh_rate

        # create a timer to call update
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """updates the size and text in the widget"""

        # set text and color based on current FIU_TTM x value
        try:
            cur_y = fiu_ttm.get_pos()[1]
            self.setText("{:05d}".format(cur_y))
            if cur_y < 100 or cur_y > 9900:
                self.setStyleSheet(orange)
            else:
                self.setStyleSheet(green)
        except StageOff:
            self.setText("D/C")
            self.setStyleSheet(red)
        except ScriptOff:
            self.setText("Unknown")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)
"""
class TC_filter:

class TC_mode:

class PIAA:

class Bundle:

class Calib_in:

class Calib_out:

########## FEU setup ##########

class Zaber_x:

class Zaber_y:

class Zaber_f:

class FEU_TTM:

class FEU_TTM_x:

class FEU_TTM_y:

class FEU_po:

class FEU_pd_stat:

class FEU_pd_flux:
"""