"""
Handle the rtsp connection between the client and the receiver.

"""
from threading import Lock

try:
    from queue import Empty
except ImportError:
    from Queue import Empty

import re
from enum import Enum, IntEnum
from logging import getLogger

from .rtspconnection import RTSPConnection
from .rtsprequest import RTSPRequest, DigestInfo

from .. import __version__
from ..crypto.srp import SRPAuthenticationHandler, new_credentials
from ..util import EventHook, random_int, random_hex, get_ip_address, to_bytes
from ..config import DEFAULT_RTSP_TIMEOUT, IV, RSA_AES_KEY, RAOP_LATENCY_MIN
from ..exceptions import DeviceAuthenticationPairingError, DeviceAuthenticationWrongPasswordError, \
    DeviceAuthenticationError, DeviceAuthenticationWrongPinCodeError, NotEnoughBandwidthError, BadResponseError, \
    DeviceAuthenticationRequiresPinCodeError, DeviceAuthenticationRequiresPasswordError, UnsupportedCryptoError, \
    UnsupportedCodecError, RTSPRequestTimeoutError

logger = getLogger("RTSPLogger")

# used for digest info and user agent
USER_STR = "Raopy"
USER_AGENT = "{0}/{1}".format(USER_STR, __version__)


def mutex_lock(func):
    """
    Simple decorator to mutex lock a whole function.
    """
    def func_wrapper(self, *args, **kwargs):
        with self._lock:
            return func(self, *args, **kwargs)
    return func_wrapper


# region enums

# Supported encryption types
class RAOPCrypto(IntEnum):
    CLEAR = 1 << 0
    RSA = 1 << 1
    # unsupported
    FAIRPLAY = 1 << 2
    MFISAP = 1 << 3
    FAIRPLAYSAP = 1 << 4


# Supported Codecs
class RAOPCodec(IntEnum):
    PCM = 1 << 0 # unsupported / coming soon
    ALAC_RAW = 1 << 1 # unsupported / coming soon
    ALAC = 1 << 2
    # unsupported
    AAC = 1 << 3
    AAL_ELC = 1 << 4


# Reason why a cleanup is required
class RTSPReason(Enum):
    BUSY = 0
    UNKNOWN = 1
    TIMEOUT = 2
    NORMAL = 3
    #WRONG_PASSWORD = 4
    AUTHENTICATION = 5


# See: https://nto.github.io/AirPlay.html#introduction
class RTSPStatus(Enum):
    OPTIONS = 0
    ANNOUNCE = 1
    SETUP = 2
    RECORD = 3
    SETVOLUME = 4
    SETPROGRESS = 5
    PLAYING = 6
    TEARDOWN = 7
    CLOSED = 8
    SETDAAP = 9
    SETART = 10
    FLUSH = 11

    def __str__(self):
        return self.name

# endregion


