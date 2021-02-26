# inherent python libraries
import sys

# installed libraries
from PyQt5.QtWidgets import QLabel, QComboBox, QLineEdit, QPushButton
from PyQt5.QtCore import QTimer

# keywords class
from ktl import Service
# epics class
from epics import PV
# module python libraries
from NPS_cmds import NPS_cmds
# library to get sep/pa
from get_distort import get_dis_sep, get_raw_sep, get_dis_pa, get_raw_pa, set_pa, set_sep
# has various exceptions thrown by python libraries
from dev_Exceptions import *

# libraries from dev directory
sys.path.insert(1, "/kroot/src/kss/nirspec/nsfiu/dev/lib")
from TTM_cmds import TTM_cmds
from Star_Tracker_cmds import Tracking_cmds
from TLS import TLS_Device
from cred2New.Cred2_Cmds import cred2

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

try:
    if not dcs2['targname']._getMonitored(): dcs2['targname'].subscribe()
except: pass
try:
    if not dcs2['el']._getMonitored(): dcs2['el'].subscribe()
except: pass
try:
    if not dcs2['airmass']._getMonitored(): dcs2['airmass'].subscribe()
except: pass
try:
    if not dcs2['rotmode']._getMonitored(): dcs2['rotmode'].subscribe()
except: pass
try:
    if not dcs2['rotposn']._getMonitored(): dcs2['rotposn'].subscribe()
except: pass
try:
    if not dcs2['instangl']._getMonitored(): dcs2['instangl'].subscribe()
except: pass

try:
    assert type(ao2) is Service
except NameError:
    ao2 = Service("ao2")
except AssertionError:
    Exception("ao2 is already defined, but is not a ktl Service. Please free this variable.")

try:
    if not ao2["obimname"]._getMonitored(): ao2["obimname"].subscribe()
except: pass
try:
    if not ao2["obsfname"]._getMonitored(): ao2["obsfname"].subscribe()
except: pass
try:
    if not ao2["obdb"]._getMonitored(): ao2["obdb"].subscribe()
except: pass
try:
    if not ao2["obswsta"]._getMonitored(): ao2["obswsta"].subscribe()
except: pass
try:
    if not ao2["dmlp"]._getMonitored(): ao2["dmlp"].subscribe()
except: pass
try:
    if not ao2["dtlp"]._getMonitored(): ao2["dtlp"].subscribe()
except: pass

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
    assert fiu_ttm is TTM_cmds
except NameError:
    fiu_ttm = TTM_cmds()
except AssertionError:
    Exception("fiu_ttm is already defined but is not an instance of FIU_TTM. Please free this variable.")

try:
    assert tracking is Tracking_cmds
except NameError:
    tracking = Tracking_cmds()
except AssertionError:
    Exception("tracking is already defined but is not an instance of Tracking_cmds. Please free this variable.")

try:
    assert tc is cred2
except NameError:
    tc = cred2("/tmp/ircam0.im.shm")
except AssertionError:
    Exception("tc is already defined but is not an instance of cred2. Please free this variable.")

try:
    assert nps is NPS_cmds
except NameError:
    nps = NPS_cmds()
except AssertionError:
    Exception("nps is already defined but is not an instance of NPS_cmds. Please free this variable.")

try:
    assert laser is TLS_Device
except NameError:
    laser = TLS_Device("/dev/ttyUSB0")
except AssertionError:
    Exception("laser is already defined but is not an instance of TLS_Device. Please free this variable.")
########## Target Info ##########

class Target_name(QLabel):
    """A widget to get the name of the current target"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for target name widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update target name
        self.setText(str(dcs2["targname"]))
        # run QLabel's update method
        super().update()

class Elevation(QLabel):
    """A widget to get the elevation of the current target"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for elevation widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update elevation
        try:
            val = float(dcs2["el"])
            self.setText("{:05.2f}".format(val))
            if val > 40:
                self.setStyleSheet(green)
            elif val >= 36.8:
                self.setStyleSheet(orange)
            else:
                self.setStyleSheet(red)
        except ValueError:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class Airmass(QLabel):
    """A widget to get the airmass of the current target"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for airmass widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

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

class RT(QLabel):
    """A widget to get the time to telescope limit"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for RT widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        try:
            # update RT
            val = tl.get()
            self.setText(val)
            time_ = val.split(":")
            self.setStyleSheet(green)
            if int(time_[0]) == 0:
                if int(time_[1]) < 10:
                    self.setStyleSheet(red)
                elif int(time_[1]) < 30:
                    self.setStyleSheet(orange)
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

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

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            val = tracking.get_status()[1]
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

