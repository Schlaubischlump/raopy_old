"""
Classes in this package are used to create audio packets which are then send by the AirTunesDevice.
Every 126 packets a "need_sync" event is dispatched to instruct the udp server to send a control packet.
"""

from .audiosync import AudioSync, ms_to_seq_num, seq_num_to_ms

__all__ = ["AudioSync", "ms_to_seq_num", "seq_num_to_ms"]