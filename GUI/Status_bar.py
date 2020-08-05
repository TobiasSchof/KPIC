from PyQt5.QtWidgets import QWidget, QApplication, QPushButton, QStackedWidget, QFrame 
from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QHBoxLayout
from PyQt5.QtGui import QColor
import sys

from Status_buttons import View, K2AO, NSPEC, Scripts

# define a class to handle the status bar
class Main(QWidget):

    def __init__(self):
        super().__init__()

        # list to hold instantiations of Mod_Wrap classes
        self.groups = []

        # create the UI
        self.initUI()

    def btn_click(self):
        """A method to react to button presses

        Will switch between expanded and quickview modes for each group
        """

        # formatting expansion/collapse before adding widgets creates stutter
        #   so here we just decide if formatting is necessary
        exp = False
        col = False

        # moving from collapsed view to expanded view
        if not any([btn.showing for btn in self.groups]) and \
            any([btn.isChecked() for btn in self.groups]): exp = True
         # moving from expanded view to collapsed view
        elif not any([btn.isChecked() for btn in self.groups]) and \
            any([btn.showing for btn in self.groups]): col = True

        # add/remove modules as necessary
        for idx, btn in enumerate(self.groups):
            # if a button was checked but modules aren't displayed, display them
            if btn.isChecked() and not btn.showing:
                btn.show_modules(self.layout, idx*2)
            # if a button is not checked but modules are displayed, remove them
            elif not btn.isChecked() and btn.showing:
                btn.hide_modules()

        # format expansion/collapse if necessary
        if exp:
            # draw in vertical lines
            for vline in self.vlines: self.layout.addWidget(*vline)

            # set minimum row height
            for row, height in enumerate(self.row_height):
                self.layout.setRowMinimumHeight(row + 2, height)

            # change gui height to expanded size
            if self.exp_height is not None:
                self.setMinimumHeight(self.exp_height)
                self.setFixedHeight(self.minimumHeight())

            # reduce spacing to fit vertical lines
            self.layout.setHorizontalSpacing(10)
        elif col:
            # remove the vertical lines from the display
            for vline in self.vlines: vline[0].setParent(self.holder)

            # keep spacing without vertical lines
            self.layout.setHorizontalSpacing(21)

            # reset row heights
            for row, height in enumerate(self.row_height):
                self.layout.setRowMinimumHeight(row + 2, 0)

            # revert gui size
            self.setMinimumHeight(self.coll_height)
            self.setFixedHeight(self.minimumHeight())

    def initUI(self):
        """creates the starting place for the UI"""

        # add a holder widget to store items we want to remove from display
        self.holder = QWidget()

        # create a grid to place buttons
        self.layout = QGridLayout()
        # have this widget use the layout
        self.setLayout(self.layout)

        # create widgets for groups
        self.groups = []
        # create a button for each group
        self.groups.append(View())
        self.groups.append(K2AO())
        self.groups.append(NSPEC())
        self.groups.append(Scripts())
        # trigger btn_click when any of the buttons are pressed
        for btn in self.groups:
            btn.con_click(self.btn_click)
        # put buttons in gui
        for idx, btn in enumerate(self.groups):
            self.layout.addWidget(btn, 0, idx*2, 1, 1)

        # the maximum number of rows needed by the expanded view
        self.max_rows = max([len(group.modules)+1 for group in self.groups])
        # the largest width of any module or button
        self.gp_width = max([gp.sizeHint().width() for gp in self.groups] + \
            [mod.sizeHint().width() for gp in self.groups for mod in gp.modules])

        # set column minimum width to the above found self.gp_width to keep formatting consistent 
        for idx in range(0, len(self.groups)):
            self.layout.setColumnMinimumWidth(idx*2, self.gp_width)

        # create vertical line separators
        self.vlines = []
        for col in range(0, len(self.groups)-1):
            # store vlines with their coordinates in the grid
            self.vlines.append([QFrame(), 1, 2*col+1, self.max_rows+1, 1])
            self.vlines[-1][0].setFrameShape(QFrame.VLine)

        # get all the modules to decide on row height
        temp = [gp.modules for gp in self.groups]
        # the height of each row
        self.row_height = []
        for i in range(0, self.max_rows-1):
           self.row_height.append(max([mods[i].sizeHint().height() for mods in temp if i < len(mods)])) 

        # the height of the gui when collapsed
        self.coll_height = self.layout.sizeHint().height()

        # we want to know the shape of the expanded gui
        # check all the buttons so all modules paint
        for btn in self.groups:
            btn.setChecked(True)
        # placeholder variables for max rows and spacing between buttons
        self.exp_height = None
        # draw expanded gui
        self.btn_click()
        # note height
        self.exp_height = self.layout.sizeHint().height()
        # uncheck the buttons now
        for btn in self.groups:
            btn.setChecked(False)

        # reset gui
        self.btn_click()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    ex = Main()
    ex.show()

    sys.exit(app.exec_())