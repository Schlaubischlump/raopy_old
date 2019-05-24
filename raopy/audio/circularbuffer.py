"""
Buffer class which prefetches data from a pcm stream in a background thread. This class should be prevent a streaming
lags caused by disk IO.
Available Events:
- on_status_changed(new_status)
"""
from enum import Enum
from threading import Thread
from audiotools.pcmconverter import BufferedPCMReader

try:
    from Queue import Queue
except ImportError:
    from queue import Queue

from ..config import FRAMES_PER_PACKET
from ..util import EventHook


class BufferStatus(Enum):
    WAITING = 0
    BUFFERING = 1
    FULL = 2
    END = 3


class CircularBuffer(Thread):

    def __init__(self, pcm, packets_in_buffer):
        """
        :param pcm: PCM reader instance
        :param packets_in_buffer: maximum amount of packets in the buffer
        """
        Thread.__init__(self)

        self.on_status_changed = EventHook()

        # run this thread as daemon
        self.daemon = True

        # Todo use this: http://audiotools.sourceforge.net/programming/audiotools.html#audiotools.AudioFile to change sample_rate etc.
        # use BufferedPCMReader to read exactly FRAMES_PER_PACKET many frames, not more
        self.pcm = BufferedPCMReader(pcm)
        # this queue will block when maxsize is reached
        self.buf = Queue(maxsize=packets_in_buffer)
        # current status
        self.status = BufferStatus.WAITING

    def next_packet(self):
        """
        :return: next packet pcm data
        """
        return self.buf.get(block=True)

    def start_buffering(self):
        """
        Start filling the buffer.
        """
        self.start()
        self._dispatch_status()

    def stop_buffering(self):
        """
        Stop filling the buffer.
        """
        self.status = BufferStatus.END

    def _dispatch_status(self):
        """
        Dispatch the current status.
        """
        self.on_status_changed.fire(self.status)

    def run(self):
        """
        Fill the buffer.
        """
        # read the first frame
        frame_list = self.pcm.read(FRAMES_PER_PACKET)
        while frame_list.frames != 0 and self.status != BufferStatus.END:
            # if we are not currently buffering change the status
            if self.status != BufferStatus.BUFFERING:
                self.status = BufferStatus.BUFFERING
                self._dispatch_status()

            if self.buf.full():
                self.status = BufferStatus.FULL
                self._dispatch_status()

            # put items inside the queue as long as we still receive frames
            # this methods blocks if the queue contains packets_in_buffer many elements
            data = frame_list.to_bytes(False, True) # is_big_endian, is_signed
            self.buf.put(data, block=True)

            frame_list = self.pcm.read(FRAMES_PER_PACKET)

        # reached the end of the pcm stream
        self.status = BufferStatus.END
        self._dispatch_status()
