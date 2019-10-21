import sys
from datetime import datetime, timezone
from PyQt5 import uic
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, \
    QMainWindow, QFileDialog, QMessageBox, QHeaderView


class MainWnd(QMainWindow):

    def __init__(self):
        super().__init__()
        uic.loadUi('./ui/MainWnd.ui', self)
        self.file_buttons = [
            self.ephemeridesButton,
            self.densityButton,
            self.fieldLineButton]
        [b.clicked.connect(self.choose_file) for b in self.file_buttons]
        self.radios = [
            self.flipRadioButton,
            self.manualRadioButton]
        [b.clicked.connect(self.change_mode) for b in self.radios]
        self.startButton.clicked.connect(self.run)

        self.model = QStandardItemModel()
        headers = [
            'Time',
            'Sat. L',
            'Sat. Alt',
            'Sat. Lat',
            'Sat. Lon',
            'L',
            'Alt',
            'Lat',
            'Lon',
            'dL',
            'dAlt',
            'dLat',
            'dLon',
            ]
        self.model.setColumnCount(len(headers))
        self.model.setHorizontalHeaderLabels(headers)
        self.tableView.setModel(self.model)

        self.showMaximized()

    def choose_file(self, e):
        filename = QFileDialog.getOpenFileName(self)[0]
        if filename:
            sender = self.sender()
            if sender is self.ephemeridesButton:
                edit = self.ephemeridesEdit
            elif sender is self.densityButton:
                edit = self.densityEdit
            elif sender is self.fieldLineButton:
                edit = self.fieldLineEdit
            edit.setText(filename)

    def change_mode(self):
        sender = self.sender()
        flip = [
            self.fieldLineButton,
            self.dAltSpinBox
            ]
        manual = [
            self.shellSpinBox,
            self.dShellSpinBox,
            self.latSpinBox,
            self.lonSpinBox]
        if sender is self.flipRadioButton:
            [w.setEnabled(True) for w in flip]
            [w.setEnabled(False) for w in manual]
        elif sender is self.manualRadioButton:
            [w.setEnabled(False) for w in flip]
            [w.setEnabled(True) for w in manual]

    def run(self):
        if self.validate():
            self.model.removeRows(0, self.model.rowCount())
            rf = RBSP_finder()
            (rf.addEph(self.ephemeridesEdit.text()).
             addDen(self.densityEdit.text()).
             addDLat(self.dLatSpinBox.value()).
             addDLon(self.dLonSpinBox.value()))
            flip = self.flipRadioButton.isChecked()
            rf.addType('f' if flip else 'm')
            if flip:
                (rf.addLin(self.fieldLineEdit.text()).
                 addDAlt(self.dAltSpinBox.value()))
            else:
                (rf.addL(self.shellSpinBox.value()).
                 addDL(self.dShellSpinBox.value()).
                 addLat(self.latSpinBox.value()).
                 addLon(self.lonSpinBox.value()))
            self.startButton.setEnabled(False)
            results = rf.process()
            for r in results:
                self.model.appendRow([QStandardItem(x) for x in r])
            self.model.sort(0)
            header = self.tableView.horizontalHeader()
            for i in range(header.count()-1):
                header.setSectionResizeMode(i+1, QHeaderView.Stretch)
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            self.startButton.setEnabled(True)
        else:
            self.show_error('Input parameters are incorrect.')

    def validate(self):
        eph_filename = bool(self.ephemeridesEdit.text())
        density_filename = bool(self.densityEdit.text())
        flip = self.flipRadioButton.isChecked()
        flip_filename = bool(self.fieldLineEdit.text())
        return (
            eph_filename and density_filename and not flip or
            eph_filename and density_filename and flip and flip_filename)

    def show_error(self, message):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText(message)
        msg.setWindowTitle('Error')
        msg.show()
        msg.exec_()


