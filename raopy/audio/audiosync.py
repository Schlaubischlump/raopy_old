"""
Sync audio playback information across connected devices by sending the audio packets and inform the udp server to send
corresponding sync packets.
"""

from threading import Timer
from random import randint

from ..rtp import rtp_timestamp_for_seq
from ..rtsp import RAOPCrypto
from ..audio.audiopacket import AudioPacket
from ..alac import ALACEncoder, encrypt_aes
from ..config import SAMPLING_RATE, FRAMES_PER_PACKET, STREAM_LATENCY, SYNC_PERIOD, RAOP_FRAME_LATENCY, RAOP_LATENCY_MIN
from ..util import milliseconds_since_1970, EventHook, random_int

from .audiofile import AudioFile


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

    def __init__(self, udp_server, receivers):
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
        self.receivers = receivers
        self.udp_server = udp_server

        # set a random sequence number which is always greater then the smallest latency possible => next_seq >= 0
        self.start_seq = randint(self.sequence_latency, 0xffff)

        # a reference sequence number which indicates when the stream started / resumed playback
        self.ref_seq = self.start_seq

        # sequence number of next packet to send
        self.next_seq = self.ref_seq

        # set to the current milliseconds since 1970 each time the stream starts / resumes playback
        # this is needed to calculate the number of packets we need to send on a burst
        self.burst_time_ref = None

        # audio sync timer
        self.timer = None

        # device magic for audio packet
        self._device_magic = random_int(9)

        self.is_streaming = False

        # encoder instance for alac encoder
        self._encoder = ALACEncoder(frames_per_packet=FRAMES_PER_PACKET)

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
        return (RAOP_FRAME_LATENCY + RAOP_LATENCY_MIN) // FRAMES_PER_PACKET

    def send_packet(self, seq_num):
        """
        Send a packet over udp
        :param seq_num: sequence number
        """
        if not self.is_streaming or not self.audio_file:
            return False

        first_packet = (seq_num == self.ref_seq)

        # send a control packet every SYNC_PERIOD number of audio packets
        if (seq_num-self.ref_seq) % SYNC_PERIOD == 0:
            # inform all listener
            self.on_need_sync.fire(seq_num)
            # send the control sync
            self.udp_server.send_control_sync(self.receivers, seq_num, first_packet)

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
        for receiver in set(self.receivers):
            # use RSA encryption if the device supports it
            if receiver.encryption_type & RAOPCrypto.RSA:
                alac_data = encrypt_aes(alac_data)

            # create the audio packet and instruct each device to send it over its udp connection
            packet = AudioPacket(seq_num, alac_data, timestamp, self._device_magic, is_first=first_packet)
            receiver.send_audio_packet(packet)
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

    def start_streaming(self):
        """
        Start streaming the music file.
        """
        if self.is_streaming or not self.audio_file:
            return False

        self.is_streaming = True

        # update the last burst timestamp
        self.burst_time_ref = milliseconds_since_1970()

        # inform all listener
        self.on_stream_started.fire(self.current_seq_number)

        # start sending audio in a background thread
        self.timer = Timer(0, self.sync_audio)
        self.timer.start()

        return True

    def resume_streaming(self):
        """
        Resume the current stream.
        Start sending audio as if it was a new audio stream. This means the transmission will start with a SyncPacket
        marked as a "first" packet, and it will be followed by an Audio packet with the "first" marker too.
        """
        # set the reference sequence to the correct position
        tmp_ref_seq = self.ref_seq
        self.ref_seq = self.next_seq

        # rollback on error
        if not self.start_streaming():
            self.ref_seq = tmp_ref_seq
            return False

        return True

    def pause_streaming(self):
        """
        Pause the current stream.
        """
        if not self.is_streaming:
            return False

        self.is_streaming = False

        # cancel the next timer
        if self.timer:
            self.timer.cancel()
            self.timer = None

        # inform all listeners that the stream paused
        self.on_stream_paused.fire(self.current_seq_number - 1)

        # after we resume the stream with have to start ~2 seconds earlier
        self.next_seq -= self.sequence_latency

        return True

    def stop_streaming(self):
        """
        Stop streaming.
        """
        stop_seq = self.current_seq_number-1

        # pause the stream, this will reduce the current_seq_number by seq_latency
        if self.is_streaming:
            self.pause_streaming()

        # inform the listeners about the stop with the correct unmodified seq number
        self.on_stream_stopped.fire(stop_seq)

        self.audio_file = None

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

        # Send all packets up to the current one and increase the next sequence number thereby.
        for i in range(self.next_seq, current_seq):
            # interrupt streaming if the stream was paused or stopped or some other error occured
            if self.send_packet(i):
                self.next_seq += 1
            else:
                return

        # schedule next sync event
        self.timer = Timer(STREAM_LATENCY, self.sync_audio)
        self.timer.start()
