import os

from PyQt5.QtWidgets import QLabel, QPushButton, QLineEdit, QFrame, QComboBox, QGroupBox, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QPixmap, QPainter, QImage, QValidator, QIntValidator
from PyQt5 import uic
import numpy as np

# nfiuserver libraries
from KPIC_shmlib import Shm
import resources.no_img

class Loc_Selection(QFrame):
    """A class to represent the QFrame holding PSF location information in the KPIC GUI"""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

    def setup(self):
        # variable to store which index is the custom option
        self.custom_idx = 5

        # get all the parts we will be interacting with
        self.drop = self.findChild(QComboBox, "psf_loc_dropdown")
        self.x = self.findChild(QLineEdit, "psf_x_input")
        self.y = self.findChild(QLineEdit, "psf_y_input")
        self.submit = self.findChild(QPushButton, "psf_loc_btn")
        self.input_frame = self.findChild(QFrame, "psf_input_frame")

        if self.drop.currentIndex() != self.custom_idx:
            self.input_frame.hide()

        # connect method to monitor goal change
        self.drop.currentIndexChanged.connect(self.sel_chng)
        
    def sel_chng(self):
        """A method to handle when the goal selection drop down is changed"""

        # if option selected is "custom", show input fields
        if self.drop.currentIndex() == self.custom_idx:
            self.input_frame.show()
        # otherwise hide input fields
        else:
            self.input_frame.hide()

class Img(QLabel):
    """A widget to display the image and maintain aspect ratio while changing size"""

    def __init__(self, *args, refresh_rate:int = 40, **kwargs):
        """Constructor
        
        Args:
            refresh_rate = the number of milliseconds to wait before refreshing widget
            """

        super().__init__(*args, **kwargs)

        # save copy of placeholder image for if img file is old
        #   or doesn't exist
        self.placeholder = None
        # save copy of unscaled image so that we can rescale GUI
        self.unscaled_img = None
        # save copy of scaled image
        self.scaled_img = None

        # store refresh rate
        self.refresh_rate = refresh_rate

        self.timer = QTimer()
        self.timer.timeout.connect(self.setup)
        self.timer.start(10)

    def setup(self):
        """Saves an unscaled image"""

        self.placeholder = QPixmap(":/placeholder/no_img.jpg")
        self.unscaled_img = self.placeholder
        self.scaled_img = self.unscaled_img.scaled(self.width(), self.height(), Qt.KeepAspectRatio)

        self.setPixmap(self.placeholder)

        self.Img = "/tmp/Track_Cam/RAWIMG.im.shm"

        self.timer.timeout.connect(self.update)
        self.timer.start(self.refresh_rate)

    def update(self):
        """Method to try to fetch a new image"""

        try:
            if type(self.Img) is str:
                self.Img = Shm(self.Img)

            raw_img = self.Img.get_data()
            if self.parent().log():
                raw_img = np.log10(np.clip(raw_img, 1, None)).astype(np.float16)
                if self.parent().img_min() is not None or self.parent().img_max() is not None:
                    raw_img = np.clip(raw_img, self.parent().img_min(), self.parent().img_max())

            self.unscaled_img = QPixmap(QImage(raw_img, self.Img.mtdata["size"][0],
                self.Img.mtdata["size"][1], QImage.Format_Grayscale16))
            self.scaled_img = self.unscaled_img.scaled(self.width(), self.height(), Qt.KeepAspectRatio)

            self.setPixmap(self.scaled_img)
        except:
            if type(self.Img) is not str and not os.path.exists(self.Img.fname):
                self.Img = self.Img.fname
            if self.unscaled_img != self.placeholder:
                self.unscaled_img = self.placeholder
                self.scaled_img = self.unscaled_img.scaled(self.width(), self.height(), Qt.KeepAspectRatio)
                self.setPixmap(self.scaled_img)

        self.timer.start(self.refresh_rate)

    def resizeEvent(self, event):
        """Changes the resize event to scale picture keeping aspect ratio"""

        super().resizeEvent(event)

        # resize event is called in constructor, before base_img is defined
        if not self.unscaled_img is None:
            self.scaled_img = self.unscaled_img.scaled(self.width(), self.height(), Qt.KeepAspectRatio)
            self.setPixmap(self.scaled_img)

    def minimumSizeHint(self):
        """Returns the size of the unscaled image as a minimum size"""

        try:
            return QSize(self.unscaled_img.width(), self.unscaled_img.height())
        except:
            return QSize(640, 512)

class Log_Scale(QGroupBox):
    """A widget to toggle the log scale on the image"""

    def __init__(self, *args, **kwargs):
        """Constructor for log scale component"""

        # run super constructor
        super().__init__(*args, **kwargs)

    def setup(self):
        """A method to set up the input boxes"""

        # collect relevant parts
        self.__min = self.findChild(log_lineedit, "min_input")
        self.__max = self.findChild(log_lineedit, "max_input")

        self.__min.setValidator(log_lineedit.log_validator(parent_scope=self, which='min'))
        self.__max.setValidator(log_lineedit.log_validator(parent_scope=self, which='max'))

        self.min = None
        self.max = None

class log_lineedit(QLineEdit):
    """A QLineEdit that reverts text if focus is lost with intermediate input"""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.last_valid = ""

    def focusOutEvent(self, QFocusEvent):
        """Override to revert text if it is in 'Intermediate' state"""

        _state, _, _ = self.validator().validate(self.text(), self.pos())
        if _state == QValidator.Intermediate: self.setText(self.last_valid)
        elif _state == QValidator.Acceptable: self.last_valid = self.text()

        super().focusOutEvent(QFocusEvent)

    class log_validator(QValidator):
        """A validator to validate the min value for the log scale"""

        def __init__(self, *args, parent_scope, which, **kwargs):
            """Stores the QGroubBox this belongs to

            Args:
                parent_scope = the groupbox that this exists within
                which = one of 'min' or 'max'
            """

            super().__init__(*args, **kwargs)

            self.p_sc = parent_scope
            self.role = which

        def validate(self, text:str, pos:str):
            """sets the min value in the log_scale parent of this validator"""

            if text == "":
                if self.role == 'min': self.p_sc.min = None
                else: self.p_sc.max = None
                return QValidator.Acceptable, text, pos

            _state = QValidator.Invalid
            try: 
                num = int(text)
                # intermediate will be rejected on focus loss
                if self.role == 'max': _state = QValidator.Intermediate
            except: return _state, text, pos

            if (self.role == 'min' and (self.p_sc.max is None or num < self.p_sc.max))\
                or (self.role == 'max' and (self.p_sc.min is None or num > self.p_sc.min)):

                _state = QValidator.Acceptable

                if self.role == 'min': self.p_sc.min = num
                else: self.p_sc.max = num

            return _state, text, pos