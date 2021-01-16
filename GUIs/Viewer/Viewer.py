#!/usr/bin/env kpython3

# inherent python libraries
import sys

# installs
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5 import uic

# nfiuserver libraries
from Viewer_Widgets import *
from Track_Cam_process import TC_process

resource_path = "/Transfer/Viewer/resources"

class Stack(QWidget):

    def __init__(self):
        """Constructor"""

        super().__init__()

        # instantiate TC_process class
        self.proc = TC_process()

        uic.loadUi("{}/Viewer.ui".format(resource_path), self)

        ######## setup widgets in Tracking tab ########
        self.interfaces.findChild(Loc_Selection, "psf_loc_frame").setup()

        ######## setup widgets in Processing tab ########

        # set up log/sqrt scale checkboxes
        log_scl = self.interfaces.findChild(Scale_chk_box, "log_scl")
        sqrt_scl = self.interfaces.findChild(Scale_chk_box, "sqrt_scl")

        scls = [log_scl, sqrt_scl]
        log_scl.setup(scls, self.proc.use_log_scale)
        sqrt_scl.setup(scls, self.proc.use_sqrt_scale)

        # set starting values for scale checkboxes
        try:
            if self.proc.is_log_scale(): log_scl.setChecked(True)
            elif self.proc.is_sqrt_scale(): sqrt_scl.setChecked(True)
        except: pass

        # setup minimize interface button
        self.minimize_btn.clicked.connect(self.btn_click)

        self.show()

        self.setWindowTitle("KPIC Display")
    
    def btn_click(self):
        """method that minimizes or maximizes the control panel"""

        # variable for storing new geometry
        width = self.geometry().width()

        if self.minimize_btn.isChecked():
            self.minimize_btn.setText("<")
            width += self.interfaces.geometry().width()
        else:
            self.minimize_btn.setText(">")
            width -= self.interfaces.geometry().width()

        app.processEvents()
        self.resize(width, self.geometry().height())

app = QApplication(sys.argv)
widge = Stack()
sys.exit(app.exec_())