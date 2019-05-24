"""
Special thanks to pyatv for this python implementation!
Routines used for the authentication with an Apple TV which runs TVOS 10.2 or higher.
See: https://htmlpreview.github.io/?https://github.com/philippe44/RAOP-Player/blob/master/doc/auth_protocol.html for
an in depth explanation of the different procedures.
"""
import hashlib
import binascii

import curve25519
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, modes, algorithms
from srptools import SRPContext, constants, SRPClientSession
from ed25519.keys import SigningKey

from ..util import random_hex
from ..exceptions import NoCredentialsError, DeviceAuthenticationError


# region helper methods

def hash_sha512(*indata):
    """Create SHA512 hash for input arguments."""
    hasher = hashlib.sha512()
    for data in indata:
        if isinstance(data, str):
            hasher.update(data.encode('utf-8'))
        elif isinstance(data, bytes):
            hasher.update(data)
        else:
            raise Exception('invalid input data: ' + str(data))
    return hasher.digest()


def aes_encrypt(mode, aes_key, aes_iv, *data):
    """
    Encrypt data with AES in specified mode.
    :param aes_key: aes_key to use
    :param aes_iv: initialization vector
    """
    encryptor = Cipher(algorithms.AES(aes_key), mode(aes_iv), backend=default_backend()).encryptor()

    result = None
    for value in data:
        result = encryptor.update(value)
    encryptor.finalize()

    return result, None if not hasattr(encryptor, 'tag') else encryptor.tag


def new_credentials():
    """Generate a new identifier and seed for authentication.

    Use the returned values in the following way:
    * The identifier shall be passed as username to SRPAuthenticationHandler.step1
    * Seed shall be passed to SRPAuthenticationHandler constructor
    :return identifier, seed
    """
    identifier = random_hex(8)
    seed = random_hex(32)  # Corresponds to private key
    return identifier, seed

# endregion


class AtvSRPContext(SRPContext):
    """Custom context implementation for Apple TV."""

    def get_common_session_key(self, premaster_secret):
        """K = H(S).
        Special implementation for Apple TV.
        """
        k_1 = self.hash(premaster_secret, b'\x00\x00\x00\x00', as_bytes=True)
        k_2 = self.hash(premaster_secret, b'\x00\x00\x00\x01', as_bytes=True)
        return k_1 + k_2


def requires_credentials(func):
    """
    Decorator function which makes sure, that the credentials are loaded before executing the function.
    """
    def func_wrapper(self, *args):
        if not self.seed:
            raise NoCredentialsError()
        return func(self, *args)
    return func_wrapper


class SRPAuthenticationHandler(object):
    """
    Handle SRP (Secure Remote Password) data and crypto routines for auth and verification.
    """

    def __init__(self):
        self.seed = None
        self.session = None
        self._auth_private = None
        self._auth_public = None
        self._verify_private = None
        self._verify_public = None
        self.client_session_key = None

    def initialize(self, seed):
        """
        This method will generate new encryption keys and must be called prior to doing authentication or verification.
        :param seed: seed used for generation or key
        """
        self.seed = binascii.unhexlify(seed)
        signing_key = SigningKey(self.seed)
        verifying_key = signing_key.get_verifying_key()
        self._auth_private = signing_key.to_seed()
        self._auth_public = verifying_key.to_bytes()

    # region pairing

    @requires_credentials
    def step1(self, username, password):
        """
        First authentication step.
        :param username: username
        :param password: password
        """
        context = AtvSRPContext(str(username),
                                str(password),
                                prime=constants.PRIME_2048,
                                generator=constants.PRIME_2048_GEN)
        self.session = SRPClientSession(context, binascii.hexlify(self._auth_private).decode())

    @requires_credentials
    def step2(self, pub_key, salt):
        """
        Second authentication step. (Run SRP)
        :param pub_key: Apple TVs public key
        :param salt: Apple TVs salt
        """
        pk_str = binascii.hexlify(pub_key).decode()
        salt = binascii.hexlify(salt).decode()

        self.client_session_key, _, _ = self.session.process(pk_str, salt)

        # Generate client public and session key proof.
        client_public = self.session.public
        client_session_key_proof = self.session.key_proof

        if not self.session.verify_proof(self.session.key_proof_hash):
            raise DeviceAuthenticationError('proofs do not match (mitm?)')
        return binascii.unhexlify(client_public), binascii.unhexlify(client_session_key_proof)

    @requires_credentials
    def step3(self):
        """
        Last authentication step. (Run AES)
        :return epk, tag
        """
        session_key = binascii.unhexlify(self.client_session_key)

        aes_key = hash_sha512('Pair-Setup-AES-Key', session_key)[0:16]
        tmp = bytearray(hash_sha512('Pair-Setup-AES-IV', session_key)[0:16])
        tmp[-1] += + 1  # Last byte must be increased by 1
        aes_iv = bytes(tmp)

        return aes_encrypt(modes.GCM, aes_key, aes_iv, self._auth_public)

    # endregion

    # region verification steps

    @requires_credentials
    def verify1(self):
        """
        First device verification step.
        """
        self._verify_private = curve25519.Private(secret=self.seed)
        self._verify_public = self._verify_private.get_public()
        verify_public = self._verify_public.serialize()
        return b'\x01\x00\x00\x00' + verify_public + self._auth_public

    @requires_credentials
    def verify2(self, atv_public_key, data):
        """
        Last device verification step.
        """
        # Generate a shared secret key
        public = curve25519.Public(atv_public_key)
        shared = self._verify_private.get_shared_key(public, hashfunc=lambda x: x)  # No additional hashing used

        # Derive new AES key and IV from shared key
        aes_key = hash_sha512('Pair-Verify-AES-Key', shared)[0:16]
        aes_iv = hash_sha512('Pair-Verify-AES-IV', shared)[0:16]

        # Sign public keys and encrypt with AES
        signer = SigningKey(self._auth_private)
        signed = signer.sign(self._verify_public.serialize() + atv_public_key)
        signature, _ = aes_encrypt(modes.CTR, aes_key, aes_iv, data, signed)

        # Signature is prepended with 0x00000000 (alignment?)
        return b'\x00\x00\x00\x00' + signature

    # endregion