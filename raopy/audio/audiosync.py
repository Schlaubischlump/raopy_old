"""
Sync audio playback information across connected devices by sending the audio packets and inform the udp server to send
corresponding sync packets.

1.) Understanding the implementation
====================================

Audio packet (See: udp package controlpacket.py)
----------------------------------------------


Syn packet (See: udp package controlpacket.py)
----------------------------------------------
Sync packets are send roughly every second. This is guaranteed by sending one sync package after `SYNC_PERIOD`
(default: 126) many audio packets.

 (a) sampling rate / frames per packet (F) =  44100Hz / 352F = 125,28 F/s

Each sync packets includes a sequence number and an RTP time stamp. Those values determine which audio packet
should be played at which relative time. The RTP timestamp can be calculated by only knowing the sequence number.
The sync packets must contain the sequence number and RTP timestamp of the next audio packet to play. The timestamp
can be obtained by the formula:

 (b) sequence number * frames per packet + optional latency provided in RTSP header (See: rtp package `__init__.py`)


1.1) Start streaming (See: start_streaming / resume_streaming)
--------------------------------------------------------------
When the stream is started for the first time the initial audio packet will have a random sequence number assigned
to it (See: `ref_seq`). This sequence number will increase with each packet send (See: `next_seq). The
initial RTP timestamp is calculated by the formula described in (b). Resuming the stream will cause the next_seq to
be reset to the ref_seq. This will reset the RTP timestamp as well. In order to tell the airplay receiver about these
changed values, the flush rtsp request send on pause must include the RTP time stamp and sequence number of the next
audio packet send after the resume. One has to keep track of the amount of packets send between pause and resume to
calculate a relative sequence number which corresponds to the frame number in the actual audio file.
Therefore the following formula is used:

 (c) self.next_seq-self.ref_seq - latency

 (d) latency = (RAOP_FRAME_LATENCY + RAOP_LATENCY_MIN) // FRAMES_PER_PACKET

self.next_seq is not yet reset which means it points to the last packet which should be send next before pausing.
Subtracting the starting ref_seq will give us the amount of packets send up until the stream is paused. The airtunes
protocol includes a default latency of approximately 2 seconds, which has to be subtracted as well (ths effectively
rewinds the audio file by ~2seconds). The latency is calculated by two components. The RAOP_LATENCY_MIN, which seems
to be 11025 in all cases. More correctly this value should be received per raop receiver from the rtsp `Apple-Response`
header, but in this implementation it is hardcoded to 11025. The second component, the RAOP_FRAME_LATENCY corresponds
to 2*SAMPLING_RATE, which is effectively a two 2 seconds delay.
To start the actual music streaming the `sync_audio` function is called in a background thread, with a delay of 0
seconds.


1.2) Streaming process (See: sync_audio)
----------------------------------------
Audio packets are send in a burst each `STREAM_LATENCY` seconds. Each time the stream is started / resumed a reference
time the burst_time_ref is set to the current milliseconds since 1970. Using the formula:

 (e) milliseconds_since_1970() - self.burst_time_ref

the elapsed time since the last start / resume can be determined. The relative sequence number of the last packet which
should be send in this burst can be obtained by:

 (f) int(elapsed * SAMPLING_RATE / (FRAMES_PER_PACKET * 1000))

To transform this relative sequence number to the actual audio packets sequence number the `ref_seq` has to be added to
the calculated result. Now we can send the audio packets with the numbers `next_seq` up to the calculated value.
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


class AudioSync(object):
    """
    Class which manages the sending of audio packets to all receivers and instructs the udp server to send a control
    packets roughly each second by sending the on_need_sync event.

    Available Events:
        - on_need_sync(seq_num)
        - on_stream_ended()
    """

    def __init__(self):
        super(AudioSync, self).__init__()

        self.on_need_sync = EventHook()
        self.on_stream_ended = EventHook()

        # current audio file
        self.audio_file = None

        self.devices = set()

        # last send sequence
        self.ref_seq = randint(0, 0xffff)
        # sequence number of next packet to send
        self.next_seq = self.ref_seq
        # amount of packets send between last pause and resume minus the latency
        self.seq_offset = 0

        # reference rtp time
        # Note: the actual rtp timestamp is only based on the packets sequence number!
        self.burst_time_ref = None

        # audio sync timer
        self.timer = None

        # device magic for audio packet
        self._device_magic = random_int(9)

        self.is_streaming = False

        # encoder instance for alac encoder
        self._encoder = ALACEncoder(frames_per_packet=FRAMES_PER_PACKET)

    def send_packet(self, seq_num):
        """
        Send a packet over udp
        :param seq_num: sequence number
        :param seq_offset: amount of sequences to skip before the first frame
        """
        if not self.is_streaming or not self.audio_file:
            return

        first_package = (seq_num == self.ref_seq)

        # we need to get the relative sequence number
        if (seq_num-self.ref_seq) % SYNC_PERIOD == 0:
            self.on_need_sync.fire(seq_num, first_package)

        # calculate a relative sequence number between 0 and #(Frames in audio file)
        relative_seq = self.next_seq + self.seq_offset - self.ref_seq
        # encode pcm raw data to alac data
        pcm_data = self.audio_file.get_frame(relative_seq)

        # reached the end of the stream... we only support one track (at the moment) => close the connection
        if not pcm_data:
            self.on_stream_ended.fire()
            return

        alac_data = self._encoder.encode_alac(pcm_data, sample_rate=SAMPLING_RATE)

        # packet rtp timestamp
        timestamp = rtp_timestamp_for_seq(seq_num)

        # send the audio packet to each device
        for device in set(self.devices):
            # use RSA encryption if the device supports it
            if device.encryption_type & RAOPCrypto.RSA:
                alac_data = encrypt_aes(alac_data)

            # create the audio packet and instruct each device to send it over its udp connection
            packet = AudioPacket(seq_num, alac_data, timestamp, self._device_magic, is_first=first_package)
            device.send_audio_packet(packet)

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

        # this timestamp is required to calculate the amount of packets to send on a burst
        self.burst_time_ref = milliseconds_since_1970()
        # set the next audio packet sequence number to send
        self.next_seq = self.ref_seq

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

    def stop_streaming(self):
        """
        Stop streaming.
        """
        # Todo: is here anything more to do ?

        if self.is_streaming:
            self.pause_streaming()

        self.audio_file = None

    def resume_streaming(self):
        """
        Resume the current stream.
        Start sending audio as if it was a new audio stream. This means the transmission will start with a SyncPacket
        marked as a "first" packet, and it will be followed by an Audio packet with the "first" marker too.
        """
        if self.is_streaming:
            return False

        self.is_streaming = True

        # increase the sequence offset by the amount of packets send from the last pause to this resume + the number
        # of sequences required for the latency
        seq_latency = (RAOP_FRAME_LATENCY + RAOP_LATENCY_MIN) // FRAMES_PER_PACKET
        self.seq_offset += (self.next_seq-self.ref_seq-seq_latency)

        self.next_seq = self.ref_seq
        self.burst_time_ref = milliseconds_since_1970()

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
        # but increases the size of the burst. If the burst size exceeds the UDP windows size packets are lost.
        # Each time the stream is paused and resume, we need to adjust the burst_time_ref, to guarantee that the right
        # amount of packets is send.
        elapsed = milliseconds_since_1970() - self.burst_time_ref
        # current_seq is the number of the packet we should be sending now. We have some packets to catch-up since
        # sync_audio is not always running. As the first packet send has the number self.ref_seq, we need to add the
        # delta value to this start value.
        current_seq = self.ref_seq+int(elapsed * SAMPLING_RATE / (FRAMES_PER_PACKET * 1000))

        # Send all packets up to the current one and increase the next sequence number thereby.
        for i in range(self.next_seq, current_seq):
            # interrupt streaming if the stream was paused or stopped
            if not self.is_streaming:
                return

            self.send_packet(i)
            self.next_seq += 1

        # schedule next sync event
        self.timer = Timer(STREAM_LATENCY, self.sync_audio)
        self.timer.start()
