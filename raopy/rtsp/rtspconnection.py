"""
Simple connection class which listens for incoming messages and allows sending requests.
"""
import re
import socket
from select import select
from threading import Thread

try:
    from Queue import Queue
except ImportError:
    from queue import Queue

from .rtspresponse import RTSPResponse


class RTSPConnection(object):
    def __init__(self, ip, port):
        """
        :param ip: client ip address
        :param port: client port number
        :param timeout: timeout after which the server will be considered gone
        """
        self.address = (ip, port)

        # store all responses in a queue
        self._response_queue = Queue()

        self.open()

    def open(self):
        """
        # Create a TCP connection to the host and listen for responses
        """
        self._socket = socket.create_connection(self.address)
        self.listen_for_responses()

    def close(self):
        """
        Close the socket connection.
        """
        self._socket.close()
        self._socket = None

    def send_request(self, req):
        """
        Send a request to the server.
        :param req: RTSPRequest
        :return True on success, False otherwise
        """
        if not self._socket:
            return False

        self._socket.sendto(req.to_data(), self.address)
        return True

    def get_response(self):
        """
        Wait until a response is received an return it. This method is blocking.
        :return: next RTSPResponse from the _response_queue
        """
        return self._response_queue.get(block=True)

    def listen_for_responses(self):
        """
        Start a background thread to listen to incoming messages from the airplay receiver.
        """
        # regex to find header information inside the data
        header_regex = re.compile(b"(RTSP/\d+.\d+\s\d{3}\s\w+?\\r\\n(?s:.*?)\\r\\n\\r\\n)")
        buffer_size = 1024

        def listen():
            data = b""
            while self._socket:
                try:
                    # wait until we can receive data
                    select([self._socket], [], [])
                    data += self._socket.recv(buffer_size)

                    # found a header inside the data
                    if header_regex.search(data):
                        # repeat for all packages found inside the data
                        for match in header_regex.finditer(data):
                            # get start and end position of the current header
                            start, end = match.span()
                            # parse the responds header
                            res = RTSPResponse.parse_response_header(data[start:end])

                            # if the request contains a body receive it
                            body_size = int(res.headers.get("Content-Length", 0))

                            # fill body with data which we already received
                            already_recv = min(len(data[end:]), body_size)
                            res.body = data[end:end+already_recv]
                            body_size -= already_recv

                            # receive remaining body data from socket in chunks of buffer size
                            while body_size > 0:
                                recv_bytes = min(body_size, buffer_size)
                                res.body += self._socket.recv(recv_bytes)
                                body_size -= recv_bytes

                            # create responds and put it in the queue
                            self._response_queue.put(res)

                        # remove processed bytes from data
                        # these variables have to be defined, because the for loop is at least executed once (because
                        # we found a match)
                        data = data[end+already_recv:]
                except (OSError, ValueError):
                    # socket was closed => cleanup and stop listening
                    self.close()
                    break

        t = Thread(target=listen)
        t.daemon = True
        t.start()
