"""
Main RAOPPlayGroup class to register receivers and start playback.
"""
from enum import Enum
from functools import partial
from logging import getLogger

from .util import EventHook
from .udp import UDPServer
from .exceptions import PlayGroupClosedError
from .audio import AudioSync, ms_to_seq_num, seq_num_to_ms


group_logger = getLogger("RAOPPlaybackGroupLogger")


class STATUS(Enum):
    PLAYING = 0
    PAUSED = 1
    STOPPED = 2
    CLOSED = 3


def is_alive(func):
    """
    Decorator function which grantees that the RAOPPlayGroup is still alive, meaning the connection is not closed.
    :param func:
    :param throw_exception:
    :return:
    """
    def func_wrapper(self, *args):
        if self.status == STATUS.CLOSED:
            raise PlayGroupClosedError("{0} is already closed. Create a new group.".format(self))
        return func(self, *args)
    return func_wrapper


class RAOPPlayGroup(object):
    """
    Group multiple RAOPReceivers to send the same synchronised audio to them.
    Available Events:
        - on_play(start_time)
        - on_pause(pause_time)
        - on_stop(stop_time)
        - on_progress(new_time)

    Note: These events are not guaranteed to run on the main thread.
    """

    def __init__(self, name=None):
        """
        :param name: name of this playgroup used for debugging
        """
        self.name = name or str(id(self))

        # all raop receivers
        self._receivers = set()
        # the udp server for timing and control packets for all devices
        self._udp_server = UDPServer()

        # audio sync needs a reference to all devices to send the audio packets and to the udp server for sync packets
        self._audio_sync = AudioSync(udp_server=self._udp_server, receivers=self._receivers)

        # upd ports for timing and control information on this server
        # these ports are obviously the same for all clients
        self._udp_ports = self._udp_server.control.port, self._udp_server.timing.port

        # current playback status
        self.status = STATUS.STOPPED

        # listen for sync callbacks
        self._audio_sync.on_stream_ended += lambda *args: self.stop()

        # add logging for the basic stream events
        self._audio_sync.on_need_sync += partial(self._log_event, "on_need_sync")
        self._audio_sync.on_stream_started += partial(self._log_event, "on_stream_started")
        self._audio_sync.on_stream_paused += partial(self._log_event, "on_stream_paused")
        self._audio_sync.on_stream_ended += partial(self._log_event, "on_stream_ended")
        self._audio_sync.on_stream_stopped += partial(self._log_event, "on_stream_stopped")

        # create events for the user to use
        self.on_play = EventHook()
        self.on_pause = EventHook()
        self.on_stop = EventHook()
        self.on_progress = EventHook()

    def __str__(self):
        return "{0}<{1}>".format(self.__class__.__name__, self.name)

    def _log_event(self, event_name, seq_num):
        """
        :param event_name: name of the received event
        :param seq_num: sequence number provided by the name
        """
        group_logger.info("%s received event: %s at sequence: %s", str(self), event_name, str(seq_num))

    # region connect / disconnect
    @is_alive
    def request_pincode_for_device(self, device):
        """
        Show a pin code dialog on the Apple TV for the given device
        :param device: device instance
        """
        device.request_pincode()

    @is_alive
    def request_login_credentials_for_device_(self, device, pin):
        """
        Register a device on the new Apple TVs.
        :param device: device instance
        :return new login credentials
        """
        return device.register(pin)

    @is_alive
    def add_receiver(self, recv, password=None, credentials=None):
        """
        Add an airplay device to the current playback session.
        :param device: RaopReceiver instance
        :param password: optional password required for some devices
        :param credentials: optional credentials required for new devices
        :return: True on success, otherwise False
        """
        if recv not in self._receivers:
            # if we are already playing the device should automatically start with the playback
            # Todo: maybe it would be better to just send an OPTION request twice to check if the device is
            #  password protected or needs credentials instead of a handshake
            recv.connect(self._udp_ports, self._audio_sync.next_seq, password, credentials)
            self._receivers.add(recv)

            return True
        return False

    @is_alive
    def remove_receiver(self, recv):
        """
        Disconnect a device from the current playback session.
        :param device: RaopReceiver instance
        :return: True on succes, otherwise False
        """
        if recv in self._receivers:
            self._receivers.remove(recv)
            # close connection to airplay device
            recv.disconnect()
            return True
        return False

    # endregion

    # region control playback
    @is_alive
    def play_resume(self, music_file=None):
        """
        Start or resume the playback.
        :param music_file: if we start the playback we should provide the path to a music file.
        :return: True on success, False otherwise
        """
        # load the music file if we start the stream
        if self.status == STATUS.STOPPED and music_file:
            self._audio_sync.load_audio(music_file)
        elif self.status == STATUS.PAUSED:
            pass
        else:
            return False

        # sequence numbers to send the progress
        start = self._audio_sync.start_seq
        cur = self._audio_sync.current_seq_number
        end = self._audio_sync.total_seq_number

        # if we wait to long between connect and play or pause and resume the RTSP connection might be shut down
        # => establish an new RTSP connection to the airplay receiver
        for recv in self._receivers:
            recv.repair_connection(cur)
            # send the current progress
            recv.set_progress(start, cur, end)

        # start streaming the audio
        if self.status == STATUS.STOPPED:
            if not music_file:
                return False
            self._audio_sync.load_audio(music_file)
            self._audio_sync.start_streaming()
        elif self.status == STATUS.PAUSED:
            self._audio_sync.resume_streaming()

        self.status = STATUS.PLAYING

        self.on_play.fire(seq_num_to_ms(cur))

        return True

    def play(self, music_file):
        """
        Load a music file and start the audio stream.
        :param music_file: path to music file
        :return: True on success, otherwise False
        """
        if not self.status == STATUS.STOPPED:
            return False

        return self.play_resume(music_file)

    def resume(self):
        """
        Resume the current playback.
        :return: True on success, otherwise False
        """
        if not self.status == STATUS.PAUSED:
            return False

        return self.play_resume()

    @is_alive
    def pause(self):
        """
        Pause the current playback.
        :return: True on success, otherwise False
        """
        if not self.status == STATUS.PLAYING:
            return False

        # stop sending audio and control packets
        self._audio_sync.pause_streaming()

        cur_seq = self._audio_sync.current_seq_number

        # send a flush request for each receiver over rtsp
        for receiver in self._receivers:
            receiver.flush(cur_seq)

        self.status = STATUS.PAUSED

        # inform the user that the stream stopped
        cur = cur_seq + self._audio_sync.sequence_latency - 1
        self.on_pause.fire(seq_num_to_ms(cur))

        return True

    @is_alive
    def stop(self):
        """
        Stop the current playback on all devices.
        :return:
        """
        if self.status == STATUS.STOPPED:
            return False

        # stop streaming
        self._audio_sync.stop_streaming()

        # disconnect the RTSP connection
        for receiver in self._receivers:
            receiver.disconnect()

        self.status = STATUS.STOPPED

        cur = self._audio_sync.current_seq_number + self._audio_sync.sequence_latency - 1
        self.on_stop.fire(seq_num_to_ms(cur))

    @is_alive
    def close(self):
        """
        Close the connection. The playgroup is useless after closing it.
        """
        if self.status != STATUS.STOPPED:
            self.stop()

        # close the udp sockets
        self._udp_server.close()

        self.status = STATUS.CLOSED
    # endregion

    # region metadata
    @is_alive
    def set_progress(self, cur_time):
        """
        :param cur_time: time in milliseconds to which we should skip
        :return: True on success, False otherwise
        """
        if self.status == STATUS.STOPPED:
            return False

        # we can only set the progress if the stream is paused
        if self.status == STATUS.PLAYING:
            return False

        # get the start, new current and end sequence number
        start = self._audio_sync.start_seq
        end = self._audio_sync.total_seq_number
        cur = start + ms_to_seq_num(cur_time)

        if not start <= cur <= end:
            raise ValueError("Current time must be between start and end time.")

        # Send an RTSP Request to all devices to change the playback position
        for recv in self._receivers:
            recv.set_progress(start, cur, end)

        # inform all listener
        prg_res = self._audio_sync.set_progress(cur)
        if prg_res:
            self.on_progress.fire(seq_num_to_ms(cur))

        return prg_res

    @is_alive
    def set_artwork(self, artwork):
        pass

    @is_alive
    def set_track_info(self, track_info):
        pass

    @is_alive
    def set_volume(self, volume):
        pass
    # endregion
