# inherent python libraries
from configparser import ConfigParser
from time import sleep
import sys

# installed libraries
from PyQt5.QtWidgets import QWidget, QComboBox
from PyQt5 import uic

# night_view_widgets has all the widgets in the .ui
from night_view_widgets import *
# this is the KPIC logo
import resources.KPIC_logo_rc

# a widget to handle the brief view
class Brief(QWidget):

    # constructor
    def __init__(self, resource_path):
        # first we call the super constructor
        super(Brief, self).__init__()

        # then we load the layout from the .ui file
        uic.loadUi("{}/status_bar_night_brief.ui".format(resource_path), self)

        # update fields with callbacks so not everything has to wait
        self.toupdate = []
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_callback)

        # we want to keep the QComboBox that selects the type of display accessible by other classes, so we make a variable for it
        self.view_val = self.findChild(QComboBox, "view_val")
        # we want to set the current view box to brief
        self.view_val.setCurrentIndex(1)

        # we load in all the QLabels that need to be updated
        self.elements = {}
        self._load_elements()

    def _load_elements(self):
        """A method to load the updatable elements from the .ui file"""

        ###### load Target Info elements ######
        self.elements["target_name"] = self.findChild(Target_name, "target_name")
        self.elements["elevation_val"] = self.findChild(Elevation, "elevation_val")
        self.elements["airmass_val"] = self.findChild(Airmass, "airmass_val")
        self.elements["rt_val"] = self.findChild(RT, "rt_val")
        ###### load Tracking Script elements ######
        self.elements["track_stat_val"] = self.findChild(Track_stat, "track_stat_val")
        self.elements["track_gain_val"] = self.findChild(Track_gain, "track_gain_val")
        self.elements["track_valid_val"] = self.findChild(Track_valid, "track_valid_val")
        self.elements["target_goal_val"] = self.findChild(Track_goal, "target_goal_val")
        self.elements["goal_pos_x_val"] = self.findChild(Goal_pos_x, "goal_pos_x_val")
        self.elements["goal_pos_y_val"] = self.findChild(Goal_pos_y, "goal_pos_y_val")
        self.elements["track_avg_val"] = self.findChild(Track_avg, "track_avg_val")
        self.elements["usr_offset_x_val"] = self.findChild(Usr_offset_x, "usr_offset_x_val")
        self.elements["usr_offset_y_val"] = self.findChild(Usr_offset_y, "usr_offset_y_val")
        self.elements["astro_raw_pa_val"] = self.findChild(Astro_raw_pa, "astro_raw_pa_val")
        self.elements["astro_raw_sep_val"] = self.findChild(Astro_raw_sep, "astro_raw_sep_val")
        self.elements["astro_dist_pa_val"] = self.findChild(Astro_dist_pa, "astro_dist_pa_val")
        self.elements["astro_dist_sep_val"] = self.findChild(Astro_dist_sep, "astro_dist_sep_val")
        self.elements["wl_tc_val"] = self.findChild(WL_tc, "wl_tc_val")
        self.elements["wl_scf_val"] = self.findChild(WL_ScF, "wl_scf_val")
        ###### load Tracking Camera elements ######
        self.elements["track_cam_temp_val"] = self.findChild(Track_cam_temp, "track_cam_temp_val")
        self.elements["track_cam_tint_val"] = self.findChild(Track_cam_tint, "track_cam_tint_val")
        self.elements["track_cam_fps_val"] = self.findChild(Track_cam_fps, "track_cam_fps_val")
        self.elements["track_cam_ndr_val"] = self.findChild(Track_cam_ndr, "track_cam_ndr_val")
        self.elements["track_cam_crop_val"] = self.findChild(Track_cam_crop, "track_cam_crop_val")
        self.elements["track_cam_crop_x_val"] = self.findChild(Track_cam_crop_x, "track_cam_crop_x_val")
        self.elements["track_cam_crop_y_val"] = self.findChild(Track_cam_crop_y, "track_cam_crop_y_val")

    def update_callback(self):
        # if there are no more widgets to update, do nothing
        if len(self.toupdate) == 0: return

        # otherwise, pop a widget
        elem = self.toupdate.pop()
        # update it
        elem.update()
        # start a timer to call the next update
        self.timer.start(10)

    def update_vals(self):
        """A method that updates all the values in the GUI"""

        self.toupdate = list(self.elements.values())

        self.timer.start(10)