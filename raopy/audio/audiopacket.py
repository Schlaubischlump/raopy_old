"""
Single audio packet to be send.
"""

from struct import pack
from array import array

from ..rtp import RtpHeader
from ..util import low16


class AudioPacket(object):
    __slots__ = ["alac_data", "rtp_header", "timestamp", "_data", "device_magic", "is_first"]

    def __init__(self, seq, alac_data, timestamp, device_magic, is_first=True):
        self.alac_data = alac_data
        self.is_first = is_first
        self.timestamp = timestamp
        self.device_magic = device_magic
        self.rtp_header = RtpHeader(a=0x80, b=(0xe0 if is_first else 0x60), seqnum=low16(seq))
        self._data = pack(">BBHII", self.rtp_header.a, self.rtp_header.b, self.rtp_header.seqnum, timestamp,
                          device_magic)
        self._data += array("B", alac_data).tobytes()

    def to_data(self):
        return self._data

    def __repr__(self):
        return "RTPHeader: {0}\ntimestamp: {1}\ndevice_magic: {2}\n".format(self.rtp_header, self.timestamp,
                                                                            self.device_magic)
