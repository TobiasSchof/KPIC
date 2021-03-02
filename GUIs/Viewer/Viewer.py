#!/usr/bin/env kpython3

# inherent python libraries
from argparse import ArgumentParser
from time import sleep
import sys, os

# installs
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtGui import QTransform
from PyQt5 import uic

# nfiuserver libraries
from Viewer_Widgets import *
from Track_Cam_process import TC_process
from Mode_Change_cmds import Mode_Change_cmds

resource_path = os.path.dirname(__file__)+"/resources"

class Shm_Watcher(QObject):
    """A class to watch a Shm and emit a Qt signal when it's updated"""

    do_update = pyqtSignal([np.ndarray])

    def setup(self, shm_fname):
        """A function to setup this widget
        
        Args:
            shm_fname = the name of the shared memory to watch
        """

        # shms to update and read from
        self.shm = Shm(shm_fname, sem = True)

        # start thread with watcher
        self.alive = True
        self.watcher_thread = threading.Thread(target = self.watch)
        self.watcher_thread.start()

    def watch(self):
        """A method that watches for a shm update and emits a signal with the updated value"""

        while self.alive:
            # wait for shm to be updated
            try:
                self.do_update.emit(self.shm.get_data(check = True))
            except:
                sleep(5)

            # repeat loop

    def clean_close(self):
        """A method to perform a clean close of this widget"""

        # set self to die
        self.alive = False
        # increment semaphore to continue
        self.shm.sem.release()

        # wait for thread to join
        self.watcher_thread.join()

class Stack(QWidget):

    def __init__(self):
        """Constructor"""

        super().__init__()

        # list to store any widgets that need to be cleaned up
        self.watch_widgs = {}

        # instantiate cmds classes
        self.proc = TC_process()
        self.mc = Mode_Change_cmds()

        # activate any inactive control scripts
        if not self.proc.tc.is_active():
            self.proc.tc.activate_control_script()
        if not self.proc.is_active():
            self.proc.activate_control_script()
        if not self.mc.is_active():
            self.mc.activate_control_script()

        uic.loadUi("{}/Viewer.ui".format(resource_path), self)

        ######## setup widgets in Processing tab ########

        # setup minimize interface button
        self.minimize_btn.clicked.connect(self.btn_click)

        save_bias = lambda : self.proc.tc.save_dark(num = min(self.proc.tc.get_fps() * 60, 50))
        self.bias_save.clicked.connect(save_bias)
        # connect 'take' buttons
        take_bkgrd = lambda : self.proc.Vis_Bkgrd.set_data(self.proc.tc.Img.get_data(reform = True))
        self.bkgrd_take.clicked.connect(take_bkgrd)
        take_ref = lambda : self.proc.Vis_Ref.set_data(self.proc.tc.Img.get_data(reform = True))
        self.ref_take.clicked.connect(take_ref)

        # hide config settings if not in lab
        if not is_lab:
            cam_conf_layout = self.view_opt_layout.itemAtPosition(2,0)
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

        # setup zoom buttons
        zoom_layout = self.view_opt_layout.itemAtPosition(1, 0)
        # connect zoom reset button
        self.rst_zoom.clicked.connect(lambda : self.image.vb.setRange(xRange = [0,self.image.img.width()],
            yRange = [0,self.image.img.height()]))
        # connect zoom save button
        self.sv_zoom.clicked.connect(self.do_sv_zoom)
        # connect zoom load button
        self.ld_zoom.clicked.connect(lambda : self.image.vb.setRange(xRange = self.sv_zm[0], yRange = self.sv_zm[1]))

        self.show()

        while not self.proc.is_active():
            sleep(.1)
        self.proc.is_processing()

        self.setWindowTitle("KPIC Display")

    def do_sv_zoom(self):
        """A method to save the current zoom state of the viewer"""

        self.sv_zm = self.image.vb.getState()["viewRange"]

        if not self.ld_zoom.isEnabled():
            self.ld_zoom.setEnabled(True)

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

    def closeEvent(self, e):
        """Method to run when widget is closed"""

        for fname in self.watch_widgs:
            self.watch_widgs[fname].clean_close()

        super().closeEvent(e)

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