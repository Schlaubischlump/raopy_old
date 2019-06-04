import sys
import socket

IS_PY2 = sys.version_info.major <= 2


def to_bytes(s):
    """
    Convert a string to bytes.
    :param s: string
    :return: bytes of the string.
    """
    if IS_PY2:
        return str(s)

    if isinstance(s, bytes):
        return s
    return bytes(str(s), "UTF-8")


def binary_ip_to_string(ip):
    """
    :param ip: ip address as binary data
    :return: ip address as readable string
    """
    if IS_PY2:
        return ".".join([str(ord(x)) for x in ip])
    return ".".join([str(x) for x in ip])


def to_unicode(s):
    """
    Convert a string to unicode.
    :param s: string
    :return: string as unicode string
    """
    if IS_PY2:
        return s.decode("utf-8") if isinstance(s, str) else s
    return s if isinstance(s, str) else s.decode("utf-8")


def to_hex(s):
    """
    Convert a bytes object to hex.
    :param s: bytes object
    :return: bytes converted to hex
    """
    return s.encode('hex') if IS_PY2 else s.hex()


def get_ip_address():
    """
    Get current ip address
    :return: ip address of this device
    """
    host_name = socket.gethostname()
    return socket.gethostbyname(host_name)


def write_plist_to_bytes(dic):
    """
    :param dic: plist entries as dictionary
    :return: binary encoded plist
    """
    try:
        from plistlib import dumps, FMT_BINARY
        return dumps(dic, fmt=FMT_BINARY)
    except ImportError:
        from bplistlib import dumps
        return dumps(dic, binary=True)


def parse_plist_from_bytes(data):
    """
    Convert a binary encoded plist to a dictionary.
    :param data: plist data
    :return: dictionary
    """
    try:
        from plistlib import loads, FMT_BINARY
        return loads(data, fmt=FMT_BINARY)
    except ImportError:
        from bplistlib import loads
        return loads(data, binary=True)