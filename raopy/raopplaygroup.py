"""
Main RAOPPlayGroup class to register receivers and start playback.
"""
from enum import Enum

from .udp import UDPServer
from .audio import AudioSync


class STATUS(Enum):
    PLAYING = 0
    PAUSED = 1
    STOPPED = 2


class RAOPPlayGroup(object):

    def __init__(self):
        # all raop receivers
        self._receivers = set()


        self._udp_server = UDPServer()

        # audio sync needs a reference to all devices to send the audio packets and to the udp server for sync packets
        self._audio_sync = AudioSync(udp_server=self._udp_server, receivers=self._receivers)

        # upd ports for timing and control information on this server
        # these ports are obviously the same for all clients
        self._udp_ports = self._udp_server.control.port, self._udp_server.timing.port

        # current playback status
        self.status = STATUS.STOPPED

        # listen for sync callbacks
        self._audio_sync.on_need_sync += self.need_sync
        self._audio_sync.on_stream_ended += self.stop


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
        :param device: RaopReceiver instance
        :param password: optional password required for some devices
        :param credentials: optional credentials required for new devices
        :return: True on success, otherwise False
        """
        if device not in self._receivers:
            # establish an rstp connection to the airplay device
            device.connect(self._udp_ports, self._audio_sync.next_seq, password, credentials)
            self._receivers.add(device)
            self._audio_sync.devices.add(device)
            return True
        return False

    def disconnect_device(self, device):
        """
        Disconnect a device from the current playback session.
        :param device: RaopReceiver instance
        :return: True on succes, otherwise False
        """
        if device in self._receivers:
            self._receivers.remove(device)
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

        # stop sending audio and control packets
        self._audio_sync.pause_streaming()

        # send a flush request for each receiver over rtsp
        for receiver in self._receivers:
            receiver.flush(self._audio_sync.current_seq_number)

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
        for receiver in self._receivers:
            # We have to start over with the first seq number
            receiver.repair_connection(self._audio_sync.current_seq_number)

        self._audio_sync.resume_streaming()
        self.status = STATUS.PLAYING
        return True

    def stop(self):
        """
        Stop the current playback on all devices.
        :return:
        """
        if self.status == STATUS.STOPPED:
            return False

        # stop streaming
        self._audio_sync.stop_streaming()

        # disconnect the rtsp connection
        for receiver in self._receivers:
            receiver.disconnect()

    def set_artwork(self, artwork):
        pass

    def set_track_info(self, track_info):
        pass

    def set_volume(self, volume):
        pass
    # endregion
