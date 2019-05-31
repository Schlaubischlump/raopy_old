import os
import sys
import logging
from PyQt5.QtWidgets import QApplication, QListView, QHBoxLayout, QVBoxLayout, QMainWindow, QWidget, QPushButton, QFileDialog
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt

from raopy import RAOPPlayGroup, RAOPServiceListener, STATUS
from raopy.util import set_logs_enabled, set_loglevel, LOG

# enable only the most basic logs
set_logs_enabled(LOG.GROUP | LOG.RTSP)
set_loglevel(LOG.ALL, logging.DEBUG)


class AirplayGUI(QApplication):
    def __init__(self, *args, **kwargs):
        super(AirplayGUI, self).__init__(*args, **kwargs)

        self.setStyle("fusion")
        self.win = QMainWindow()

        # create an empty list for all airplay devices
        main = QWidget()

        boxlayout = QVBoxLayout()
        boxlayout.addStretch(1)

        self.list = QListView()
        self.list.setWindowTitle("Airplay devices")
        self.list.setMinimumSize(150, 100)

        boxlayout.addWidget(self.list)

        # create an empty model for the list's data and apply it
        self.model = QStandardItemModel(self.list)
        self.model.itemChanged.connect(self.checkStateChanged)
        self.list.setModel(self.model)

        bt_widget = QWidget()
        bt_container = QHBoxLayout()
        bt_container.addStretch(1)
        bt_widget.setLayout(bt_container)

        load_bt = QPushButton("load")
        play_bt = QPushButton("play")
        stop_bt = QPushButton("stop")

        load_bt.clicked.connect(self.load)
        play_bt.clicked.connect(self.toggle_play_pause)
        stop_bt.clicked.connect(self.stop)

        bt_container.addWidget(load_bt)
        bt_container.addWidget(play_bt)
        bt_container.addWidget(stop_bt)
        boxlayout.addWidget(bt_widget)

        # listen for new Airplay devices
        self.listener = RAOPServiceListener()
        self.listener.start_listening()
        self.listener.on_connect += self.connect_player
        self.listener.on_disconnect += self.disconnect_player

        # change the button text according to the current status
        self.raop_group = RAOPPlayGroup("default_group")
        self.raop_group.on_pause += lambda *args: play_bt.setText("play")
        self.raop_group.on_play += lambda *args: play_bt.setText("pause")
        self.raop_group.on_stop += lambda *args: play_bt.setText("play")

        self.music_file = None

        # show the list
        main.setLayout(boxlayout)
        self.win.setCentralWidget(main)
        self.win.show()

    def toggle_play_pause(self, *args):
        """
        Play or resume the stream depending on its status.
        """
        if self.raop_group.status == STATUS.PLAYING:
            self.raop_group.pause()
        elif self.raop_group.status == STATUS.PAUSED:
            self.raop_group.resume()
        elif self.raop_group.status == STATUS.STOPPED and self.music_file:
            self.raop_group.play(self.music_file)

    def stop(self, *args):
        """
        Stop the stream.
        """
        self.raop_group.stop()

    def load(self, *args):
        """
        Load a new file which should be streamed.
        """
        file_name, _ = QFileDialog.getOpenFileName(self.win, "QFileDialog.getOpenFileName()", "","All Files (*);;MP3 (*.mp3);; M4a (*.m4a);; WAW (*.waw);; PCM (*.pcm)")
        if file_name:
            # update the window title
            self.win.setWindowTitle(os.path.basename(file_name))

            # save the path to the selected music file
            self.music_file = file_name

            # add all currently selected players to the stream
            for i in range(self.model.rowCount()):
                item = self.model.item(i)
                if item.checkState() == Qt.Checked:
                    self.raop_group.add_receiver(item.player)

    def checkStateChanged(self, item):
        """
        Called when a listview item is checkd.
        :param item: checked listview item
        """
        # add a device to the current playback if it is checked
        if item.checkState() == Qt.Checked:
            self.raop_group.add_receiver(item.player)
        elif item.checkState() == Qt.Unchecked:
            self.raop_group.remove_receiver(item.player)

    def connect_player(self, player, name, info):
        """
        Called when a new airplay device gets connected.
        :param player: raop player instance
        :param name: service name
        :param info: additional device information
        """
        # try to extract name from server name
        item = QStandardItem(player.hostname)
        item.player = player
        item.setCheckable(True)
        self.model.appendRow(item)

    def disconnect_player(self, player, name, info):
        """
        Called when a new airplay device gets disconnected.
        :param player: raop player instance
        :param name: service name
        :param info: additional device information
        """
        for i in range(self.model.rowCount()):
            item = self.model.item(i)
            if item.player == player:
                # remove current player from stream
                self.raop_group.remove_receiver(item.player)
                # remove the entry
                self.model.removeRow(i)
                break


app = AirplayGUI(sys.argv)
app.exec_()
