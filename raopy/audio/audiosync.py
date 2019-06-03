"""
Sync audio playback information across connected devices by sending the audio packets and inform the udp server to send
corresponding sync packets.
"""
import socket
from threading import Timer, Lock, Event
from random import randint

from ..rtp import rtp_timestamp_for_seq
from ..rtsp import RAOPCrypto
from ..audio.audiopacket import AudioPacket
from ..alac import ALACEncoder, encrypt_aes
from ..config import SAMPLING_RATE, FRAMES_PER_PACKET, STREAM_LATENCY, SYNC_PERIOD, RAOP_FRAME_LATENCY, RAOP_LATENCY_MIN
from ..util import milliseconds_since_1970, EventHook, random_int

from .audiofile import AudioFile


SYNC_AUDIO_THREAD_NAME = "raopy-sync_audio-thread"


def seq_num_to_ms(seq_num):
    """
    Convert a sequence number to milliseconds.
    :param seq_num: sequence number to convert
    :return: milliseconds
    """
    return seq_num * (FRAMES_PER_PACKET * 1000) / SAMPLING_RATE


def ms_to_seq_num(millisec):
    """
    Convert milliseconds to a sequence number
    :param millisec: milliseconds
    :return: sequence number
    """
    return millisec * SAMPLING_RATE // (FRAMES_PER_PACKET * 1000)


