import logging
from time import sleep
from getpass import getpass

import keyring

from raopy import RAOPPlayGroup, RAOPServiceListener, STATUS
from raopy.util import set_logs_enabled, set_loglevel, LOG
from raopy.exceptions import DeviceAuthenticationRequiresPasswordError, DeviceAuthenticationRequiresPinCodeError, \
    DeviceAuthenticationWrongPasswordError

# the basic config needs to be enabled for the lowest required loglevel
#logging.basicConfig(level=logging.DEBUG)

#set_logs_enabled(LOG.RTSP | LOG.RECEIVER)# | LOG.CONTROL)
set_logs_enabled(LOG.GROUP | LOG.RTSP)
set_loglevel(LOG.ALL, logging.DEBUG)
set_loglevel(LOG.RECEIVER, logging.INFO)

SHAIRPORT_DEVICE3 = "JonasMacbookpro._raop._tcp.local."
SHAIRPORT_DEVICE1 = "MacBookPro._raop._tcp.local."
SHAIRPORT_DEVICE0 = "Wohnzimmer._raop._tcp.local."
SHAIRPORT_DEVICE2 = "ATV._raop._tcp.local."


group = RAOPPlayGroup()


def add_receiver(device, name, info):
    if SHAIRPORT_DEVICE0 == name.split("@")[1] or SHAIRPORT_DEVICE1 == name.split("@")[1]:
        try:
            group.add_receiver(device)
        except DeviceAuthenticationRequiresPasswordError:
            # try to connect with a password
            pwd = getpass("Enter password: ")
            while True:
                try:
                    group.add_receiver(device, password=pwd)
                    break
                except DeviceAuthenticationWrongPasswordError:
                    pwd = getpass("Wrong password, try again: ")

        except DeviceAuthenticationRequiresPinCodeError:
            # connect with a pin code
            keychain = "Pygroup"
            # check if we already got credentials for this device
            auth_data = keyring.get_password(keychain, device.name)
            if auth_data:
                auth_identifier, auth_secret = auth_data.split(":")
            else:
                # request a pin code an generate credentials for this device
                group.request_pincode_for_device(device)
                pin = getpass("Enter pin code: ")
                auth_identifier, auth_secret = group.request_login_credentials_for_device_(device, pin)
                # save password
                keyring.set_password(keychain, device.name, "{0}:{1}".format(auth_identifier, auth_secret))

            # try to connect with new credentials
            group.add_receiver(device, credentials=(auth_identifier, auth_secret))


def remove_receiver(device, name, info):
    group.remove_receiver(device)


listener = RAOPServiceListener()
listener.on_connect += add_receiver
listener.on_disconnect += remove_receiver
listener.start_listening()

# listen for new devices for 5 seconds
sleep(5)

group.play("sample.mp3")

# sleep(4)
# print("Pause it now.")
# group.stop()
#group.pause()
# group.set_progress(90000)
#sleep(4)
# print("Resume it now.")
#group.resume()

#sleep(14)
# print("Pause it now.")
#group.pause()
#sleep(6)
# print("Resume it now.")
#group.resume()

# play until the track is finished
while group.status != STATUS.STOPPED:
    sleep(1)

group.close()