class Track_gain(QPushButton):
    """A widget to get the gain of the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for track gain widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # set button so checked state is green, unchecked state is red
        self.setStyleSheet("QPushButton:checked { background-color: #c1ffba } QPushButton { background-color: #ffbaba }")

        # connect set gain method to when the button is pushed
        self.clicked.connect(self.set_gain)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def set_gain(self):
        """Sets the gain on the tracking loop"""

        gain = 1 if self.isChecked() else 0

        if gain != tracking.get_gain():
            tracking.set_gain(gain)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            val = tracking.get_gain()
            if val == 0 and self.isChecked():
                self.toggle()
            elif val == 1 and not self.isChecked():
                self.toggle()
            elif val > 0 and val < 1 and self.isChecked():
                self.toggle()
            self.setText("{:04.3f}".format(val))
        except:
            self.setText("?")
            if self.isChecked():
                self.toggle()
        # run super's update method
        super().update()

class Track_valid(QLabel):
    """A widget to get the validity of the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for track valid widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            val = tracking.is_psf1_parameters_valid()
            if val:
                self.setStyleSheet(green)
                self.setText("Valid")
            else:
                self.setStyleSheet(red)
                self.setText("Invalid")
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class Track_goal(QComboBox):
    """A widget to get the current goal of the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for track goal widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a dictionary to translate from index to what goal should be sent
        self.sel_goal = {0:"scf1", 1:"scf2", 2:"scf3", 3:"scf4", 4:"scf5", 5:"center",
            6:"ul", 7:"bl", 8:"ur", 9:"br", 10:"zern"}
        # create a dictionary to translate from the current goal to which index should be set
        self.sel_idx = {"scf_1":0, "scf_2":1, "scf_3":2, "scf_4":3, "scf_5":4,
            "center":5, "upper left":6, "bottom left":7, "upper right":8,
            "bottom right":9, "zernike mask":10, "custom":-1}

        # to add an unselectable "custom" option, we set widget to editable
        #    and underlying linEdit to readonly
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText("Custom")

        # connect option selection to goal selection
        self.activated.connect(self.change_goal)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # don't update if a goal is currently being selected
        if not self.view().isVisible():
            # update value
            try:
                val = tracking.get_goal()[1]
                idx = self.sel_idx[val]

                if idx != self.currentIndex():
                    self.setCurrentIndex(idx)
            except:
                pass
            # run QLabel's update method
            super().update()

    def change_goal(self):
        """Changes the current goal of the tracking script"""

        # get selection and pass through self.sel before handing value to
        #    tracking commands script
        try:
            val = tracking.get_goal()[1]
            if self.currentIndex() != self.sel_idx[val]:
                tracking.set_goal(self.sel_goal(self.currentIndex()))
        except:
            self.update()

class Goal_pos_x(QLabel):
    """A widget to get the current x position of the goal of the tracking script"""

    def __init__(self, *args, refresh_rate:int = 1000, **kwargs):
        """Constructor for goal pos x widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            x_pos = tracking.get_goal()[3]
            x_dist = tracking.get_dist()
            if not x_dist:
                self.setStyleSheet(red)
                self.setText("{:06.2f} (\u0394: N/A)".format(x_pos))
            else:
                if abs(x_dist[0]) < .5:
                    self.setStyleSheet(green)
                elif abs(x_dist[0]) < 1:
                    self.setStyleSheet(orange)
                else:
                    self.setStyleSheet(red)
                self.setText("{:06.2f} (\u0394: {:.2f})".format(x_pos, x_dist[0]))
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class Goal_pos_y(QLabel):
    """A widget to get the current y position of the goal of the tracking script"""

    def __init__(self, *args, refresh_rate:int = 1000, **kwargs):
        """Constructor for goal pos y widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            y_pos = tracking.get_goal()[2]
            y_dist = tracking.get_dist()
            if not y_dist:
                self.setStyleSheet(red)
                self.setText("{:06.2f} (\u0394: N/A)".format(y_pos))
            else:
                if abs(y_dist[1]) < .5:
                    self.setStyleSheet(green)
                elif abs(y_dist[1]) < 1:
                    self.setStyleSheet(orange)
                else:
                    self.setStyleSheet(red)
                self.setText("{:06.2f} (\u0394: {:.2f}".format(y_pos, y_dist[1]))
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class Track_avg(QLabel):
    """A widget to get the number of images in an average for the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for track avg widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            val = tracking.get_nb_images()
            self.setStyleSheet(grey)
            self.setText("{:02d}".format(val))
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class Usr_offset_x(QLabel):
    """A widget to get the x scan offset of the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for usr offset x widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            val = tracking.get_user_offsets()[0]
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

class Usr_offset_y(QLabel):
    """A widget to get the y scan offset of the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for usr offset y widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            val = tracking.get_user_offsets()[1]
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

