"""
Sync audio playback information across connected devices.
Available Events:
- on_need_sync(seq_num)
"""
from threading import Timer
from random import randint

from .audiofile import AudioFile

from ..rtsp import RAOPCrypto
from ..audio.audiopacket import AudioPacket
from ..alac import ALACEncoder, encrypt_aes
from ..config import SAMPLING_RATE, FRAMES_PER_PACKET, STREAM_LATENCY, SYNC_PERIOD
from ..util import milliseconds_since_1970, low32, EventHook, random_int


class AudioSync(object):

    def __init__(self):
        super(AudioSync, self).__init__()

        self.on_need_sync = EventHook()

        # current audio file
        self.audio_file = None

        self.devices = set()

        # last send sequence
        self.ref_seq = randint(0, 0xffff)
        self.last_seq = self.ref_seq

        # reference rtp time
        self.rtp_time_ref = None

        # audio sync timer
        self.timer = None

        # device magic for audio packet
        self._device_magic = random_int(9)

        self.is_streaming = False

        # is the next package to send the first one (Note: resume leads to a first package as well)
        self._is_first_package = True

        # encoder instance for alac encoder
        self._encoder = ALACEncoder(frames_per_packet=FRAMES_PER_PACKET)

    def send_packet(self, seq_num):
        """
        Send a packet over udp
        :param seq_num: sequence number
        :param use_backlog: look for the packet in the back_log (cache of all packets send in the last two seconds)
        """
        if not self.is_streaming or not self.audio_file:
            return

        rel_seq_num = seq_num - self.ref_seq
        if rel_seq_num % SYNC_PERIOD == 0:
            self.on_need_sync.fire(seq_num, self._is_first_package)

        # encode pcm raw data to alac data
        pcm_data = self.audio_file.get_frame(rel_seq_num)
        alac_data = self._encoder.encode_alac(pcm_data, sample_rate=SAMPLING_RATE)

        # packet timestamp
        timestamp = low32(seq_num*FRAMES_PER_PACKET + 2 * SAMPLING_RATE)

        # send the audio packet to each device
        for device in set(self.devices):
            # use RSA encryption if the device supports it
            if device.encryption_type & RAOPCrypto.RSA:
                alac_data = encrypt_aes(alac_data)

            # create the audio packet and instruct each device to send it over its udp connection
            packet = AudioPacket(seq_num, alac_data, timestamp, self._device_magic, is_first=self._is_first_package)
            device.send_audio_packet(packet)

        # toggle the the first package flag
        if self._is_first_package:
            self._is_first_package = False

    # region start/stop streaming
    def start_streaming(self, file_path):
        """
        Start streaming the music file at the given path.
        :param file_path: path to the audio file
        """
        if self.is_streaming:
            return False

        # create an audio file to read the pcm data
        self.audio_file = AudioFile(file_path)

        # store the reference rtp_time_ref
        self.rtp_time_ref = milliseconds_since_1970()

        # start the streaming process
        self.is_streaming = True

        # start sending audio in a background thread
        self.timer = Timer(0, self.sync_audio)
        self.timer.start()
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

        return True

    def resume_streaming(self):
        """
        Resume the current stream.
        Start sending audio as if it was a new audio stream. This means the transmission will start with a SyncPacket
        marked as a "first" packet, and it will be followed by an Audio packet with the "first" marker too.
        """
        if self.is_streaming:
            return False

        self.is_streaming = True

        # because the device buffer is lost we need to seek back two seconds
        packets_per_seconds = SAMPLING_RATE//FRAMES_PER_PACKET
        latency = 2*packets_per_seconds
        self.last_seq = max(self.last_seq-latency, self.ref_seq)

        # resume where we left off => add the time delta between pause and resume to the reference time
        # substract the latency SAMPLING_RATE*2
        elapsed = milliseconds_since_1970() - self.rtp_time_ref
        current_seq = self.ref_seq + int(elapsed * SAMPLING_RATE / (FRAMES_PER_PACKET * 1000))
        time_delta = int((current_seq-self.last_seq)*(FRAMES_PER_PACKET * 1000)/SAMPLING_RATE)
        self.rtp_time_ref += time_delta

        # start the stream
        self.timer = Timer(0, self.sync_audio)
        self.timer.start()

    def sync_audio(self):
        """
        Callback to repeatably send audio.
        """
        if not self.is_streaming:
            return

        # Each time sync_audio runs, a burst of packet is sent. Increasing config.stream_latency lowers CPU usage
        # but increases the size of the burst. If the burst size exceeds the UDP windows size (which we do not know),
        # packets are lost.
        elapsed = milliseconds_since_1970() - self.rtp_time_ref
        # current_seq is the number of the packet we should be sending now. We have some packets to catch-up since
        # sync_audio is not always running.
        current_seq = self.ref_seq+int(elapsed * SAMPLING_RATE / (FRAMES_PER_PACKET * 1000))
        #print("before: ", self.last_seq)

        for i in range(self.last_seq, current_seq):
            # interrupt streaming if the stream was paused or stopped
            if not self.is_streaming:
                return

            self.send_packet(i)

        self.last_seq = current_seq
        #print("after: ", self.last_seq)

        # schedule next sync event
        self.timer = Timer(STREAM_LATENCY, self.sync_audio)
        self.timer.start()
