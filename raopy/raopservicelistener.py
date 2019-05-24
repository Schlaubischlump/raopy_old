"""
Listen for newly connected airplay receiver devices.
Available Events:
- on_connect(receiver, name, info)
- on_disconnect(receiver, name, info)
You can implement these methods to respond when a new airplay receiver is found
"""

import logging

from zeroconf import ServiceBrowser, Zeroconf

from .util import EventHook
from .raopreceiver import RAOPReceiver

RAOP_ZEROCONF_SERVICE = "_raop._tcp.local."


logger = logging.getLogger("RAOPServiceListenerLogger")


class RAOPServiceListener(object):
    """
    Listener for incoming airplay connections.
    """
    def __init__(self):
        """
        :param dacp_id: expected name of the connected airplay service
        :param conf: zeroconf instance
        """
        super(RAOPServiceListener, self).__init__()
        self.devices = {}
        self._browser = None

        self.on_connect = EventHook()
        self.on_disconnect = EventHook()

    def remove_service(self, zeroconf, type, name):
        """
        Called when a service gets removed
        :param zeroconf:
        :param type:
        :param name: name of the servie
        :return:
        """
        logger.info("Remove airplay service: {0}".format(name))
        info = zeroconf.get_service_info(type, name)
        self.on_disconnect.fire(self.devices[name], name=name, info=info)

    def add_service(self, zeroconf, type, name):
        """
        Called when a new service is detected
        :param zeroconf:
        :param type:
        :param name: name of the service
        """
        info = zeroconf.get_service_info(type, name)
        if not info:
            logger.warning("Could not load airplay service information. Skipping device: {0}".format(name))
            return

        self.devices[name] = RAOPReceiver(name=info.name,
                                          address=info.address,
                                          port=info.port,
                                          hostname=info.server)
        logger.info("Add airplay service: {0}".format(name))
        self.on_connect.fire(self.devices[name], name=name, info=info)

    def start_listening(self):
        """
        Wait for incoming connections.
        """
        self._browser = ServiceBrowser(Zeroconf(), RAOP_ZEROCONF_SERVICE, self)

    def stop_listening(self):
        """
        Cancel waiting for incoming connections.
        """
        self._browser = None