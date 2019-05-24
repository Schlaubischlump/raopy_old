# RTP header bits
RTP_HEADER_A_EXTENSION = 0x10
RTP_HEADER_A_SOURCE = 0x0f
RTP_HEADER_B_PAYLOAD_TYPE = 0x7f
RTP_HEADER_B_MARKER = 0x80


class RtpHeader(object):
    """
    RTP Header.
    """
    __slots__ = ["a", "b", "seqnum"]

    def __init__(self, a, b, seqnum):
        self.a = a # uint8_t
        self.b = b # uint8_t
        self.seqnum = seqnum # uint16_t

    @property
    def extension(self):
        return bool(self.a & RTP_HEADER_A_EXTENSION)

    @property
    def source(self):
        return self.a & RTP_HEADER_A_SOURCE

    @property
    def payload_type(self):
        return self.b & RTP_HEADER_B_PAYLOAD_TYPE

    @property
    def marker(self):
        return bool(self.b & RTP_HEADER_B_MARKER)

    def __repr__(self):
        return "RTPHeader ({0}): a={1} b={2} seqnum={3}".format(hex(self.payload_type), self.a, self.b, self.seqnum)