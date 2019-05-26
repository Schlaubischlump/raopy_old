from struct import unpack_from, pack

from ..rtp import RtpHeader
from ..util import NtpTime, low16

CONTROL_RANGE_RESEND = 0x55


class ResendPacket(object):
    __slots__ = ["rtp_header", "missed_seqnum", "count", "_data"]

    def __init__(self):
        self.rtp_header = None
        self.missed_seqnum = 0
        self.count = 0
        self._data = None

    @classmethod
    def parse(cls, data):
        """
        Parse the raw data into a timing packet.
        :param data: raw data received from udp server
        :return: timing packet instance or None when an error occurs while parsing
        """
        try:
            # create timing packet
            control_packet = cls()
            control_packet.rtp_header = RtpHeader(*unpack_from(">BBH", data, 0))

            # malformed data
            if control_packet.rtp_header.payload_type != CONTROL_RANGE_RESEND:
                return None

            control_packet.missed_seqnum = unpack_from(">H", data, 4)[0]
            control_packet.count = unpack_from(">H", data, 6)[0]
            control_packet._data = data
            return control_packet
        except Exception as e:
            return None

    def __repr__(self):
        return "RTPHeader: {0}\nmissed_seqnum: {1}\ncount: {2}\n".format(self.rtp_header, self.missed_seqnum,
                                                                         self.count)


class SyncPacket(object):

    __slots__ = ["rtp_header", "now_minus_latency", "time_last_sync", "now", "_data"]

    @classmethod
    def create(cls,
               now_minus_latency=0,  # current RTP timestamp (playback position)
               time_last_sync=NtpTime(0, 0),  # current time
               now=0, is_first=True):  # next packet RTP timestamp
        sync_packet = cls()

        rtp_header = RtpHeader(a=0x90 if is_first else 0x80, b=0xd4, seqnum=0x0007)

        sec, frac = time_last_sync
        try:
            data = pack(">BBHIIII", rtp_header.a, rtp_header.b, low16(rtp_header.seqnum), now_minus_latency, sec, frac,
                        now)
        except:
            return None

        sync_packet.rtp_header = rtp_header
        sync_packet.now_minus_latency = now_minus_latency
        sync_packet.time_last_sync = time_last_sync
        sync_packet.now = now
        sync_packet._data = data
        return sync_packet

    def __init__(self):
        self.rtp_header = None
        self.now_minus_latency = 0  # rtp timestamp
        self.time_last_sync = NtpTime(0, 0)
        self.now = 0  # rtp timestamp
        self._data = 0

    def to_data(self):
        return self._data

    def __repr__(self):
        return "RTPHeader: {0}\nnow_minus_latency: {1}\ntime_last_sync: {2}\nnow: {3}\n"\
            .format(self.rtp_header, self.now_minus_latency, self.time_last_sync, self.now, self.now)
