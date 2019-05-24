"""
Sync audio playback information across connected devices.
Available Events:
- on_need_sync(seq_num)
"""
from threading import Timer

import audiotools

from ..rtsp import RAOPCrypto
from ..audio.audiopacket import AudioPacket
from ..audio.circularbuffer import CircularBuffer, BufferStatus
from ..alac import ALACEncoder, encrypt_aes
from ..config import SAMPLING_RATE, FRAMES_PER_PACKET, STREAM_LATENCY, SYNC_PERIOD, REF_SEQ
from ..util import milliseconds_since_1970, low32, EventHook


class AudioSync(object):

    def __init__(self):
        super(AudioSync, self).__init__()

        self.on_need_sync = EventHook()

        self.devices = set()

        # last send sequence
        self.last_seq = REF_SEQ
        self.rtp_time_ref = milliseconds_since_1970()

        # audio sync timer
        self.timer = None

        # buffer for audio data
        self.buffer = None
        self.is_streaming = False
        # This flag prevents the playback if the buffer is not full, the stream is paused and a callback is
        # send that the buffer status changed.
        self.is_paused = False

        # encoder instance for alac encoder
        self._encoder = ALACEncoder(frames_per_packet=FRAMES_PER_PACKET)

    def send_packet(self, seq_num):
        """
        Send a packet over udp
        :param seq_num: sequence number
        """
        if not self.is_streaming:
            return

        rel_seq = (seq_num - REF_SEQ)
        if rel_seq % SYNC_PERIOD == 0:
            self.on_need_sync.fire(seq_num)

        if self.is_paused:
            return

        # encode pcm raw data to alac data
        pcm_data = self.buffer.next_packet()
        alac_data = self._encoder.encode_alac(pcm_data, sample_rate=SAMPLING_RATE)

        # packet timestamp
        timestamp = low32(seq_num*FRAMES_PER_PACKET + 2 * SAMPLING_RATE)

        # send the audio packet to each device
        for device in set(self.devices):
            # use RSA encryption if the device supports it
            if device.encryption_type & RAOPCrypto.RSA:
                alac_data = encrypt_aes(alac_data)

            # create the audio packet and instruct each device to send it over its udp connection
            packet = AudioPacket(seq_num, alac_data, timestamp, is_first=(rel_seq == 0))
            device.send_audio_packet(packet)

    # region start/stop streaming
    def start_streaming(self, audio_file):
        """
        Create the buffer and fill it with 100 packets.
        :param audio_file: path to audio file
        """
        # create buffer for pcm data
        pcm = audiotools.open(audio_file).to_pcm()
        #import audioread
        #pcm = audioread.audio_open(audio_file)
        self.buffer = CircularBuffer(pcm, 20)
        self.buffer.on_status_changed += self.status_changed
        self.buffer.start_buffering()

    def pause_streaming(self):
        """
        Pause the current stream.
        """
        self.is_paused = True
        #self.is_streaming = False

    def resume_streaming(self):
        """
        Resume the current stream.
        Start sending audio as if it was a new audio stream. This means the transmission will start with a SyncPacket
        marked as a "first" packet, and it will be followed by an Audio packet with the "first" marker too.
        """
        self.is_paused = False
        #self.is_streaming = True
        #
        self.last_seq = REF_SEQ

        # restart the streaming if the status is already BufferStatus.FULL, otherwise the streaming will resume
        # automatically
        #if self.buffer.status == BufferStatus.FULL:
        #    self.sync_audio()

    def close(self):
        """
        Cleanup the buffer.
        """
        self.is_streaming = False

        if self.buffer:
            self.buffer.stop_buffering()
            self.buffer.on_status_changed -= self.status_changed

        if self.timer:
            self.timer.cancel()
            self.timer = None

    def sync_audio(self):
        """
        :return:
        """
        if not self.is_streaming:
            return

        # Each time sync_audio runs, a burst of packet is sent. Increasing config.stream_latency lowers CPU usage
        # but increases the size of the burst. If the burst size exceeds the UDP windows size (which we do not know),
        # packets are lost.
        elapsed = milliseconds_since_1970() - self.rtp_time_ref
        # current_seq is the number of the packet we should be sending now. We have some packets to catch-up since
        # sync_audio is not always running.
        current_seq = REF_SEQ+int(elapsed * SAMPLING_RATE / (FRAMES_PER_PACKET * 1000))

        for i in range(self.last_seq, current_seq):
            self.send_packet(i)

        self.last_seq = current_seq

        # schedule next sync event
        self.timer = Timer(STREAM_LATENCY, self.sync_audio)
        self.timer.start()

    # region Buffer callbacks
    def status_changed(self, status):
        """
        Called when the buffer status changed.
        :param status: new buffer status
        """
        if self.is_paused:
            return

        # preload finished => start playback
        if status == BufferStatus.FULL and not self.is_streaming:
            self.is_streaming = True
            # start playback in a background thread, because otherwise put and get will block at the same time
            # as they are both called from the CircularBuffer-Thread, because the dispatch method does not
            # dispatch to the main thread
            self.rtp_time_ref = milliseconds_since_1970()

            # send first audio sync to start playback
            self.timer = Timer(0, self.sync_audio)
            self.timer.start()

        # stream ended => remove the buffer listener
        if status == BufferStatus.END:
            self.close()
    # endregion