class SEP_PA_validator():
    """A validator for a QLineEdit that will validate input on focus loss
        and return value to former value if new value is invalid"""

    def __init__(self, validation_field, edit_func=None):
        """Constructur for validator
        
        Args:
            validation_field: the QLineEdit this validator is to work on
            edit_func: the function that should be called after text is validated
        """

        # store QLineEdit we're editing
        self.val_f = validation_field
        validation_field.editingFinished.connect(self.validate)
        self.old_val = validation_field.text()

        self.set_field = edit_func

    def validate(self):
        """A method to validate the new input"""

        # try to cast value as a double
        try:
            val = float(self.val_f.text())
        # if it can't be cast, set text to old value
        except:
            self.val_f.setText(self.old_val)
        # update old value and set new sep/pa
        finally:
            self.old_val = self.val_f.text
            if not self.set_field is None:
                try: self.set_field(float(self.val_f.text()))
                except: pass

class Astro_raw_pa(QLineEdit):
    """A widget to get the undistorted PA value"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for raw pa value widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # make a validator for value
        self.validator = SEP_PA_validator(self, set_pa)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def set_pa(self):
        """Sets raw PA when a valid argument is provided"""

    def update(self):
        """updates the size and text in the widget"""

        if not self.hasFocus():
            # update value
            try:
                self.setText("{:06.2f}".format(get_raw_pa()))
                self.setStyleSheet(grey)
            except AttributeError:
                self.setText("Off")
                self.setStyleSheet(red)
            except:
                self.setText("?")
                self.setStyleSheet(red)
            # run QLabel's update method
            super().update()

    def setText(self, text):
        """An extension of setText that sets the validator's old text field"""

        super().setText(text)
        self.validator.old_val = self.text()

class Astro_raw_sep(QLineEdit):
    """A widget to get the undistorted Sep value"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for raw sep value widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # make a validator for value
        self.validator = SEP_PA_validator(self, set_sep)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        if not self.hasFocus():
            # update value
            try:
                self.setText("{:07.2f}".format(get_raw_sep()))
                self.setStyleSheet(grey)
            except AttributeError:
                self.setText("Off")
                self.setStyleSheet(red)
            except:
                self.setText("?")
                self.setStyleSheet(red)
            # run QLabel's update method
            super().update()

    def setText(self, text):
        """An extension of setText that sets the validator's old text field"""

        super().setText(text)
        self.validator.old_val = self.text()

class Astro_dist_pa(QLabel):
    """A widget to get the distorted PA value"""

    def __init__(self, *args, refresh_rate:int = 2000, **kwargs):
        """Constructor for distorted pa value widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            self.setText("{:06.2f}".format(get_dis_pa()))
            self.setStyleSheet(grey)
        except AttributeError:
            self.setText("Off")
            self.setStyleSheet(red)
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class Astro_dist_sep(QLabel):
    """A widget to get the distorted Sep value"""

    def __init__(self, *args, refresh_rate:int = 2000, **kwargs):
        """Constructor for distorted sep value widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            self.setText("{:07.2f}".format(get_dis_sep()))
            self.setStyleSheet(grey)
        except AttributeError:
            self.setText("Off")
            self.setStyleSheet(red)
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class DAR(QLabel):
    """A widget to get the DAR value"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for dr widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)


    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            self.setText("{:06.2f}".format(tracking.get_ADC_shift()))
            self.setStyleSheet(grey)
        except AttributeError:
            self.setText("Off")
            self.setStyleSheet(red)
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class WL_tc(QLabel):
    """A widget to get the tracking camera wavelength for the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for WL tc widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            val = tracking.get_ADC_wavelengths()[0]
            self.setStyleSheet(grey)
            self.setText("{:.3f}".format(val))
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class WL_ScF(QLabel):
    """A widget to get the science fiber wavelength for the tracking script"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for WL ScF widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            val = tracking.get_ADC_wavelengths()[1]
            self.setStyleSheet(grey)
            self.setText("{:.3f}".format(val))
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

########## Tracking Camera ##########
"""
class Track_cam_stat:

