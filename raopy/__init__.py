"""
For information about the protocol see:
- https://nto.github.io/AirPlay.html#servicediscovery-airplayservice (v1)
- https://git.zx2c4.com/Airtunes2/about/ (v2)
- https://web.archive.org/web/20120508065551/http://blog.technologeek.org/airtunes-v2 (v2)
"""

__version__ = "0.0.1"

from .raopservicelistener import RAOPServiceListener
from .airtunes import AirTunes
from .rtsp import RAOPCodec, RAOPCrypto

__all__ = ["RAOPServiceListener", "AirTunes", "__version__", "RAOPCodec", "RAOPCrypto"]