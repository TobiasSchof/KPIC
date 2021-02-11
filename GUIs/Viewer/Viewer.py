#!/usr/bin/env kpython3

# inherent python libraries
from argparse import ArgumentParser
from time import sleep
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

        # connect medfilt checkbox
        self.med_filt.toggled.connect(self.proc.use_medfilt)
        try:
            self.med_filt.setChecked(self.proc.is_medfilt())
        except: pass

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
        save_bias = lambda : self.proc.tc.save_dark(num = min(self.proc.tc.get_fps() * 60, 50))
        self.bias_save.clicked.connect(save_bias)
        # connect 'take' buttons
        take_bkgrd = lambda : self.proc.Vis_Bkgrd.set_data(self.proc.tc.Img.get_data(reform = True))
        self.bkgrd_take.clicked.connect(take_bkgrd)
        take_ref = lambda : self.proc.Vis_Ref.set_data(self.proc.tc.Img.get_data(reform = True))
        self.ref_take.clicked.connect(take_ref)

        # hide config settings if not in lab
        if not is_lab:
            cam_conf_layout = self.view_opt_layout.itemAtPosition(1,0)
            # delete all widgets in layout
            while self.cam_config_layout.count():
                item = self.cam_config_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)

            # delete layout
            self.cam_config_layout.setParent(None)
        # if in lab disable hmag field
        else:
            self.view_opt_layout.itemAtPosition(0,1).widget().setEnabled(False)

        self.show()

        while not self.proc.is_active(vis=True):
            sleep(.1)
        self.proc.is_processing(vis = True)

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

if __name__ == "__main__":

    # parse for tags

    # create argument parser
    parser = ArgumentParser(add_help=False)

    parser.add_argument("-lab", action="store_true")

    # parse args
    args = parser.parse_args()

    # check for config flag
    is_lab = (args.lab)

    app = QApplication(sys.argv)
    widge = Stack()
    sys.exit(app.exec_())