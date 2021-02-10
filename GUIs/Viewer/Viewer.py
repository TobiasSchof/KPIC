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

        # activate any inactive control scripts
        if not self.proc.tc.is_active():
            self.proc.tc.activate_control_script()
        if not self.proc.is_active(base=True, vis=True):
            self.proc.activate_control_script(base=True, vis=True)

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

        # set subtraction checkboxes to proper positions
        try:
            self.bias_sub.setChecked(self.proc.is_minus_bias())
            self.bkgrd_sub.setChecked(self.proc.is_minus_bkgrd())
            self.ref_sub.setChecked(self.proc.is_minus_ref())
        except: pass
        # connect subtraction checkboxes
        self.bias_sub.toggled.connect(self.proc.use_minus_bias)
        self.bkgrd_sub.toggled.connect(self.proc.use_minus_bkgrd)
        self.ref_sub.toggled.connect(self.proc.use_minus_ref)
        # connect 'save dark' button
        #save_bias = lambda : self.proc.tc.save_dark(num = min(self.proc.tc.get_fps() * 60, 50))
        #self.bias_save.clicked.connect(save_bias)
        # connect 'take' buttons
        #take_bkgrd = lambda : self.proc.Bkgrd.set_data(self.proc.Proc.get_data(reform = True))
        #self.bkgrd_take.clicked.connect(take_bkgrd)
        #take_ref = lambda : self.proc.Ref.set_data(self.proc.Proc.get_data(reform = True))
        #self.ref_take.clicked.connect(take_ref)

        # connect raw img checkbox

        self.show()

        self.setWindowTitle("KPIC Display")
        self.base_img_chk.toggled.connect(self.proc.use_base)
    
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