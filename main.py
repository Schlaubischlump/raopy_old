import logging
from time import sleep
from getpass import getpass

import keyring

from raopy import AirTunes, RAOPServiceListener
from raopy.util import set_logs_enabled, set_loglevel, LOG
from raopy.exceptions import DeviceAuthenticationRequiresPasswordError, DeviceAuthenticationRequiresPinCodeError, \
    DeviceAuthenticationWrongPasswordError

# the basic config needs to be enabled for the lowest required loglevel
#logging.basicConfig(level=logging.DEBUG)

set_logs_enabled(LOG.RTSP | LOG.RECEIVER | LOG.CONTROL)# | LOG.CONTROL)
set_loglevel(LOG.ALL, logging.DEBUG)
#set_loglevel(LOG.RECEIVER, logging.INFO)


SHAIRPORT_DEVICE = "MacBookPro._raop._tcp.local."
SHAIRPORT_DEVICE1 = "D0D2B08AFC10@Wohnzimmer._raop._tcp.local."
SHAIRPORT_DEVICE2 = "1C1AC0A2A0E8@ATV._raop._tcp.local."


airtunes = AirTunes()


def add_receiver(device, name, info):
    if SHAIRPORT_DEVICE == name.split("@")[1]:# or SHAIRPORT_DEVICE1 == device.name:
        try:
            airtunes.connect_device(device)
        except DeviceAuthenticationRequiresPasswordError:
            # try to connect with a password
            pwd = getpass("Enter password: ")
            while True:
                try:
                    airtunes.connect_device(device, password=pwd)
                    break
                except DeviceAuthenticationWrongPasswordError:
                    pwd = getpass("Wrong password, try again: ")

        except DeviceAuthenticationRequiresPinCodeError:
            # connect with a pin code
            keychain = "PyAirTunes"
            # check if we already got credentials for this device
            auth_data = keyring.get_password(keychain, device.name)
            if auth_data:
                auth_identifier, auth_secret = auth_data.split(":")
            else:
                # request a pin code an generate credentials for this device
                airtunes.request_pincode_for_device(device)
                pin = getpass("Enter pin code: ")
                auth_identifier, auth_secret = airtunes.request_login_credentials_for_device_(device, pin)
                # save password
                keyring.set_password(keychain, device.name, "{0}:{1}".format(auth_identifier, auth_secret))

            # try to connect with new credentials
            airtunes.connect_device(device, credentials=(auth_identifier, auth_secret))

        airtunes.play("sample.m4a")
        sleep(14)
        print("Pause it now.")
        airtunes.pause()
        sleep(10)
        print("Resume it now.")
        airtunes.resume()

def remove_receiver(device, name, info):
    airtunes.disconnect_device(device)


listener = RAOPServiceListener()
listener.on_connect += add_receiver
listener.on_disconnect += remove_receiver
listener.start_listening()
sleep(60)
