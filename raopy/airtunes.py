"""
Main AirTunes class to register devices and start playback.
"""
from enum import Enum

from .udp import UDPServer
from .audio import AudioSync


class STATUS(Enum):
    PLAYING = 0
    PAUSED = 1
    STOPPED = 2


class AirTunes(object):

    def __init__(self):
        self._devices = set()
        self._audio_sync = AudioSync()
        self._udp_servers = UDPServer()

        # upd ports for timing and control information on this server
        # these ports are obviously the same for all clients
        self._udp_ports = self._udp_servers.control.port, self._udp_servers.timing.port

        # listen for sync callbacks
        self._audio_sync.on_need_sync += self.need_sync

        # current playback status
        self.status = STATUS.STOPPED

    # region audio sync callbacks
    def need_sync(self, last_seq, is_first):
        """
        Called whenever control packets to all clients should be send.
        :param last_seq: last sequence number
        :param is_first: is this package the first to send after play or resume
        """
        self._udp_servers.send_control_sync(last_seq, is_first)
    # endregion

    # region connect/disconnect
    def request_pincode_for_device(self, device):
        """
        Show a pin code dialog on the Apple TV for the given device
        :param device: device instance
        """
        device.request_pincode()

    def request_login_credentials_for_device_(self, device, pin):
        """
        Register a device on the new Apple TVs.
        :param device: device instance
        :return new login credentials
        """
        return device.register(pin)

    def connect_device(self, device, password=None, credentials=None):
        """
        Add an airplay device to the current playback session.
        :param device: AirTunesDevice instance
        :param password: optional password required for some devices
        :param credentials: optional credentials required for new devices
        :return: True on success, otherwise False
        """
        if device not in self._devices:
            # establish an rstp connection to the airplay device
            self._udp_servers.register_host(device)

            device.connect(self._udp_ports, self._audio_sync.last_seq, password, credentials)
            self._devices.add(device)
            self._audio_sync.devices.add(device)
            return True
        return False

    def disconnect_device(self, device):
        """
        Disconnect a device from the current playback session.
        :param device: AirTunesDevice instance
        :return: True on succes, otherwise False
        """
        if device in self._devices:
            self._devices.remove(device)
            self._udp_servers.unregister_host(device)
            self._audio_sync.devices.remove(device)

            # close connection to airplay device
            device.disconnect()
            return True
        return False

    # endregion

    # region metadata / control
    def play(self, music_file):
        """
        Load a music file and start the audio stream.
        :param music_file: path to music file
        :return: True on success, otherwise False
        """
        if not self.status == STATUS.STOPPED:
            return False

        self._audio_sync.start_streaming(music_file)
        self.status = STATUS.PLAYING
        return True

    def pause(self):
        """
        Pause the current playback.
        :return: True on success, otherwise False
        """
        if not self.status == STATUS.PLAYING:
            return False

        # send a flush request for each receiver over rtsp
        for receiver in self._devices:
            receiver.flush(self._audio_sync.last_seq)

        # stop sending audio and control packets
        self._audio_sync.pause_streaming()
        self.status = STATUS.PAUSED
        return True

    def resume(self):
        """
        Resume the current playback.
        :return: True on success, otherwise False
        """
        if not self.status == STATUS.PAUSED:
            return False

        # Fix the current connection if a teardown was sent in the meantime
        for receiver in self._devices:
            # We have to start over with the first seq number
            receiver.repair_connection(self._audio_sync.last_seq)

        self._audio_sync.resume_streaming()
        self.status = STATUS.PLAYING
        return True

    def stop(self):
        pass

    def set_artwork(self, artwork):
        pass

    def set_track_info(self, track_info):
        pass

    def set_volume(self, volume):
        pass
    # endregion
