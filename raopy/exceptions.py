"""
All possible exceptions.
"""


class BadResponseError(Exception):
    """
    Thrown when an unknown HTTP error occurs.
    """
    pass


class NotEnoughBandwidthError(Exception):
    """
    Thrown when the corresponding HTTP error occurs.
    """
    pass


class DeviceAuthenticationError(Exception):
    """
    Thrown in the >= 10.2 authentication process for various errors.
    """
    pass


class DeviceAuthenticationPairingError(Exception):
    """
    Thrown in the >= 10.2 authentication process, if no pin code can be requested.
    """
    pass


class DeviceAuthenticationWrongPasswordError(Exception):
    """
    Thrown during the handshake if the wrong password was entered.
    """
    pass


class DeviceAuthenticationWrongPinCodeError(Exception):
    """
    Thrown in the >= 10.2 authentication process, if the wrong pin code was entered.
    """
    pass


class DeviceAuthenticationRequiresPinCodeError(Exception):
    """
    Thrown in the >= 10.2 authentication process, if the a pin code is required to connect.
    """
    pass


class DeviceAuthenticationRequiresPasswordError(Exception):
    """
    Thrown when an airplay receiver requires a password.
    """
    pass


class NoCredentialsError(Exception):
    """
    Thrown in the >= 10.2 authentication process, if no credentials are loaded.
    """
    pass


class HandshakeNotFinishedError(Exception):
    """
    Thrown during the handshake is not yet finished, but the audio sender is instructed to send data.
    """
    pass


class MissingServerPortError(Exception):
    """
    Thrown when the audio senders destination port is not set, but a packet should be sent.
    """
    pass


class MissingNtpReferenceTime(Exception):
    """
    Thrown when no refrence time for the NTP timestamp was set.
    """
    pass


class UnsupportedCryptoError(Exception):
    """
    Thrown when an unsupported encryption type (not CLEAR or RSA) is specified.
    """
    pass


class UnsupportedCodecError(Exception):
    """
    Thrown when an unsupported codec type is specified.
    """
    pass


class UnsupportedFileType(Exception):
    """
    Thrown when the given file type is not supported.
    """
    pass


class RTSPClientAlreadyConnected(Exception):
    """
    Thrown when a new RTSP connection should be established, but the old one is still active.
    """
    pass