class Track_cam_f_l:
"""
class Track_cam_temp(QLabel):
    """A widget to get the temp for the tracking camera"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for track cam temp widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            # get crop returns false or the crop window
            val = tc.get_temp()
            if abs(val - -40) <= 5:
                self.setStyleSheet(green)
            elif abs(val - -40) <= 30:
                self.setStyleSheet(orange)
            else:
                self.setStyleSheet(red)
            self.setText("{:03.1f}".format(val))
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class Track_cam_tint(QLabel):
    """A widget to get the exposure time for the tracking camera"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for track cam tint widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            val = round(tc.get_tint()*1000, 2)
            self.setStyleSheet(grey)
            self.setText("{:08.3f}".format(val))
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class Track_cam_fps(QLabel):
    """A widget to get the fps for the tracking camera"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for track cam fps widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            val = tc.get_fps()
            self.setStyleSheet(grey)
            self.setText("{:04d}".format(int(val)))
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class Track_cam_ndr(QLabel):
    """A widget to get the ndr for the tracking camera"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for track cam ndr widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            val = tc.get_ndr()
            self.setStyleSheet(grey)
            self.setText("{:02d}".format(val))
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class Track_cam_crop(QLabel):
    """A widget to get the crop for the tracking camera"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for track cam crop widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        """
        # update value
        try:
            # get crop returns false or the crop window
            val = tc.get_crop()
            if val:
                # if cropping is a square, define the square
                if val[1] - val[0] == val[3] - val[2]:
                    val = "{0}x{0}".format(val[1] - val[0])
                # otherwise, call it custom
                else:
                    val = "Custom"
            else:
                val = "Full Frame"
            self.setStyleSheet(grey)
            self.setText(val)
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)
        """
        super().update()

class Track_cam_crop_x(QLabel):
    """A widget to get the x crop for the tracking camera"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for track cam crop x widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        """
        # update value
        try:
            # get crop returns false or the crop window
            val = tc.get_crop()
            if val:
                val = "[{}:{}]".format(val[0], val[1])
            else:
                val = "---"
            self.setStyleSheet(grey)
            self.setText(val)
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)
        """
        super().update()

class Track_cam_crop_y(QLabel):
    """A widget to get the y crop for the tracking camera"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for track cam crop y widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        """
        # update value
        try:
            # get crop returns false or the crop window
            val = tc.get_crop()
            if val:
                val = "[{}:{}]".format(val[2], val[3])
            else:
                val = "---"
            self.setStyleSheet(grey)
            self.setText(val)
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
        # start timer again
        self.timer.start(self.refresh_rate)
        """
        super().update()

class Track_cam_inst_ang(QLabel):
    """A widget to get the inst angle for the tracking camera"""

    def __init__(self, *args, refresh_rate:int = 86400000, **kwargs):
        """Constructor for track cam inst ang widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            val = tc.instangle
            self.setStyleSheet(grey)
            self.setText("{}".format(val)+u"\u00B0")
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class Track_cam_ps(QLabel):
    """A widget to get the platescale for the tracking camera"""

    def __init__(self, *args, refresh_rate:int = 86400000, **kwargs):
        """Constructor for track cam ps widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            val = 1/tc.mastopix
            self.setStyleSheet(grey)
            self.setText("{:04.2f}".format(val))
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

"""
class Track_cam_dist_map:
"""
"""
########## Error Bar ##########

class Errors:
########## Adaptive Optics ##########

class WFS:
    
"""

class TTM_loop(QLabel):
    """A widget to get which whether the (ao2) TTM loop is open"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for TTM_loop widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update airmass
        try:
            val = str(ao2["DMLP"])
            self.setText(val)
            if val.lower() == "open":
                self.setStyleSheet(red)
            elif val.lower() == "closed":
                self.setStyleSheet(green)
            else:
                self.setStyleSheet(grey)
        except ValueError:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class DM_loop(QLabel):
    """A widget to get which whether the (ao2) DM loop is open"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for TTM_loop widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update airmass
        try:
            val = str(ao2["DTLP"])
            self.setText(val)
            if val.lower() == "open":
                self.setStyleSheet(red)
            elif val.lower() == "closed":
                self.setStyleSheet(green)
            else:
                self.setStyleSheet(grey)
        except ValueError:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
"""
class Extinction:
"""

class Rot_mode(QLabel):
    """A widget to get the rotator mode value"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for rotator mode value widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        self.setText(str(dcs2["rotmode"]))
        # run QLabel's update method
        super().update()

