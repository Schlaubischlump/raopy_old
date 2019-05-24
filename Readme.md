# RAOPY

## Todo
- Cleanup the code! 
- ~~Fix Audio playback not working~~
- Feature: Flush, Teardown, Artwork, Trackinfo support
- PCM stream support (look at RAOP-Player for how to send a raw unencoded pcm stream) 
- Fix connection interrupted, because receiver went offline 
- Allow play, pause, stop, volume of all and single devices
- Allow remote control with http server
- ~~Fix encrypt alac only if apple challenge is requested / 401 is not reliable to detect a password (use the information from zeroconf ?)~~
- Fix respond to control data	
- automatically extract metadata with audiotools and send it
- ~~Add enums for encryption formats etc.~~
- ~~add support for encryption without password protection~~
- Fix throw error if no device is connected and you try to stream audio or something like this (this includes the connection is lost)
- ~~Fix encryption~~
- user zeroconf information for encryption type and codecs (authentication and password as well ?)
- include 2 seconds latency
- Fix setup.py requirements
- - Fix ATV 4 not sending the timing_port (we don't actually need it, but it would be nice to have) (is this possible ?)
- Fix replace hardcoded RSA-Key by a dynamic one (?)
- replace the status variable with locks (?) 