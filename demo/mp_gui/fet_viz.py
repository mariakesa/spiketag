
from PyQt4 import QtGui, QtCore
import sys
import numpy as np
from spiketag.view.grid_scatter3d import grid_scatter3d
from spiketag.utils import Timer

if __name__ == '__main__':
    appQt = QtGui.QApplication(sys.argv)
    # appQt.setStyle('gtk')
    # appQt.setGraphicsSystem('raster')
    rows, cols = 6, 8
    win = grid_scatter3d(rows, cols)
    win.show()

    N = 2000
    fet = np.random.randn(N, 9)
    clu = np.zeros((N,)).astype(np.int)
    for idx in range(rows*cols):
        with Timer('fet_view[{0}].set_data'.format(idx)):
            win.fet_view[idx].set_data(fet, clu)
            win.fet_view[idx]._timer.start()
            win.fet_view[idx].debug = True
    # win.fet_view[0].highlight(np.arange(1000))
    appQt.exec_()
