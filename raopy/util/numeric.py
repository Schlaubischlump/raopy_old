from os import urandom
from random import randint
from base64 import b64encode

from .helper import to_hex


def random_hex(n):
    """
    :param n: number of bytes
    :return: random bytes hex encoded
    """
    return to_hex(urandom(n)).upper()


def random_base64(n):
    """
    :param n: number of bytes
    :return: random bytes base64 encoded
    """
    return b64encode(urandom(n)).replace(b"=", b"")


def random_int(n):
    """
    :param n: max number
    :return: random int between 0 and n
    """
    return randint(10**(n-1), (10**n)-1)


def low16(i):
    """
    :param i: number
    :return: lower 16 bits of number
    """
    return i % 65536


def low32(i):
    """
    :param i: number
    :return: lower 16 bits of number
    """
    return i % 4294967296