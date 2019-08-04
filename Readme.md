# RAOPY

AirPlay audio for the rest of us. An (hopefully) easy to use implementation of the AirTunes v2 Protocol. 

## Todo
- Cleanup the code! 
- ~~Send DAAP: Artwork, Trackinfo (use audiotools metadata)~~
- PCM stream support (look at RAOP-Player for how to send a raw unencoded pcm stream)
- ~~Fix: Move the seq argument out of RTSP Client and work with the rtp time instead~~
- ~~Fix: replace the status variable with locks (I don't know if this is required, because all rtsp request already wait until a response is in the queue)~~
- Fix: http server lags
- Fix: Dmap classes have some problems with encoding certain ints
- Fix: rewrite the audio-sync class, so that it is actually working and thread safe
- Fix: Audio is sometimes only processed by some devices, but not all
- Fix: connection interrupted, because receiver went offline 
- Fix: stop function (including when the end of the stream is reached)
- Fix: setup.py requirements
- ~~Fix: player hangs if the RTSP connection times out~~
- Fix: seekable audiofile implementation (there is a bug .frames can't be written from python)
- Fix: throw error if no device is connected and you try to stream audio or something like this (this includes the connection is lost)
- use zeroconf information for encryption type and codecs (authentication and password as well ?)
- Test with Python2.7

> Note: Sending RTSP is (is it ... ?) blocking, sending audio packets is not. This is expected behaviour 

### Features:
- Allow volume control of all and single devices
- Allow streaming muliple files after each other

### Low priority:
- Add testcases 
- Add examples
- Provide a convenient wrapper around the password / authentication api 
- Fix: do not allow interaction while flushing (Is this correctly implemented [See: Note above] ?)
- Fix: insert low16 and low32 where required (are there any missing ?)
- Fix: ATV 4 not sending the timing_port (we don't actually need it, but it would be nice to have) (is this possible ?)
- Fix: replace hardcoded RSA-Key by a dynamic one (?)
- Fix: use the latency of each device from the header (is this a good idea after all ? the header seems to be incorrect in some cases and it would require restructuring the code)