class RTSPClient(object):
    """
    Establish a TCP connection to the server and perform the necessary Real-Time Streaming Protocol communication steps.
    Available Events:
        - on_connection_ready
        - on_connection_closed(reason)
    """

    def __init__(self, ip, port, codecs=RAOPCodec.ALAC, crypto=RAOPCrypto.CLEAR, user_agent=USER_AGENT,
                 dacp_id=None, active_remote=None, protocol_version=1.0):
        """
        :param ip: server ip address
        :param port: server port
        :param codecs: supported RAOP codecs (see the enum for available codes)
        :param crypto: supported RAOP encryption types (see the enum for available types)
        :param user_agent: clients user name
        :param protocol_version: rtsp protocol version number as float
        """
        super(RTSPClient, self).__init__()

        # Callbacks to get informed if the handshake was successfull or when the connection gets closed.
        # If the connection gets closed for what ever reason, you can try to repair it and reconnect.
        self.on_connection_ready = EventHook()
        self.on_connection_closed = EventHook()

        # default lock to prevent sending multiple requests at once
        self._lock = Lock()

        # RTSP protocol version number (1.0 seems to be the only one at the moment)
        self.protocol_version = protocol_version

        # establish a rtsp connection to the server
        self.connection = RTSPConnection(ip, port)

        self.user_agent = user_agent

        self._status = None

        # If the rtsp connection does not responds in a given time frame, the connection will be closed.
        self.timeout = DEFAULT_RTSP_TIMEOUT

        # generate necessary ids
        self.active_remote = active_remote or random_int(9)
        self.dacp_id = dacp_id or random_hex(8)

        # main uri used in the first line of the rtsp request
        client_ip = get_ip_address()
        self.announce_id = random_int(8)
        self.default_uri = "rtsp://{0}/{1}".format(client_ip, self.announce_id)

        # counter variable
        self.cseq = 0

        # current session number received by SETUP
        self.session_id = None
        # current login information
        self.digest_info = None

        # control / timing port on this device
        self.client_control_port = None
        self.client_timing_port = None

        # received ports from handshake
        self.server_port = 0
        self.control_port = 0
        self.timing_port = 0

        # audio latency received by the handshake
        self.audio_latency = RAOP_LATENCY_MIN

        # last used authentication information
        self._last_password = None
        self._last_credentials = None

        # supported encryption types
        self.crypto = crypto
        if not self.crypto & (RAOPCrypto.CLEAR | RAOPCrypto.RSA):
            raise UnsupportedCryptoError("Encrpytion: {0} is not supported.".format(self.crypto.name))

        # supported audio codecs
        self.codecs = codecs
        if not self.codecs & RAOPCodec.ALAC:
            raise UnsupportedCodecError("Codec: {0} is not supported.".format(self.crypto.name))

    def __str__(self):
        return "session_id: {0}\nclient_ip: {1}\nannounce_id: {2}\nserver_port: {3}\ncontrol_port: {4}\n" \
               "timing_port: {5}\ndacp_id: {6}\nactive_remote: {7}\n".format(self.session_id, get_ip_address(),
                                                                             self.announce_id, self.server_port,
                                                                             self.control_port, self.timing_port,
                                                                             self.dacp_id, self.active_remote)

    @property
    def status(self):
        """
        Readonly status of the client.
        :return: current RTSPStatus
        """
        return self._status

    # region helper
    def send_and_recv(self, request, allowed_codes=None):
        """
        Send a request and wait for the responds.
        Return a response only if its code is in the allowed_codes set, otherwise throw an exception.
        :param allowed_codes: whitelist for allow codes
        :return: response instance
        """
        # reopen the connection if required (TEARDOWN was send or the connection wasn't opened yet)
        if not self.connection.is_open():
            self.connection.open()

        logger.debug("Send request:\n\033[91m" + str(request) + "\033[0m")

        # start a timer for each send / receive. If the response takes to long, we consider the server gone
        self.connection.send_request(request)
        try:
            response = self.connection.get_response(timeout=self.timeout)
        except Empty:
            self.cleanup(RTSPReason.TIMEOUT)
            raise RTSPRequestTimeoutError("RTSP request {0} timed out.".format(request.method))

        logger.debug("Received response:\n\033[94m" + str(response) + "\033[0m")

        if allowed_codes is None or response.code in allowed_codes:
            return response

        # error handling
        if response.code == 453:
            self.cleanup(RTSPReason.BUSY)
            raise NotEnoughBandwidthError("Not enough bandwidth, try rebooting your devices.")
        elif response.code != 200:
            self.cleanup(RTSPReason.UNKNOWN)
            raise BadResponseError("Received response with code {0}.".format(response.code))

    def _get_default_header(self):
        """
        Default headers required for an rtsp request.
        :return: header dictionary
        """
        # create our default header
        header = {
            "CSeq": self.cseq,
            "User-Agent": self.user_agent,
            "DACP-ID": self.dacp_id,
            "Client-Instance": self.dacp_id,
            "Active-Remote": self.active_remote,
        }

        # add session number if one is available
        if self.session_id:
            header.update({"Session": self.session_id})

        return header

    def cleanup(self, reason):
        """
        Close the current connection.
        :param reason: RTSPReason reason for cleaning up
        """
        if self._status == RTSPStatus.CLOSED:
            return

        # try to send a teardown request
        try:
            self.teardown()
        except:
            pass

        self._status = RTSPStatus.CLOSED
        self.on_connection_closed.fire(reason.name)

        # close the socket
        self.connection.close()

        logger.info("Connection closed with reason: %s\n%s", reason.name, str(self))
    # endregion

    # region stream control commands: TEARDOWN / FLUSH
    @mutex_lock
    def teardown(self, digest_info=None):
        """
        Teardown the connection.
        """
        if self._status == RTSPStatus.PLAYING:
            if not digest_info:
                digest_info = self.digest_info

            self._status = RTSPStatus.TEARDOWN

            header = self._get_default_header()
            req = RTSPRequest(self.default_uri, "TEARDOWN", header, digest_info=digest_info,
                              protocol_version=self.protocol_version)
            res = self.send_and_recv(req)

            return res.code == 200
        return False

    @mutex_lock
    def flush(self, next_seq, rtp_time, digest_info=None):
        """
        Flush the data.
        :param next_seq: next audio packet sequence number to play
        :param rtp_time: rtp timestamp for next_seq
        """
        if self._status == RTSPStatus.PLAYING:
            # if the handshake was correctly performed, this should be set
            if not digest_info:
                digest_info = self.digest_info

            self._status = RTSPStatus.FLUSH

            self.cseq += 1
            header = self._get_default_header()

            header.update({
                "RTP-Info": "seq={0};rtptime={1}".format(next_seq, rtp_time)
            })

            req = RTSPRequest(self.default_uri, "FLUSH", header, digest_info=digest_info,
                              protocol_version=self.protocol_version)
            res = self.send_and_recv(req)

            self._status = RTSPStatus.PLAYING
            return res.code == 200

        return False
    # endregion

    # region media control commands: VOLUME, PROGRESS, DMAP, ARTWORK
    @mutex_lock
    def set_volume(self, vol, digest_info=None):
        """
        Set a new volume, if the handshake is finished.
        :param vol: new volume
        :param digest_info: information for password protected devices
        :return True on success, otherwise False
        """
        # make sure handshake has finished
        if self._status == RTSPStatus.PLAYING:
            self._status = RTSPStatus.SETVOLUME

            # if the handshake was correctly performed, this should be set
            if not digest_info:
                digest_info = self.digest_info

            # calculate airplay volume
            if vol >= 100:
                vol = 0.0
            elif vol <= 0:
                vol = -144.0  # mute
            else:
                vol = -30.0 * (100.0 - vol) / 100.0

            self.cseq += 1
            header = self._get_default_header()
            header.update({"Content-Type": "text/parameters"})
            body = 'volume: {0}\r\n'.format(vol)
            req = RTSPRequest(self.default_uri, "SET_PARAMETER", header, body=body, digest_info=digest_info,
                              protocol_version=self.protocol_version)

            res = self.send_and_recv(req)
            self._status = RTSPStatus.PLAYING
            return res.code == 200

    @mutex_lock
    def set_progress(self, progress, digest_info=None):
        """
        Set the current playback progress.
        :param progress: new progress as tuple: start/current/end sequence rtp timestamps
        :param digest_info: (optional) information for password protected devices
        :return True on success, otherwise False
        """
        if self._status == RTSPStatus.PLAYING:
            self._status = RTSPStatus.SETPROGRESS

            if not digest_info:
                digest_info = self.digest_info

            self.cseq += 1
            header = self._get_default_header()
            header.update({"Content-Type": "text/parameters"})
            body = 'progress: {0}/{1}/{2}\r\n'.format(*progress)
            req = RTSPRequest(self.default_uri, "SET_PARAMETER", header, body=body, digest_info=digest_info,
                              protocol_version=self.protocol_version)

            res = self.send_and_recv(req)
            self._status = RTSPStatus.PLAYING
            return res.code == 200

        return False

    @mutex_lock
    def set_track_info(self, rtp_time, *args, digest_info=None):
        """
        Set the current track information for the playing tack.
        :param rtp_time: start rtp time of this track
        :param args: a number of dmap items
        """
        if self._status == RTSPStatus.PLAYING:
            self._status = RTSPStatus.SETDAAP

            if not digest_info:
                digest_info = self.digest_info

            self.cseq += 1
            header = self._get_default_header()
            header.update({"Content-Type": "application/x-dmap-tagged"})
            header.update({"RTP-Info": "rtptime={0}".format(rtp_time)})

            body = [item.to_data() for item in args]
            req = RTSPRequest(self.default_uri, "SET_PARAMETER", header, body=b"".join(body), digest_info=digest_info,
                              protocol_version=self.protocol_version)
            res = self.send_and_recv(req)

            self._status = RTSPStatus.PLAYING
            return res.code == 200
        return False

    @mutex_lock
    def set_artwork_data(self, rtp_time, data, mime, digest_info=None):
        """
        Set the current artwork for the playing tack.
        :param rtp_time: start rtp time of this track
        :param data: artwork data base64 encoded
        :param mime: image mime type
        """
        if self._status == RTSPStatus.PLAYING:
            self._status = RTSPStatus.SETART

            if not digest_info:
                digest_info = self.digest_info

            self.cseq += 1
            header = self._get_default_header()
            header.update({"Content-Type": mime})
            header.update({"RTP-Info": "rtptime={0}".format(rtp_time)})
            req = RTSPRequest(self.default_uri, "SET_PARAMETER", header, body=data, digest_info=digest_info,
                              protocol_version=self.protocol_version)
            res = self.send_and_recv(req)

            self._status = RTSPStatus.PLAYING
            return res.code == 200
        return False
    # endregion

    # region handshaking requests: OPTIONS / ANNOUNCE / SETUP / RECORD
    def get_options_request(self, digest_info=None):
        self.cseq += 1
        header = self._get_default_header()
        header.update({"Apple-Challenge": random_hex(8)})
        return RTSPRequest("*", self._status, header, digest_info=digest_info, protocol_version=self.protocol_version)

    def get_announce_request(self, digest_info=None):
        self.cseq += 1
        server_ip = self.connection.address[0]
        client_ip = get_ip_address()

        # add content type to header
        header = self._get_default_header()
        header.update({"Content-Type": "application/sdp"})

        body = "v=0\r\n" \
               "o=iTunes {0} 0 IN IP4 {1}\r\n" \
               "s=iTunes\r\n" \
               "c=IN IP4 {2}\r\n" \
               "t=0 0\r\n" \
               "m=audio 0 RTP/AVP 96\r\n" \
               "a=rtpmap:96 AppleLossless\r\n" \
               "a=fmtp:96 352 0 16 40 10 14 2 255 0 0 44100\r\n".format(self.announce_id, client_ip, server_ip)

        # add encryption key
        if self.crypto & RAOPCrypto.RSA:
            body += "a=rsaaeskey:{0}\r\n" \
                    "a=aesiv:{1}\r\n".format(RSA_AES_KEY, IV)
        body += "\r\n"

        return RTSPRequest(self.default_uri, self._status, header, body=body, digest_info=digest_info,
                           protocol_version=self.protocol_version)

    def get_setup_request(self, digest_info=None):
        """
        Create a SETUP request.
        :param digest_info: optional digest information
        :return: SETUP request
        """
        self.cseq += 1
        header = self._get_default_header()
        header.update({
            "Transport": "RTP/AVP/UDP;unicast;interleaved=0-1;mode=record;"
                         "control_port={0};timing_port={1}".format(self.client_control_port, self.client_timing_port)
        })
        return RTSPRequest(self.default_uri, self._status, header, digest_info=digest_info,
                           protocol_version=self.protocol_version)

    def get_record_request(self, next_seq, rtp_time, digest_info=None):
        """
        Create a RECORD request.
        :param next_seq: next sequence number to play
        :param rtp_time: rtp time of the next sequence number
        :param digest_info: (optional) digest login information
        :return: RECORD request
        """
        self.cseq += 1
        header = self._get_default_header()

        header.update({
            "Range": "npt=0-",
            "RTP-Info": "seq={0};rtptime={1}".format(next_seq, rtp_time)
        })
        return RTSPRequest(self.default_uri, self._status, header, digest_info=digest_info,
                           protocol_version=self.protocol_version)
    # endregion

    # region handshake / repair / close
    @mutex_lock
    def start_handshake(self, udp_ports, next_seq, rtp_time, password=None, credentials=None):
        """
        Handshake with the server.
        :param next_seq: next sequence number to play
        :param rtp_time: rtp time of the next sequence number
        :param udp_ports: udp control and timing port as tuple
        :param password: optional password
        :param credentials: optional login credentials for new apple TVs
        """
        def get_digest_info(headers, password):
            """
            Read the provider OPTIONS headers and extract the digest info.
            :param header: OPTIONS headers
            :return: digest information on success, otherwise None
            """
            if not password:
                return None

            auth = headers.get("WWW-Authenticate", None)
            if not auth:
                return None

            # read digest information from response and establish a connection
            realm, nonce = re.search('realm="([^"]+)".+nonce="([^"]+)"', auth).groups()

            return DigestInfo(username=USER_STR, realm=realm, nonce=nonce, password=password)

        self.client_control_port, self.client_timing_port = udp_ports

        # digest_info for password protected airplay server
        self.digest_info = None

        # store the last authentication information to allow repairing the connection
        self._last_password = password
        self._last_credentials = credentials

        # region options

        self._status = RTSPStatus.OPTIONS
        options = self.get_options_request(self.digest_info)
        res = self.send_and_recv(options, allowed_codes={200, 403, 401})

        # if the device does support encryption it will reply to Apple-Challenge
        if "Apple-Response" in res.headers:
            self.crypto |= RAOPCrypto.RSA

        # Forbidden => Client certificate required
        if res.code == 403:
            # perform the TV OS 10.2 authentication
            if not credentials:
                raise DeviceAuthenticationRequiresPinCodeError("Please provide a pin code for the connection.")
            self._connect_client(credentials)

        # Unauthorized => password is required
        elif res.code == 401:
            if not password:
                raise DeviceAuthenticationRequiresPasswordError("Password required.")

            # the user did provide a password => load the digest information and continue
            # we do not need to resend the OPTIONS request because it does not require the digest information
            self.digest_info = get_digest_info(res.headers, password)

            if not self.digest_info:
                raise DeviceAuthenticationError("Missing password or malformed response.")

        # endregion

        # region announce
        self._status = RTSPStatus.ANNOUNCE
        announce = self.get_announce_request(self.digest_info)
        res = self.send_and_recv(announce, allowed_codes={200, 401})

        # Still unauthorized => password is wrong
        if res.code == 401:
            #self.cleanup(RTSPReason.WRONG_PASSWORD)
            raise DeviceAuthenticationWrongPasswordError("Wrong password.")
        # endregion

        # region setup
        self._status = RTSPStatus.SETUP
        setup = self.get_setup_request(self.digest_info)
        res = self.send_and_recv(setup, allowed_codes={200})

        self.session_id = res.headers["Session"]
        # save server, timing and control port and dispatch an event
        ports = dict(re.findall("((?:control|timing|server)_port)=(\d{1,5})", res.headers["Transport"]))

        self.server_port = int(ports["server_port"])
        self.control_port = int(ports["control_port"])
        self.timing_port = int(ports["timing_port"])
        # endregion

        # region record
        self._status = RTSPStatus.RECORD
        record = self.get_record_request(next_seq, rtp_time, self.digest_info)
        res = self.send_and_recv(record, allowed_codes={200})

        # Todo: currently not used
        if "Audio-Latency" in res.headers:
            self.audio_latency = int(res.headers["Audio-Latency"])
            logger.info("Received audio latency: %s", self.audio_latency)
        else:
            self.audio_latency = RAOP_LATENCY_MIN
            logger.info("Assume default audio latency: %s", self.audio_latency)

        self.on_connection_ready.fire()
        logger.info("Connection ready:\n%s", str(self))
        #endregion

        #  region volume
        self._status = RTSPStatus.PLAYING
        # endregion

    def repair_connection(self, next_seq, rtp_time):
        """
        Try to reopen a socket connection after it was closed.
        :param next_seq: next audio packet sequence number. This can be a random number.
        :param rtp_time: rtp time of next_seq
        """
        # send a complete handshake request
        self.start_handshake((self.client_control_port, self.client_timing_port), next_seq, rtp_time,
                             password=self._last_password, credentials=self._last_credentials)

    def close(self):
        self.cleanup(RTSPReason.NORMAL)
    # endregion

    # region Apple TV 4 authentication
    @mutex_lock
    def request_pincode(self):
        """
        Starting with ios 10.2 Apple TVs require an authentication to communicate over airplay.
        Show a pin code on the apple tv.
        """
        header = {"User-Agent": self.user_agent, "Connection": "keep-alive"}
        req = RTSPRequest("/pair-pin-start", "POST", header, protocol_version=self.protocol_version)
        res = self.send_and_recv(req)

        if res.code != 200:
            self.cleanup(RTSPReason.AUTHENTICATION)
            raise DeviceAuthenticationPairingError("Can not request a pin code.")

    @mutex_lock
    def register_client(self, pin):
        """
        Perform the authentication steps introduced by TV OS 10.2
        :param pin: pin code
        """
        # optional imports required for authentication
        from ..util import parse_plist_from_bytes, write_plist_to_bytes

        def get_plist_request_data(plist_data):
            """
            Create a request header and body to send a plist to the server.
            :param plist_data: dictionary holding the plist data
            :return: plist rtsp request header, plist rtsp request body
            """
            header = {
                "User-Agent": self.user_agent,
                "Content-Type:": "application/x-apple-binary-plist",
                "Connection": "keep-alive",
            }
            return header, write_plist_to_bytes(plist_data)

        # create new unique credentials
        auth_identifier, auth_secret = new_credentials()

        # 2. send plist data to receiver
        header, body = get_plist_request_data({"user": auth_identifier, "method": "pin"})
        req = RTSPRequest("/pair-setup-pin", "POST", header, body=body, protocol_version=self.protocol_version)
        res = self.send_and_recv(req)

        if res.code != 200:
            self.cleanup(RTSPReason.AUTHENTICATION)
            raise DeviceAuthenticationError("Can not receive public key and salt.")

        # 3. read the public key and salt
        res_plist = parse_plist_from_bytes(res.body)
        public_key = res_plist["pk"]
        salt = res_plist["salt"]

        # 4. Run  Secure Remote Password procedure
        srp_handler = SRPAuthenticationHandler()
        srp_handler.initialize(auth_secret)
        srp_handler.step1(auth_identifier, pin)
        pub_key, m1_proof = srp_handler.step2(public_key, salt)

        # send the public key and the proof to the server
        header, body = get_plist_request_data({"pk": pub_key, "proof": m1_proof})
        req = RTSPRequest("/pair-setup-pin", "POST", header, body=body, protocol_version=self.protocol_version)
        res = self.send_and_recv(req)

        if res.code != 200:
            self.cleanup(RTSPReason.AUTHENTICATION)
            raise DeviceAuthenticationWrongPinCodeError("Wrong pin code used.")

        # 5. Run AES
        epk, tag = srp_handler.step3()
        header, body = get_plist_request_data({"epk": epk, "authTag": tag})
        req = RTSPRequest("/pair-setup-pin", "POST", header, body=body, protocol_version=self.protocol_version)
        res = self.send_and_recv(req)

        if res.code != 200:
            self.cleanup(RTSPReason.AUTHENTICATION)
            raise DeviceAuthenticationWrongPinCodeError("Can not confirm authentication secret.")

        return auth_identifier, auth_secret

    def _connect_client(self, credentials):
        """
        Connect a pin code protected device with given credentials. This is an internal not thread safe method !
        :param credentials: login credentials
        """
        auth_identifier, auth_secret = credentials
        # load existing credentials
        srp_handler = SRPAuthenticationHandler()
        srp_handler.initialize(auth_secret)

        # 6. RTSP session authentication
        header = {"User-Agent": self.user_agent,
                  "Connection": "keep-alive",
                  "Content-Type": "application/octet-stream"}
        req = RTSPRequest("/pair-verify", "POST", header, body=srp_handler.verify1(),
                          protocol_version=self.protocol_version)
        res = self.send_and_recv(req)

        if res.code != 200:
            self.cleanup(RTSPReason.AUTHENTICATION)
            raise DeviceAuthenticationError("Can not create keys. Error in verify1.")

        atv_public_secret, data = res.body[:32], res.body[32:]
        req = RTSPRequest("/pair-verify", "POST", header, body=srp_handler.verify2(atv_public_secret, data),
                          protocol_version=self.protocol_version)
        res = self.send_and_recv(req)

        if res.code != 200:
            self.cleanup(RTSPReason.AUTHENTICATION)
            raise DeviceAuthenticationError("Can not create keys. Error in verify2.")
    # endregion
