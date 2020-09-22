# inherent python libraries
import sys

# installed libraries
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import QTimer

# keywords class
from ktl import Service
# epics class
from epics import PV
# module python libraries
from FIU_TTM_cmds import FIU_TTM_cmds
# library to get sep/pa
from get_distort import get_dis_sep, get_raw_sep, get_dis_pa, get_raw_pa
# has various exceptions thrown by python libraries
from dev_Exceptions import *

# libraries from dev directory
sys.path.insert(1, "/kroot/src/kss/nirspec/nsfiu/dev/lib")
from Tracking_cmds import Tracking_cmds

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
if not dcs2['rotmode']._getMonitored(): dcs2['rotmode'].subscribe()
if not dcs2['rotposn']._getMonitored(): dcs2['rotposn'].subscribe()
if not dcs2['instangl']._getMonitored(): dcs2['instangl'].subscribe()

try:
    assert type(ao2) is Service
except NameError:
    ao2 = Service("ao2")
except AssertionError:
    Exception("ao2 is already defined, but is not a ktl Service. Please free this variable.")

if not ao2["obimname"]._getMonitored(): ao2["obimname"].subscribe()
if not ao2["obsfname"]._getMonitored(): ao2["obsfname"].subscribe()

########## Connect to necessary epics channels ##########
try:
    assert type(tl) is PV
# in this case, tl isn't defined, so define it
except NameError:
    tl = PV("k2:dcs:sup:timeToLim")
# in this case, tl is defined, but isn't an epics channel, so throw an error
except AssertionError:
    Exception("tl is already defined, but isn't an epics channel. Please free this variable.")

# define default refresh rate (in milliseconds)
refresh = 30000

########## Initiate module libraries ##########
try:
    assert fiu_ttm is FIU_TTM
except NameError:
    fiu_ttm = FIU_TTM_cmds()
except AssertionError:
    Exception("fiu_ttm is already defined but is not an instance of FIU_TTM. Please free this variable.")

try:
    assert tracking is Tracking_cmds
except NameError:
    tracking = Tracking_cmds()
except AssertionError:
    Exception("tracking is already defined but is not an instance of Tracking_cmds. Please free this variable.")

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
        try:
            self.setText("{:05.2f}".format(float(dcs2["el"])))
            self.setStyleSheet(grey)
        except ValueError:
            self.setText("?")
            self.setStyleSheet(red)
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
        try:
            self.setText("{:05.2f}".format(float(dcs2["airmass"])))
            self.setStyleSheet(grey)
        except ValueError:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

class RT(QLabel):
    """A widget to get the time to telescope limit"""

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
        self.setText(tl.get())
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

"""
class Hmag(QLabel):
"""
########## Tracking Script ##########

class Track_stat(QLabel):
    """A widget to get the status of the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for track stat widget

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
            val = tracking.get_status()
            if val == "off":
                self.setStyleSheet(red)
            else:
                self.setStyleSheet(green)
            self.setText(val)
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

class Track_gain(QLabel):
    """A widget to get the gain of the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for track gain widget

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
            _, val = tracking.get_gain()
            if val == 0:
                self.setStyleSheet(red)
            elif val < 1:
                self.setStyleSheet(orange)
            else:
                self.setStyleSheet(green)
            self.setText(val)
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

"""
class Track_valid:
"""

class Track_goal(QLabel):
    """A widget to get the current goal of the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for track goal widget

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
            val = tracking.get_()[1]
            self.setStyleSheet(grey)
            self.setText(val)
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

class Goal_pos_x(QLabel):
    """A widget to get the current x position of the goal of the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for goal pos x widget

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
            x_pos = tracking.get_goal()[2]
            x_dist = tracking.get_dist()[0]
            if abs(x_dist) < .5:
                self.setStyleSheet(green)
            elif abs(x_dist) < 1:
                self.setStyleSheet(orange)
            else:
                self.setStyleSheet(red)
            self.setText("{:06.2f} (\u0394: {:.2f}".format(x_pos, x_dist))
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

class Goal_pos_y(QLabel):
    """A widget to get the current y position of the goal of the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for goal pos y widget

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
            y_pos = tracking.get_goal()[3]
            y_dist = tracking.get_dist()[1]
            if abs(y_dist) < .5:
                self.setStyleSheet(green)
            elif abs(y_dist) < 1:
                self.setStyleSheet(orange)
            else:
                self.setStyleSheet(red)
            self.setText("{:06.2f} (\u0394: {:.2f}".format(y_pos, y_dist))
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

"""
class Track_avg:
"""

class Usr_offset_x(QLabel):
    """A widget to get the x scan offset of the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for usr offset x widget

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
            val = tracking.get_scan_offset()[0]
            if val == 0:
                self.setStyleSheet(green)
            else:
                self.setStyleSheet(orange)
            self.setText("{:04.1f}".format(val))
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

class Usr_offset_y(QLabel):
    """A widget to get the y scan offset of the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for usr offset y widget

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
            val = tracking.get_scan_offset()[1]
            if val == 0:
                self.setStyleSheet(green)
            else:
                self.setStyleSheet(orange)
            self.setText("{:04.1f}".format(val))
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

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
            self.setText("?")
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
            self.setText("?")
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
            self.setText("?")
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
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

"""
class DAR:

class WL_tc:

class WL_ScF:
"""
########## Tracking Camera ##########
"""
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
"""

class Rot_mode(Qlabel):
    """A widget to get the rotator mode value"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for rotator mode value widget

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
        self.setText(str(dcs2["rotmode"]))
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

class Rot_pos_val(Qlabel):
    """A widget to get the rotator offset value"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for rotator offset value widget

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
            self.setText("{:04.2f}".format(float(dcs2["rotposn"]) - float(dcs2["instangl"])))
            self.setStyleSheet(grey)
        except ValueError:
            self.setText("?")
            self.setStyleSheet(red)
        self.setText(dcs2["rotmode"])
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)

"""
########## FIU setup ##########
"""
class NIRSPEC_po(QLabel):
    """A widget to get the nirspec pickoff position"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for nirspec po widget

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
        val = str(ao2["obimname"])
        if val == "out":
            self.setText(green)
        else:
            self.setText(red)
        self.setText(val)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)
"""
class KPIC_po:

class PYWFS_po:

class TC_po:

class Calib_src:

class Keck_src:
"""
class SFP(QLabel):
    """A widget to get the SFP"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for SFP widget

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
        val = str(ao2["obsfname"])
        if val == "telescope":
            self.setText(green)
        else:
            self.setText(red)
        self.setText(val)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)
"""
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
            self.setText("?")
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
            self.setText("?")
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
            self.setText("?")
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