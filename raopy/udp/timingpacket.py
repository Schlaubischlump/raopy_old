"""
Header send over upd.
For details see: https://git.zx2c4.com/Airtunes2/about/#replying-to-timing-packet
"""
from struct import unpack_from, pack
from ..rtp import RtpHeader
from ..util import NtpTime

TIMING_PACKET_SIZE = 32
TIMING_REQUEST_PAYLOAD = 0x52
TIMING_RESPONSE_PAYLOAD = 0x53


class TimingPacket(object):
    __slots__ = ["rtp_header", "zero_padding", "reference_time", "received_time", "send_time", "_data"]

    @classmethod
    def parse(cls, data):
        """
        Parse the raw data into a timing packet.
        :param data: raw data received from udp server
        :return: timing packet instance or None when an error occurs while parsing
        """
        try:
            # create timing packet
            timing_packet = cls()
            timing_packet.rtp_header = RtpHeader(*unpack_from(">BBH", data, 0))

            # malformed data
            if timing_packet.rtp_header.payload_type != TIMING_REQUEST_PAYLOAD:
                return None

            timing_packet.zero_padding = unpack_from(">I", data, 4)[0]
            timing_packet.reference_time = NtpTime(*unpack_from(">II", data, 8))
            timing_packet.received_time = NtpTime(*unpack_from(">II", data, 16))
            timing_packet.send_time = NtpTime(*unpack_from(">II", data, 24))
            timing_packet._data = data
            return timing_packet
        except:
            return None

    @classmethod
    def create(cls,
               rtp_header=RtpHeader(a=0x80, b=0xd3, seqnum=0x0007),
               zero_padding=0,
               reference_time=NtpTime(0, 0),
               received_time=NtpTime(0, 0),
               send_time=NtpTime(0, 0)):
        """
        Create a new timing packet with the given data
        :param rtp_header: rtp_header instance
        :param zero_padding: int padding
        :param reference_time: NtpTime instance
        :param received_time: NtpTime instance
        :param send_time: NtpTime instance
        :return:
        """
        try:
            ref_sec, ref_frac = reference_time
            rec_sec, rec_frac = received_time
            sen_sec, sen_frac = send_time
            data = pack(">BBHIIIIIII", rtp_header.a, rtp_header.b, rtp_header.seqnum, zero_padding,
                        ref_sec, ref_frac, rec_sec, rec_frac, sen_sec, sen_frac)
        except:
            return None

        timing_packet = cls()
        timing_packet._data = data
        timing_packet.rtp_header = rtp_header
        timing_packet.zero_padding = zero_padding
        timing_packet.reference_time = reference_time
        timing_packet.received_time = received_time
        timing_packet.send_time = send_time
        return timing_packet

    def __init__(self):
        """
        You should really not set these values by yourself.
        Just use create or parse depending on your use case.
        """
        self.rtp_header = None  # sizeof(uint32_t)
        self.zero_padding = 0  # uint32_t
        self.reference_time = None  # uint32_t, uint32_t
        self.received_time = None  # uint32_t, uint32_t
        self.send_time = None  # uint32_t, uint32_t
        self._data = b""

    def __repr__(self):
        return "RTPHeader: {0}\nzero_padding: {1}\nreference_time: {2}\nreceived_time: {3}\n" \
               "send_time: {4}\n".format(self.rtp_header, self.zero_padding, self.reference_time, self.received_time,
                                           self.send_time)

    def to_data(self):
        return self._data