from PyQt5.QtWidgets import QApplication, QStackedWidget, QSizePolicy
from configparser import ConfigParser
from time import sleep
from views import Expanded, Brief
import sys

class Stack(QStackedWidget):

    def __init__(self, views:list):
        super(Stack, self).__init__()

        for view in views:
            view.view_val.currentIndexChanged.connect(self.set_view)
            self.addWidget(view)

        self.show()

    def set_view(self):
        # ignore size policy of the view we are no longer using
        self.currentWidget().setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        self.setCurrentIndex(self.currentWidget().view_val.currentIndex())
        self.currentWidget().view_val.setCurrentIndex(self.currentIndex())

        # use size policy of the new view
        self.currentWidget().setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        # set size to sizehint of current view
        self.setFixedSize(self.currentWidget().sizeHint())

    def sizeHint(self):
        return self.currentWidget().sizeHint()

    def minimumSizeHint(self):
        return self.currentWidget().sizeHint()


app = QApplication(sys.argv)
views = [Expanded(), Brief()]
stack = Stack(views)
# in order to resize to current widget, we set stack's size policy to maximum (which has shrink flag)
stack.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
sys.exit(app.exec_())