from ..config import FRAMES_PER_PACKET, RAOP_FRAME_LATENCY
from ..util import low32
from .rtpheader import RtpHeader


def rtp_timestamp_for_seq(seq, include_latency=True):
    """
    Calculate the rtp timestamp for a given sequence number optionally including the latency
    :param seq: packet sequence number
    :param include_latency: True to include the latency, False otherwise
    :return: rtp timestamp for this packet
    """
    if include_latency:
        return low32(seq * FRAMES_PER_PACKET + RAOP_FRAME_LATENCY)
    return low32(seq * FRAMES_PER_PACKET)


__all__ = ["RtpHeader", "rtp_timestamp_for_seq"]