class Rot_pos_val(QLabel):
    """A widget to get the rotator offset value"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for rotator offset value widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        try:
            self.setText("{:04.2f}".format(float(dcs2["rotposn"]) - float(dcs2["instangl"])))
            self.setStyleSheet(grey)
        except ValueError:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

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

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        val = str(ao2["obimname"])
        if val == "home":
            self.setStyleSheet(green)
        else:
            self.setStyleSheet(red)
        self.setText(val)
        # run QLabel's update method
        super().update()

class KPIC_po(QLabel):

    """A widget to get the kpic pickoff position"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for kpic po widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        val = float(ao2["obdb"])
        if val < 3:
            val = "Out"
            self.setStyleSheet(red)
        elif val >= 110 and val <= 115:
            val = "Mirror"
            self.setStyleSheet(green)
        elif val > 215:
            val = "Dichroic"
            self.setStyleSheet(red)
        else:
            val = "Unkown"
            self.setStyleSheet(red)
        self.setText(val)
        # run QLabel's update method
        super().update()

"""
class PYWFS_po:

class TC_po:

class Calib_src:
"""

class Keck_src(QLabel):
    """A widget to get the keck light source position"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for keck src widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        val = str(ao2["obswsta"])
        if val == "off":
            self.setStyleSheet(green)
        else:
            self.setStyleSheet(red)
        self.setText(val)
        # run QLabel's update method
        super().update()

class SFP(QLabel):
    """A widget to get the SFP"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for SFP widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # update value
        val = str(ao2["obsfname"])
        if val == "telescope":
            self.setStyleSheet(green)
        else:
            self.setStyleSheet(red)
        self.setText(val)
        # run QLabel's update method
        super().update()

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

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # set text and color based on current FIU_TTM stat value
        try:
            if fiu_ttm.isScriptActif():
                if fiu_ttm.SVO_status():
                    self.setText("Closed")
                    self.setStyleSheet(green)
                else:
                    self.setText("Open")
                    self.setStyleSheet(red)
            else:
                self.setText("D/C")
                self.setStyleSheet(red) 
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
    """
    def update(self):
        updates the size and text in the widget

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
    """

class FIU_TTM_x(QLabel):
    """A widget to get the x value of the FIU TTM"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for FIU TTM x widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # set text and color based on current FIU_TTM x value
        try:
            cur_x = fiu_ttm.Position()[0]
            self.setText("{:d}".format(int(cur_x)))
            if cur_x < 100 or cur_x > 9900:
                self.setStyleSheet(orange)
            else:
                self.setStyleSheet(green)
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class FIU_TTM_y(QLabel):
    """A widget to get the y value of the FIU TTM"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for FIU TTM y widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # set text and color based on current FIU_TTM x value
        try:
            cur_y = fiu_ttm.Position()[1]
            self.setText("{:d}".format(int(cur_y)))
            if cur_y < 100 or cur_y > 9900:
                self.setStyleSheet(orange)
            else:
                self.setStyleSheet(green)
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
    
"""
class TC_filter:

class TC_mode:

class PIAA:

class Bundle:
"""
class Calib_in(QLabel):
    """A widget to get the laser source"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for calib in widget

        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # set text and color based on current FIU_TTM x value
        try:
            stat = nps.getStatusAll()[4]
            if not stat:
                self.setStyleSheet(green)
                self.setText("Off")
            else:
                laser.open()
                if laser.isEnabledOut():
                    self.setStyleSheet(grey)
                    self.setText("{:05.2f}".format(laser.reqPowerAct()))
                else:
                    self.setStyleSheet(green)
                    self.setText("Disabled")
        except:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()

class Calib_out(QLabel):
    """A widget to get the MIR sources"""

    def __init__(self, *args, refresh_rate:int = refresh, **kwargs):
        """Constructor for calib out widget
        Args:
            refresh_rate = number of milliseconds to wait before refreshing value
        """

        super().__init__(*args, **kwargs)

        # create a repeating timer to call update
        self.timer =QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(refresh_rate)

        # create a one time timer to update initially
        setup_timer = QTimer(self)
        setup_timer.setSingleShot(True)
        setup_timer.timeout.connect(self.update)
        setup_timer.start(10)

    def update(self):
        """updates the size and text in the widget"""

        # set text and color based on current FIU_TTM x value
        try:
            stat = nps.getStatusAll()[2]
            self.setStyleSheet(grey)
            self.setText("On" if stat else "Off")
        except ScriptOff:
            self.setText("?")
            self.setStyleSheet(red)
        # run QLabel's update method
        super().update()
"""
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