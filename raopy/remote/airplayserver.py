"""
Implemented according to https://nto.github.io/AirPlay.html#audio-remotecontrol
"""
import time
import socket
import logging
from enum import Enum
from threading import Thread

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

from zeroconf import ServiceInfo, Zeroconf

from raopy.util import EventHook


logger = logging.getLogger("AirplayRemoteServerLogger")


class AirplayCommand(Enum):
    """
    Available airplay commands.
    """
    BEGIN_FAST_FORWARD = "beginff"
    BEGIN_REWIND = "beginrew"
    PREVIOUS_SONG = "previtem"
    NEXT_SONG = "nextitem"
    PAUSE = "pause"
    PLAY_PAUSE = "playpause"
    PLAY = "play"
    STOP = "stop"
    PLAY_RESUME = "playresume"
    SHUFFLE_SONGS = "shuffle_songs"
    VOLUME_DOWN = "volumedown"
    VOLUME_UP = "volumeup"

    def __str__(self):
        return self.value

AIRPLAY_ZEROCONF_SERVICE = "_dacp._tcp.local."


class RequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        """
        Handle GET requests.
        """
        res_code = 200

        # check if the path is correct
        _, ctrl, num, cmd = self.path.split("/")
        if _ == "" and ctrl == "ctrl-int" and num == "1":
            # check if the command is valid and inform all listener
            try:
                airplay_cmd = AirplayCommand(cmd)
                logger.debug("Received airplay remote command: %s", airplay_cmd)
                self.server.on_remote_command.fire(airplay_cmd)
            except ValueError:
                res_code = 400
        else:
            res_code = 400

        # create the responds header
        self.send_response(res_code)
        self.send_header('Content-Length', '0')
        self.send_header('Date', time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime()))
        self.end_headers()


class AirplayServer(HTTPServer):
    """
    Start an Airplay remote server on this device with a specific port.
    Available Events:
        - on_remote_command(AirplayCommand)
    """
    def __init__(self, dacp_id, active_remote, port=52485):
        super(AirplayServer, self).__init__(("", port), RequestHandler)

        self.dacp_id = dacp_id
        self.active_remote = active_remote

        self.on_remote_command = EventHook()

        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        # setup the service information
        self.info = ServiceInfo(
            type_=AIRPLAY_ZEROCONF_SERVICE,
            name="iTunes_Ctrl_{0}.{1}".format(dacp_id, AIRPLAY_ZEROCONF_SERVICE),
            address=socket.inet_aton(local_ip),
            port=port,
            properties={},
            server="{0}.local.".format(hostname)
        )

        self._zeroconf = Zeroconf()

    def start(self):
        """
        Start the main http server and register the dacp service.
        :return: server thread
        """

        thread = Thread(target=self.serve_forever, daemon=True)
        thread.start()
        logger.debug("Started HTTP server on port: %s", self.info.port)

        # register a zeroconf dacp service
        self._zeroconf.register_service(self.info)
        logger.debug("Published service with info: %s", self.info)

        return thread

    def stop(self):
        """
        Close the current server.
        :return:
        """
        # unregister zero conf service
        self._zeroconf.unregister_service(self.info)
        self._zeroconf.close()
        logger.debug("Removed service with info: %s", self.info)

        # shutdown the http server
        self.shutdown()
        logger.debug("Stopped HTTP server on port: %s", self.info.port)