class RBSP_finder:

    def __init__(self):
        self.request = dict()

    def addType(self, s):
        if s.startswith('f') or s.startswith('F'):
            self.request['flip'] = True
        elif s.startswith('m') or s.startswith('M'):
            self.request['flip'] = False
        return self

    def addEph(self, s):
        self.request['eph'] = s
        return self

    def addDen(self, s):
        self.request['den'] = s
        return self

    def addLin(self, s):
        self.request['lin'] = s
        return self

    def addDAlt(self, s):
        self.request['dAlt'] = s
        return self

    def addDLat(self, s):
        self.request['dLat'] = s
        return self

    def addDLon(self, s):
        self.request['dLon'] = s
        return self

    def addLat(self, s):
        self.request['lat'] = s
        return self

    def addLon(self, s):
        self.request['lon'] = s
        return self

    def addL(self, s):
        self.request['l'] = s
        return self

    def addDL(self, s):
        self.request['dL'] = s
        return self

    def process(self):
        sat = self._load_sat(self.request['eph'])
        d_lat_max = self.request['dLat']
        d_lon_max = self.request['dLon']
        r = []
        if self.request['flip']:
            tube, shell = self._load_tube(self.request['lin'])
            d_alt_max = self.request['dAlt']
            for t in tube:
                alt = t[0]
                lat = t[1]
                lon = t[2]
                for s in sat:
                    s_time = s[0]
                    s_alt = s[1]
                    s_lat = s[2]
                    s_lon = s[3]
                    s_l = s[4]

                    d_alt = abs(s_alt - alt)
                    d_lat = abs(s_lat - lat)
                    d_lon = abs(s_lon - lon)
                    if (d_alt <= d_alt_max
                        and d_lat <= d_lat_max
                            and d_lon <= d_lon_max):
                        r.append([
                                  s_time.isoformat(),
                                  '{:6.3f}'.format(s_l),
                                  '{:8.1f}'.format(s_alt),
                                  '{:6.1f}'.format(s_lat),
                                  '{:6.1f}'.format(s_lon),
                                  '{:6.3f}'.format(shell),
                                  '{:8.1f}'.format(alt),
                                  '{:6.1f}'.format(lat),
                                  '{:6.1f}'.format(lon),
                                  '{:6.3f}'.format(s_l - shell),
                                  '{:8.1f}'.format(s_alt - alt),   # (+-)d_alt
                                  '{:6.1f}'.format(s_lat - lat),   # (+-)d_lat
                                  '{:6.1f}'.format(s_lon - lon)])  # (+-)d_lon
        return r

    def _load_tube(self, filename):
        with open(filename) as file:
            lines = []
            head = True
            for line in file.readlines():
                if line.startswith('  L-shell ='):
                    shell = float(line.split()[2][:-1])
                if line.startswith('    pt     alt    arc_len'):
                    header = line.split()
                    head = False
                    continue
                if not head and line:
                    lines.append(line.split())

        alt_index = header.index('alt')
        lat_index = header.index('G_lat')
        lon_index = header.index('G_long')

        tube = [[float(x[alt_index]),
                 float(x[lat_index]),
                 float(x[lon_index])] for x in lines]

        return tube, shell

    def _load_sat(self, filename):
        with open(filename) as file:
            lines = []
            head = True
            for line in file.readlines():
                if not head and line:
                    lines.append(line.split())
                elif line.startswith('# YYYY-MM-DDTHH:MM:SS.SSSSZ'):
                    head = False

        sat_time_i = 0
        sat_alt_i = 14
        sat_lat_i = 12
        sat_lon_i = 13
        sat_l_i = 174

        format = '%Y-%m-%dT%H:%M:%S.0000Z'
        sat = [[datetime.strptime(x[sat_time_i], format),
                float(x[sat_alt_i]),
                float(x[sat_lat_i]),
                float(x[sat_lon_i]) + (360 if float(x[sat_lon_i]) < 0 else 0),
                float(x[sat_l_i])] for x in lines]
        return sat


if __name__ == '__main__':
    app = QApplication(sys.argv)
    wnd = MainWnd()
    sys.exit(app.exec_())
