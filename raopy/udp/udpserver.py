"""
Listen on all interfaces for udp requests.
This class processes all timing and control requests from all clients and send sync packages accordingly.
"""

import socket
from logging import getLogger
from collections import namedtuple
from select import select
from threading import Thread

from ..util import NtpTime, low32
from ..config import FRAMES_PER_PACKET, SAMPLING_RATE, REF_SEQ
from .timingpacket import TIMING_PACKET_SIZE, TimingPacket
from .controlpacket import SyncPacket

timing_logger = getLogger("TimingLogger")
control_logger = getLogger("ControlLogger")

DEFAULT_TIMING_PORT = 6002
DEFAULT_RTP_CONTROL_PORT = 6001


SocketSpecification = namedtuple("SocketSpecification", ["socket", "port", "name"])


def find_open_ports(start_port):
    """
    Find all open ports beginning by the start_port.
    :param ip: ip address to scan open ports
    :param start_port: port to begin the search
    :yield: socket, open port
    """
    assert 0 < start_port < 65535

    for port in range(start_port, 65535):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(("", port))
        except OSError:
            # socket already in use
            continue
        yield s, port


class UDPServer(object):
    """
    UDP Server to allow sending timing information to the host.
    """
    def __init__(self):
        self._hosts = {}

        # set a NTP reference time
        NtpTime.initialize()

        s, p = next(find_open_ports(DEFAULT_TIMING_PORT))
        self.timing = SocketSpecification(s, p, "timing")

        s, p = next(find_open_ports(DEFAULT_RTP_CONTROL_PORT))
        self.control = SocketSpecification(s, p, "control")

        self._is_listening = False
        # start listening and responding to incoming packets
        self.start_responding()

    def register_host(self, device):
        """
        Register an new raop receiver which should be listened/responded to.
        :param device: airtunes receiver instance
        :return: True on success, otherwise False
        """
        if device.ip not in self._hosts:
            self._hosts[device.ip] = device
            return True
        return False

    def unregister_host(self, device):
        """
        Unregister an raop receiver and stop listening/responding to it.
        :param device: airtunes receiver instance
        :return: True on success, otherwise False
        """
        if device.ip in self._hosts:
            del self._hosts[device.ip]
            return True
        return False

    def send_control_sync(self, seq):
        """
        Send a control packet to all registered devices.
        :param seq: sequence number
        """
        for device in self._hosts.values():
            if not device.control_port:
                return

            latency = SAMPLING_RATE*2
            now = low32(seq*FRAMES_PER_PACKET + latency)
            sync_packet = SyncPacket.create(is_first=(seq == REF_SEQ),
                                            now_minus_latency=now - latency,
                                            now=now,
                                            time_last_sync=NtpTime.get_timestamp())


            #sync_packet = SyncPacket.create(is_first=is_first,
            #                                now_minus_latency=low32(seq*FRAMES_PER_PACKET),
            #                                time_last_sync=NtpTime.get_timestamp(),
            #                                now=seq*FRAMES_PER_PACKET + SAMPLING_RATE*2)
            control_logger.debug("Send control packet:\n\033[91m{0}\033[0m".format(sync_packet))
            self.control.socket.sendto(sync_packet.to_data(), (device.ip, device.control_port))

    def close(self):
        self._is_listening = False

        if self.timing:
            self.timing.socket.close()
            self.timing = None

        if self.control:
            self.control.socket.close()
            self.control = None

    def start_responding(self):
        if self._is_listening:
            return

        self._is_listening = True

        def listen_timing():
            """
            Listen and responds to the timing data.
            """
            while self._is_listening:
                select([self.timing.socket], [], [])
                data, addr = self.timing.socket.recvfrom(TIMING_PACKET_SIZE)

                # make sure that the host is registered
                if addr[0] not in self._hosts:
                    return

                # read the timing packet
                response = TimingPacket.parse(data)

                if not response:
                    timing_logger.warning("Skipping malformed packet.")
                    continue
                timing_logger.debug("Received timing packet:\n\033[94m{0}\033[0m".format(response))

                # send responds to timing packets
                request = TimingPacket.create(reference_time=response.send_time, received_time=NtpTime.get_timestamp(),
                                              send_time=NtpTime.get_timestamp())
                timing_logger.debug("Send timing packet:\n\033[91m{0}\033[0m".format(request))
                self.timing.socket.sendto(request.to_data(), addr)

        def listen_control():
            """
            Listen and respond to the control data.
            """
            while self._is_listening:
                select([self.control.socket], [], [])
                data, addr = self.control.socket.recvfrom(1024)
                #print(data)

        # Start a background thread,
        t = Thread(target=listen_timing)
        t.daemon = True
        t.start()

        t = Thread(target=listen_control)
        t.daemon = True
        t.start()
