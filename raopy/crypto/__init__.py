"""
Cryptographic functions required for authentication.
"""

from .srp import SRPAuthenticationHandler, new_credentials

__all__ = ["SRPAuthenticationHandler", "new_credentials"]