from logging import getLogger

from .rtp import rtp_timestamp_for_seq
from .rtsp import RTSPReason, DmapList, DmapItem
from .exceptions import RTSPClientAlreadyConnected
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

        # True if the RTSP connection is established, False otherwise
        self._rtsp_is_connected = False

        # listen for callback events from the RTSPClient
        self._rtsp_client.on_connection_ready += self.connection_ready
        self._rtsp_client.on_connection_closed += self.connection_closed

    def __str__(self):
        return "<{0}>: name={1}, address={2}:{3}, server={4}".format(self.__class__.__name__, self.name, self.ip,
                                                                     self.port, self.hostname)

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
        # if the
        if reason != RTSPReason.NORMAL:
            self.disconnect()

    def connection_ready(self):
        """
        Called when the RTSP connection is established.
        """
        self._rtsp_is_connected = True
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

    def connect(self, udp_ports, next_seq, password=None, credentials=None, volume=100):
        """
        Connect to the airplay receiver by performing an handshake
        :param udp control and timing port als tuple
        :param next_seq: last sequence number
        :param password: optional password required for the device
        :param credentials: credentials required for the device (Apple TV 4 and up only)
        :param volume: default connection volume
        """
        if self._rtsp_is_connected:
            raise RTSPClientAlreadyConnected("The RTSP client for {0} is already connected.".format(str(self)))

        # connect to the rtsp client
        self._rtsp_client.start_handshake(udp_ports, next_seq, rtp_timestamp_for_seq(next_seq, include_latency=True),
                                          password, credentials)
        # set an initial volume
        self._rtsp_client.set_volume(volume)
        return True

    def repair_connection(self, next_seq):
        """
        Reopen the connection if it was closed for e.g. because of a teardown request.
        :param next_seq: next sequence number
        :return: True on success, False otherwise
        """
        if self._rtsp_client.status == RTSPStatus.CLOSED:
            # repair the rtsp connection
            self._rtsp_client.repair_connection(next_seq, rtp_timestamp_for_seq(next_seq, include_latency=True))

            return True

        return False

    def disconnect(self):
        """
        Close the connection to this receiver.
        """
        self._rtsp_is_connected = False

        # close RTSP connection and send the teardown request
        self._rtsp_client.close()

    @property
    def is_connected(self):
        return self._rtsp_is_connected
    # endregion

    # region control / metadata
    def flush(self, seq):
        """
        Send a flush request.
        """
        return self._rtsp_client.flush(seq, rtp_timestamp_for_seq(seq, include_latency=True))

    def set_progress(self, start_seq, current_seq, last_seq):
        """
        Change the current progress.
        :param start_seq: sequence number of the first audio packet
        :param current_seq: sequence number of the current audio packet
        :param last_seq: sequence number of the last audio packet
        """
        # calculate rtp timestamp for each sequence number
        start_rtp = rtp_timestamp_for_seq(start_seq, include_latency=True)
        cur_rtp = rtp_timestamp_for_seq(current_seq, include_latency=True)
        end_rtp = rtp_timestamp_for_seq(last_seq, include_latency=True)

        return self._rtsp_client.set_progress([start_rtp, cur_rtp, end_rtp])

    def set_track_info(self, start_seq, title="", artist="", album=""):
        """
        Set the current track information for the playing tack.
        :param start_seq: start sequence of the current track
        :param title: track title name
        :param artist: track artist name
        :param album: track album name
        :return: True on success, False otherwise
        """
        return self._rtsp_client.set_track_info(
            rtp_timestamp_for_seq(start_seq, include_latency=True),
            DmapList(
                itemname=title,
                songartist=artist,
                songalbum=album
            )
        )

    def set_artwork_data(self, start_seq, data, mime):
        """
        Set the current artwork for the playing tack.
        :param start_seq: start sequence of the current track
        :param data: base64 encoded image data
        :param mime: image mime type
        :return: True on success, False otehrwise
        """
        return self._rtsp_client.set_artwork_data(
            rtp_timestamp_for_seq(start_seq, include_latency=True),
            data,
            mime
        )
    # endregion