class AudioSync(object):
    """
    Class which manages the sending of audio packets to all receivers and instructs the udp server to send a control
    packets roughly each second by sending the on_need_sync event.

    Available Events:
        - on_stream_started(seq_num)
        - on_need_sync(seq_num)
        - on_stream_paused(seq_num)
        - on_stream_ended(seq_num)
        - on_stream_stopped(seq_num)

    Note: All events run on the same thread from which they are called. The events on_need_sync and on_stream_stopped
    run from the same thread, that send the audio data. Do not perform compute heavy tasks on these callback functions!
    """

    def __init__(self, receivers):
        super(AudioSync, self).__init__()

        # optional events which can be used to observe the status of the audio
        self.on_need_sync = EventHook()
        self.on_stream_started = EventHook()
        self.on_stream_paused = EventHook()
        self.on_stream_ended = EventHook()
        self.on_stream_stopped = EventHook()

        # current audio file
        self.audio_file = None

        # save a reference (no copy!) to the devices and the udp sever
        self._receivers = receivers

        # set a random sequence number which is always greater then the smallest latency possible => next_seq >= 0
        self.start_seq = 0#randint(self.sequence_latency, 0xffff)

        # a reference sequence number which indicates when the stream started / resumed playback
        self.ref_seq = self.start_seq#-self.sequence_latency

        # sequence number of next packet to send
        self.next_seq = self.ref_seq

        # set to the current milliseconds since 1970 each time the stream starts / resumes playback
        # this is needed to calculate the number of packets we need to send on a burst
        self.burst_time_ref = None

        # audio sync timer
        self.timer = None

        # device magic for audio packet
        self._device_magic = random_int(9)

        # are we currently streaming music
        self.is_streaming = False

        # the main audio socket
        self._audio_socket = None

        # encoder instance for alac encoder
        self._encoder = ALACEncoder(frames_per_packet=FRAMES_PER_PACKET)

        # make accessing the next sequence number thread save
        self._next_seq_lock = Lock()

    # region open / close socket
    def open(self):
        """
        Open an audio udp socket.
        :return: True on success, False otherwise.
        """
        if not self._audio_socket:
            self._audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            return True
        return False

    def close(self):
        """
        Close the audio socket.
        :return: True on success, False otherwise.
        """
        if self.is_streaming:
            self.stop_streaming()

        if self._audio_socket:
            self._audio_socket.close()
            self._audio_socket = None
            return True
        return False

    # endregion

    # region properties
    @property
    def total_seq_number(self):
        """
        Get the absolute sequence number of the last frame of the audio file.
        Note: This might change when the stream is paused and resumed
        :return: last sequence number of the audio file
        """
        if not self.audio_file:
            return None

        num_frames = self.audio_file.total_frames
        return self.start_seq+num_frames-1

    @property
    def current_seq_number(self):
        """
        Get the sequence number of the next frame which should be played
        :return: current sequence number
        """
        with self._next_seq_lock:
            return self.next_seq

    @property
    def start_seq_number(self):
        """
        :return:
        """
        return self.start_seq

    @property
    def sequence_latency(self):
        """
        :return: latency in amount of sequences
        """
        return (RAOP_FRAME_LATENCY + RAOP_LATENCY_MIN) // FRAMES_PER_PACKET + 2
    # endregion

    def send_packet(self, seq_num, receivers=None, is_resend=False):
        """
        Send a packet over udp
        :param seq_num: sequence number
        :param receivers: list of receivers which should receiver this packet
        :param is_resend: True if we are resending a packet
        """
        if not self.is_streaming or not self.audio_file:
            return False

        # use all receivers as default
        if receivers is None:
            receivers = self._receivers

        first_packet = (seq_num == self.ref_seq)# + self.sequence_latency)

        # send a control packet every SYNC_PERIOD number of audio packets (except on a resend)
        if (seq_num-self.ref_seq) % SYNC_PERIOD == 0 and not is_resend:
            # inform all listener
            self.on_need_sync.fire(seq_num, set(receivers), is_first=first_packet)

        # calculate a relative sequence number between 0 and #(Frames in audio file)
        # this can be smaller than zero, e.g. if we pause on second 1 and subtract the latency of ~2 seconds
        relative_seq = self.next_seq - self.start_seq
        # encode pcm raw data to alac data
        pcm_data = self.audio_file.get_frame(relative_seq)

        # reached the end of the stream... we only support one track (at the moment) => close the connection
        if not pcm_data:
            self.on_stream_ended.fire(min(seq_num, self.total_seq_number))
            return False

        alac_data = self._encoder.encode_alac(pcm_data, sample_rate=SAMPLING_RATE)

        # packet rtp timestamp
        timestamp = rtp_timestamp_for_seq(seq_num)

        # send the audio packet to each device
        for receiver in set(receivers):
            # use RSA encryption if the device supports it
            if receiver.encryption_type & RAOPCrypto.RSA:
                alac_data = encrypt_aes(alac_data)

            # create the audio packet and instruct each device to send it over its udp connection
            packet = AudioPacket(seq_num, alac_data, timestamp, self._device_magic, is_first=first_packet)
            self._audio_socket.sendto(packet.to_data(), (receiver.ip, receiver.server_port))
            if is_resend:
                print("send audio packet: ", seq_num, " is_first: ", first_packet)

        return True

    # region start/stop streaming
    def load_audio(self, file_path):
        """
        Load an audio file.
        :param file_path: path to the audio file
        """
        # create an audio file to read the pcm data
        self.audio_file = AudioFile(file_path)

        # set the next audio packet sequence number to the start number
        self.next_seq = self.start_seq

    def start_streaming(self, seq=None):
        """
        Start streaming the music file at a specific sequence. Do not include the latency in this sequence number!
        :param seq: start playback at this sequence number
        """
        if self.is_streaming or not self.audio_file:
            return False

        self.is_streaming = True

        # set the correct start position
        if seq is None:
            seq = self.start_seq

        self.ref_seq = seq# - self.sequence_latency
        self.next_seq = self.ref_seq

        # update the last burst timestamp
        self.burst_time_ref = milliseconds_since_1970()

        # start sending audio in a background thread
        self.timer = Timer(0, self.sync_audio)
        self.timer.name = SYNC_AUDIO_THREAD_NAME
        self.timer.start()

        # inform all listener
        self.on_stream_started.fire(seq)

        return True

    def resume_streaming(self):
        """
        Resume the current stream.
        Start sending audio as if it was a new audio stream. This means the transmission will start with a SyncPacket
        marked as a "first" packet, and it will be followed by an Audio packet with the "first" marker too.
        """
        # set the reference sequence to the correct position
        return self.start_streaming(self.next_seq)

    def pause_streaming(self):
        """
        Pause the current stream.
        """
        if not self.is_streaming:
            return False

        self.is_streaming = False

        # cancel the timer
        if self.timer:
            self.timer.cancel()
            self.timer = None

        # inform all listeners that the stream paused
        # current_seq_number is thread safe, therefore the stream will be paused when we reach this part
        self.on_stream_paused.fire(self.current_seq_number)

        self.next_seq -= self.sequence_latency

        return True

    def stop_streaming(self):
        """
        Stop streaming.
        """
        # pause the stream, this will reduce the current_seq_number by seq_latency
        if self.is_streaming:
            self.pause_streaming()

        # inform the listeners about the stop with the correct unmodified seq number
        self.on_stream_stopped.fire(self.current_seq_number)

        self.audio_file = None

        # reset the playback progress and ref_seq
        self.next_seq = self.start_seq
        self.ref_seq = self.start_seq

        return True

    def set_progress(self, new_seq):
        """
        Set a new playback progress.
        :param new_seq: sequence number where we should start of at
        :return: True on success, False otherwise
        """
        if not self.audio_file or not self.start_seq <= new_seq <= self.total_seq_number:
            return False

        self.next_seq = new_seq

    def sync_audio(self):
        """
        Callback to repeatably send audio.
        """
        if not self.is_streaming:
            return

        # Each time sync_audio runs, a burst of packet is sent. Increasing config.stream_latency lowers CPU usage
        # but increases the size of the burst. If the burst size exceeds the UDP windows size packets are lost.
        # Each time the stream is paused and resume, we need to adjust the burst_time_ref, to guarantee that the right
        # amount of packets is send.
        elapsed = milliseconds_since_1970() - self.burst_time_ref
        # current_seq is the number of the packet we should be sending now. We have some packets to catch-up since
        # sync_audio is not always running. As the first packet send has the number self.ref_seq, we need to add the
        # delta value to this start value.
        current_seq = self.ref_seq + ms_to_seq_num(elapsed)

        # make sure that the next sequence number is updated before another thread can read it
        with self._next_seq_lock:
            # Send all packets up to the current one and increase the next sequence number thereby
            for i in range(self.next_seq, current_seq):
                    # interrupt streaming if the stream was paused or stopped or some other error occured
                    if self.send_packet(i):
                        self.next_seq += 1
                    else:
                        return

        # schedule next sync event
        self.timer = Timer(STREAM_LATENCY, self.sync_audio)
        self.timer.name = SYNC_AUDIO_THREAD_NAME
        self.timer.start()
