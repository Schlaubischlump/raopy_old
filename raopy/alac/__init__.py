"""
Load the C++ bindings for the ALACEncoder.
"""
from .libalac import ALACEncoder, encrypt_aes

__all__ = ["ALACEncoder", "encrypt_aes"]
