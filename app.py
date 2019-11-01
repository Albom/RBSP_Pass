import sys
from datetime import datetime, timezone, timedelta
from PyQt5 import uic
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, \
    QMainWindow, QFileDialog, QMessageBox, QHeaderView
from cdflib import CDF, cdfepoch


class MainWnd(QMainWindow):

    def __init__(self):
        super().__init__()
        uic.loadUi('./ui/MainWnd.ui', self)
        self.file_buttons = [
            self.ephemeridesButton,
            self.densityButton,
            self.fieldLineButton]
        [b.clicked.connect(self.choose_file) for b in self.file_buttons]
        self.startButton.clicked.connect(self.run)
        self.saveButton.clicked.connect(self.save)
        self.aboutButton.clicked.connect(self.about)

        self.model = QStandardItemModel()
        self.headers = [
            '{:20s}'.format('DateTime'),
            '{:>10s}'.format('Time'),
            '{:>10s}'.format('Sat_L'),
            '{:>10s}'.format('Sat_Alt'),
            '{:>10s}'.format('Sat_Lat'),
            '{:>10s}'.format('Sat_Lon'),
            '{:>10s}'.format('L'),
            '{:>10s}'.format('Alt'),
            '{:>10s}'.format('Lat'),
            '{:>10s}'.format('Lon'),
            '{:>10s}'.format('dL'),
            '{:>10s}'.format('dAlt'),
            '{:>10s}'.format('dLat'),
            '{:>10s}'.format('dLon'),
            '{:>10s}'.format('Ne')
            ]
        self.model.setColumnCount(len(self.headers))
        self.model.setHorizontalHeaderLabels([s.strip() for s in self.headers])
        self.tableView.setModel(self.model)

        self.program_name = 'RBSP_Pass version 1.0'
        self.setWindowTitle(self.program_name)

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

    def run(self):
        if self.validate():
            self.model.removeRows(0, self.model.rowCount())
            rf = RBSP_finder()
            rf.addEph(self.ephemeridesEdit.text())
            rf.addDen(self.densityEdit.text())
            is_flip = self.tabWidget.currentIndex() == 1
            rf.addType('f' if is_flip else 'm')
            if is_flip:
                rf.addLin(self.fieldLineEdit.text())
                rf.addDAlt(self.dAltSpinBox.value())
                rf.addDLat(self.dLatSpinBox.value())
                rf.addDLon(self.dLonSpinBox.value())
            else:
                rf.addL(self.shellSpinBox.value())
                rf.addDL(self.dShellSpinBox.value())
                rf.addLat(self.latSpinBox.value())
                rf.addDLat(self.dLatSpinBox_2.value())
                rf.addLon(self.lonSpinBox.value())
                rf.addDLon(self.dLonSpinBox_2.value())
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
        is_flip = self.tabWidget.currentIndex() == 1
        if is_flip:
            flip_filename = bool(self.fieldLineEdit.text())
            return eph_filename and density_filename and flip_filename
        else:
            return eph_filename and density_filename

    def save(self):
        filename, _ = QFileDialog.getSaveFileName()

        if filename:
            model = self.tableView.model()
            data = []
            for row in range(model.rowCount()):
                data.append([])
                for column in range(model.columnCount()):
                    index = model.index(row, column)
                    data[row].append(model.data(index))

            with open(filename, 'w') as file:
                for s in self.headers:
                    file.write(s)
                file.write('\n')
                for row in range(model.rowCount()):
                    for column in range(model.columnCount()):
                        file.write(data[row][column])
                    file.write('\n')

    def about(self):
        text = (
            '\n\n'
            '© 2019 Oleksandr Bogomaz'
            '\n'
            'o.v.bogomaz1985@gmail.com')

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText(self.program_name + text)
        msg.setWindowTitle('About')
        msg.show()
        msg.exec_()

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
        densities = self._load_densities(self.request['den'])

        def get_density():
            delta_min = timedelta(minutes=1)
            ne = -1
            for d in densities:
                delta = abs(s_time - d)
                if delta < delta_min:
                    ne = densities[d]
                    delta_min = delta
            return ne

        sat = self._load_sat(self.request['eph'])
        d_lat_max = self.request['dLat']
        d_lon_max = self.request['dLon']
        r = []

        def append_results():
            r.append([
                      '{:20s}'.format(s_time.isoformat()),
                      '{:10.5f}'.format(dec),
                      '{:10.3f}'.format(s_l),
                      '{:10.2f}'.format(s_alt),
                      '{:10.2f}'.format(s_lat),
                      '{:10.2f}'.format(s_lon),
                      '{:10.3f}'.format(shell),
                      '{:10.2f}'.format(alt),
                      '{:10.2f}'.format(lat),
                      '{:10.2f}'.format(lon),
                      '{:10.3f}'.format(s_l - shell),
                      '{:10.2f}'.format(d_alt),
                      '{:10.2f}'.format(d_lat),
                      '{:10.2f}'.format(d_lon),
                      '{:10.2f}'.format(ne)])

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

                    dec = s_time.hour + s_time.minute/60. + s_time.second/3600.

                    d_alt = abs(s_alt - alt)
                    d_lat = abs(s_lat - lat)
                    d_lon = abs(s_lon - lon)
                    if (d_alt <= d_alt_max
                        and d_lat <= d_lat_max
                            and d_lon <= d_lon_max):
                        ne = get_density()
                        d_alt = s_alt - alt
                        d_lat = s_lat - lat
                        d_lon = s_lon - lon
                        append_results()
        else:

            shell = self.request['l']
            lat = self.request['lat']
            lon = self.request['lon']

            d_l_max = self.request['dL']

            for s in sat:
                s_time = s[0]
                s_alt = s[1]
                s_lat = s[2]
                s_lon = s[3]
                s_l = s[4]

                dec = s_time.hour + s_time.minute/60. + s_time.second/3600.

                d_l = abs(s_l - shell)
                d_lat = abs(s_lat - lat)
                d_lon = abs(s_lon - lon)

                if (d_l <= d_l_max
                    and d_lat <= d_lat_max
                        and d_lon <= d_lon_max):
                    ne = get_density()
                    d_l = s_l - shell
                    d_lat = s_lat - lat
                    d_lon = s_lon - lon
                    alt = -1
                    d_alt = -1
                    append_results()
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

    def _load_densities(self, filename):
        cdf = CDF(filename)
        timestamps, densities = (
            cdf.varget('Epoch'),
            cdf.varget('density'))
        dates = [datetime.fromtimestamp(t, timezone.utc).replace(
            tzinfo=None, microsecond=0)
                 for t in cdfepoch.unixtime(timestamps)]

        mdict = dict(zip(dates, densities))
        return mdict


if __name__ == '__main__':
    app = QApplication(sys.argv)
    wnd = MainWnd()
    sys.exit(app.exec_())
