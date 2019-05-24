from __future__ import print_function

import socket
from logging import getLogger

from .rtsp import RTSPStatus, RTSPClient, RAOPCrypto, RAOPCodec
from .util import binary_ip_to_string

logger = getLogger("RAOPReceiverLogger")


class RAOPReceiver(object):
    def __init__(self, name, address, port, hostname="", crypto=RAOPCrypto.CLEAR, codecs=RAOPCodec.ALAC):
        """
        :param name: name of this service e.g 2E3AB0A4D0E9@ATV._raop._tcp.local.
        :param address: ip address of the airplay server
        :param port: port number of the service
        :param hostname: server hostname
        """
        self.name = name
        self.ip = binary_ip_to_string(address)  # server ip address
        self.port = port  # raop service port
        self.hostname = hostname

        # create a RTSP client to send the data to the host
        self._rtsp_client = RTSPClient(self.ip, self.port, crypto=crypto, codecs=codecs)

        # configure rtsp client and audio sender
        self._rtsp_client.volume = 50

        # listen for callback events from the RTSPClient
        self._rtsp_client.on_connection_ready += self.connection_ready
        self._rtsp_client.on_connection_closed += self.connection_closed

    def __str__(self):
        return "<{0}>: name={1}, address={2}:{3}, server={4}".format(self.__class__.__name__,
                                                                                     self.name,
                                                                                     self.ip, self.port,
                                                                                     self.hostname)

    def __repr__(self):
        return str(self)

    # region rstp client properties and callbacks
    @property
    def server_port(self):
        """
        :return: Server port to send audio packets to.
        """
        return self._rtsp_client.server_port

    @property
    def timing_port(self):
        """
        Todo: on Apple TV 4 and up this value is 0 ... why ?
        :return: timing port (not used)
        """
        return self._rtsp_client.timing_port

    @property
    def control_port(self):
        """
        :return: control port used to send control packets to.
        """
        return self._rtsp_client.control_port

    @property
    def encryption_type(self):
        """
        Note: The returned value is an integer. Use the RAOPCrypto enum to check which types are supported.
        Example: self.encryption_type & RAOPCrypto.RSA # check if RSA encryption is available
        :return: encryption type enum
        """
        return self._rtsp_client.crypto

    @property
    def codecs(self):
        """
        Note: The returned value is an integer. Use the RAOPCodec enum to check which types are supported.
        Example: self.codecs & RAOPCodec.ALAC # check if ALAC streaming is available
        :return: codec enum
        """
        return self._rtsp_client.codecs

    def connection_closed(self, reason):
        """
        Called when RTSP connection shut down.
        :param reason: Reason why the rtsp server shut down.
        """
        self.disconnect()

    def connection_ready(self):
        """
        Called when the RTSP connection is established.
        """
        pass
    # endregion

    # region establish/destroy a connection
    def request_pincode(self):
        """
        Show a pin code on the Apple TV (4 and up).
        """
        self._rtsp_client.request_pincode()

    def register(self, pin):
        """
        Register a new device on the Apple TV (4 and up) and return the credentials.
        You should save these credentials for the next time you try to connect to the device.
        """
        return self._rtsp_client.register_client(pin)

    def connect(self, udp_ports, last_seq, password=None, credentials=None):
        """
        Connect to the airplay receiver by performing an handshake
        :param udp control and timing port als tuple
        :param last_seq: last sequence number
        :param password: optional password required for the device
        :param credentials: credentials required for the device (Apple TV 4 and up only)
        """
        # socket required to send the audio packets to
        self._audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self._rtsp_client.start_handshake(udp_ports, last_seq, password, credentials)

    def repair_connection(self, last_seq):
        """
        Reopen the connection if it was closed for e.g. because of a teardown request.
        :param last_seq: last seq number
        """
        if self._rtsp_client.status == RTSPStatus.CLOSED:
            # repair the rtsp connection
            self._rtsp_client.repair_connection(last_seq)

            # recreat the audio socket
            if not self._audio_socket:
                self._audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def disconnect(self):
        """
        Close the connection to this Airtunes device.
        """
        # close RTSP connection
        self._rtsp_client.close()

        # close audio out connection
        if self._audio_socket:
            self._audio_socket.close()
            self._audio_socket = None

    def flush(self, last_seq):
        """
        Send a flush request.
        """
        self._rtsp_client.flush(last_seq)

    # endregion

    # region audio packet
    def send_audio_packet(self, packet):
        """
        Send audio data over UDP as RTP packet.
        :param packet: audio packet instance
        """
        # make sure the handshake is finished
        if not self.server_port:
            return

        self._audio_socket.sendto(packet.to_data(), (self.ip, self.server_port))
        logger.debug("Send audio packet:\n\033[91m%s\033[0m", packet)

    # endregion