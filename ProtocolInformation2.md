This is a markdown mirror of [https://git.zx2c4.com/Airtunes2/about/#detect-metadata-and-audio-latency](https://git.zx2c4.com/Airtunes2/about/#detect-metadata-and-audio-latency).


# AirTunes 2 Protocol

- [Introduction](#introduction)
- [Credits](#credits)
- [Conventions](#conventions)
- [Streaming audio to an AirTunes 2 compatible server](#streaming-audio-to-an-airtunes-2-compatible-server)
  - [Connect](#connect)
  - [Transmitting Audio](#transmitting-audio)
  - [Suspending Audio Transmission](#suspending-audio-transmission)
  - [Resuming Audio Transmission](#resuming-audio-transmission)
  - [Disconnect](#disconnect)
- [Preferred TCP/UDP ports](#preferred-tcpudp-ports)
- [Payloadtypes](#payloadtypes)
  - [Data types](#data-types)
  - [RtpHeader](#rtpheader)
  - [NTP Timestamp](#ntp-timestamp)
  - [RTP Timestamp](#rtp-timestamp)
  - [TimingPacket](#timingpacket)
  - [SyncPacket](#syncpacket)
  - [ResendPacket](#resendpacket)
- [Constants](#constants)
- [RTSP](#rtsp)
  - [Common request headers](#common-request-headers)
  - [Request URI](#request-uri)
  - [ANNOUNCE](#announce)
  - [FLUSH](#flush)
  - [OPTIONS](#options)
  - [RECORD](#record)
  - [SET\_PARAMETER](#set\parameter)
    - [Setting volume](#setting-volume)
    - [Set progress](#set-progress)
    - [Set DAAP metadata](#set-daap-metadata)
  - [SETUP](#setup)
  - [TEARDOWN](#teardown)
  - [Rogue Amoeba extensions](#rogue-amoeba-extensions)
    - [X\_RA\_SET\_ALBUM\_ART](#x\ra\set\album\art)
    - [X\_RA\_SET\_PLIST\_METADATA](#x\ra\set\plist\metadata)
  - [Authentication](#authentication)
  - [Detect speaker type](#detect-speaker-type)
  - [Detect metadata and audio latency](#detect-metadata-and-audio-latency)
- [Timing](#timing)
  - [Replying to timing packet](#replying-to-timing-packet)
- [Sync](#sync)
  - [Sending sync packet](#sending-sync-packet)
- [Audio](#audio)
  - [Audio packet](#audio-packet)
  - [Audio codec](#audio-codec)
  - [Packetizing audio](#packetizing-audio)
- [Metadata](#metadata)
  - [DAAP metadata](#daap-metadata)
  - [PList metadata](#plist-metadata)
- [Zeroconf TXT record](#zeroconf-txt-record)
- [Rogue Amoeba extensions](#rogue-amoeba-extensions-1)

## Introduction

Airtunes 2 is the protocol used by Apple's Airport Express, iTunes and Rogue Amoeba's Airfoil. The [previously known RAOP protocol](http://xmms2.org/wiki/Technical_note_to_describe_the_Remote_Audio_Access_Protocol_(RAOP)_as_used_in_Apple_iTunes_to_stream_music_to_the_Airport_Express_(ApEx).) does not support more advanced timing features, and as such, some software, such as [PulseAudio](http://www.pulseaudio.org/) do not support audio/video syncing and sometime suffer from unreliable playback. The Airtunes 2 project seeks to remedy this.

## Credits

- [The Airtunes 2 Team](http://git.zx2c4.com/Airtunes2/about/)
- [Apple Inc.](http://www.apple.com/)
- [Rogue Amoeba Software, LLC](http://www.rogueamoeba.com/)

## Conventions

In the examples below, values to be replaced are put into curly braces ("{}"). The braces should not be included after replacing the values.

## Streaming audio to an AirTunes 2 compatible server

If encryption is necessary, a random key and IV (initialization vector) for AES encryption, 16 bytes each, should be generated.

Every stream has an associated RTP timestamp (uint32; initially set to a random number transmitted to the server in the RECORD RTSP request) and a sequence number (int16; initially set to random value transmitted to the server in the RECORD RTSP request). Both are updated when sending audio packets. Audio data is encapsulated in RTP packets which are sent sent as UDP packets to the audio port.

There are TIMESTAMPS\_PER\_SECOND RTP timestamp ticks per second (equivalent to the number of frames per second).

Up to PACKET\_BACKLOG audio packets should be kept around after encoding and encryption to resend if necessary. After sending an audio packet, the sender should check if a sync packet should also be sent (basically every TIMESYNC\_INTERVAL frames and just after connecting).

### Connect

1. Establish TCP connection to RTSP port
	- IP address(es) from Zeroconf TXT record
2. Send RTSP OPTIONS request
3. Send RTSP ANNOUNCE request
	- Use password authentication based on authentication type from Zeroconf TXT record or after receiving HTTP status code 401 (401 Unauthorized)
4. Send RTSP SETUP request
5. Set sequence number of connection to a random 16 bit unsigned int and initial  RTP timestamp to a random 32 bit unsigned int. Normal play time (npt) is initially 0.
6. Send RTSP RECORD request
7. Send RTSP SET_PARAMETER request to set initial volume (see Setting volume)
8. Prepare RTP connection for audio packets


### Transmitting Audio

The audio data is encapsulated in an RTP packet (see RFC3550 Section 5.1)

1. Bytes 0-1 of the RTP Header are 0x80, 0x60 (0x80, 0xe0 for the 1st packet in a stream or after a FLUSH).
2. Bytes 2-3 store the current sequence number (whose initial value was set in the RECORD RTSP request)
3. Bytes 4-7 store the current RTP timestamp (initial value was transmitted to the Airtunes device in the RECORD RTSP request)
4. Bytes 8-11 store the SSRC (random number which will be the same in all audio packets, see RFC3550 Section 5.1 for more details) (TODO: is the SSRC the same as the RTSP client session ID ?)
5. Starting at byte 12 comes the audio data (see Packetizing audio for its format)
6. Send this RTP packet as UDP on the audio data port
7. Increase sequence number by one for next audio packet
8. Increase timestamp by number of frames in this audio packet

### Suspending Audio Transmission

1. Send a FLUSH RTSP request
2. Stop sending audio packets
3. If the audio transmission is suspsending for too long (iTunes defines "too long" as being equal to 2 seconds), send an RTSP TEARDOWN request.

### Resuming Audio Transmission

1. If a TEARDOWN request has been sent, the RTSP connection has to be recreated, so the steps described in Connect have to be replayed (the OPTIONS step can be omitted)
2. Start sending audio as if it was a new audio stream even if the Connect steps weren't replayed. This means the transmission will start with a SyncPacket marked as a "first" packet, and it will be followed by an Audio packet with the "first" marker too.

### Disconnect

1. Stop sending audio data
2. Close RTSP connection

## Preferred TCP/UDP ports

|Connection|Port|
|---|---|
|RTSP|5000|
|Audio data|6000|
|RTP control|6001|
|Timing|6002|

## Payloadtypes

<table>
<tr><td>Timing request</td><td>0x52</td></tr>
<tr><td>Timing response</td><td>0x53</td></tr>
<tr><td>Sync</td><td>0x54</td></tr>
<tr><td>Range resend</td><td>0x55</td></tr>
<tr><td>Audio data</td><td>0x60</td></tr>
</table>

### Data types

When transferred over the network, multi-byte values need to converted to network byte order. No aligning must be used within the packet structures.

### RtpHeader

```C
/* RTP header bits */
RTP_HEADER_A_EXTENSION = 0x10;
RTP_HEADER_A_SOURCE = 0x0f;

RTP_HEADER_B_PAYLOAD_TYPE = 0x7f;
RTP_HEADER_B_MARKER = 0x80;

/* sizeof(RtpHeader) == 4 */
RtpHeader {
 uint8_t a;
 uint8_t b;
 uint16_t seqnum;

 /* extension = bool(a & RTP_HEADER_A_EXTENSION) */
 /* source = a & RTP_HEADER_A_SOURCE */

 /* payload_type = b & RTP_HEADER_B_PAYLOAD_TYPE */
 /* marker = bool(b & RTP_HEADER_B_MARKER) */
}
```

### NTP Timestamp

This is an NTP Timestamp as described in RFC 3450 Section 4. and RFC 1305. The timestamps used by iTunes and the device seems to come from a monotonic clock which starts at 0 when they just started/booted. This monotonic clock's origin of time is the unix epoch, which corresponds to 0x83aa7e80 seconds in NTP time.

```C
/* sizeof(NtpTime) == 8 */
struct NtpTime {
  /* Seconds since 1900-01-01 00:00:00 (TODO: Timezone?) */
  uint32_t integer;

  /* Fraction of second (0..2^32) */
  uint32_t fraction;
}
```

### RTP Timestamp

This is a 32 bit network order value increasing by 1 for each frame of data transmitted, which means it increases by FRAMES\_PER\_PACKET for every RTP packet sent.

### TimingPacket

```C
/* sizeof(TimingPacket) == 32 */
struct TimingPacket {
  RtpHeader header;
  uint32_t zero_padding;
  NtpTime reference_time;
  NtpTime received_time;
  NtpTime send_time;
}
```

### SyncPacket

```C
/* sizeof(SyncPacket) == 20 */
struct SyncPacket {
  RtpHeader header;
  RtpTimestamp now_minus_latency;
  NtpTime time_last_sync;
  RtpTimestamp now;
}
```

### ResendPacket

```C
/* sizeof(RtpResendPacket) == 8 */
struct RtpResendHeader {
  RtpHeader header;
  uint16_t missed_seqnum;
  uint16_t count;
}
```

## Constants

|Name|Value|Description|
|---|---|---|
|FRAMES\_PER\_PACKET|352|Audio frames per packet|
SHORTS\_PER\_PACKET|2 * FRAMES\_PER\_PACKET|Shorts per packet|
TIMESTAMPS\_PER\_SECOND|44100|Timestamps per second|
TIMESYNC\_INTERVAL|44100|Once per second|
TIME\_PER\_PACKET|FRAMES\_PER\_PACKET / 44100|Milliseconds|
PACKET\_BACKLOG|1000|Packet resend buffer size|

## RTSP

### Common request headers

<table>
<tr><td>Client-Instance</td><td>64 random bytes in hex. Must be unique per connection.</td></tr>
<tr><td>CSeq</td><td>Request sequence number. Can either be counted locally or response sequence number can be increased by one.</td></tr>
<tr><td>RTP-Info</td><td>rtptime={RTP timestamp}</td></tr>
<tr><td>Session</td><td>Server session ID (after SETUP)</td></tr>
<tr><td>User-Agent</td><td>iTunes/{Version} (Windows; N;) (e.g. Version=``iTunes/7.6.2 (Windows; N;)``) (for a mac, this looks like User-Agent: iTunes/9.2.1 (Macintosh; Intel Mac OS X 10.5.8) AppleWebKit/533.17.8)</td></tr>
</table>

### Request URI

Unless specified otherwise, `rtsp://{Local IP address}/{Client session ID}` must be used as the request URI. The client session ID is a random number between 0 and 2<sup>32</sup> generated once per connection.

Note that the Local IP address cannot be a Link Local address (i.e. it cannot begin with 169.254) - it must be the primary IP address of the Airport, which is the first address record listed in the Airport's RAOP service announcement.

### ANNOUNCE

<table>
<tr><td>Headers</td><td>Content-Type: application/sdp</td></tr>
<tr><td>Body</td><td>v=0\r\n</td></tr>
<tr><td></td><td>o=iTunes {Client session ID} O IN IP4 {Local IP address}\r\n</td></tr>
<tr><td></td><td>s=iTunes\r\n</td></tr>
<tr><td></td><td>c=IN IP4 {Server IP address}\r\n</td></tr>
<tr><td></td><td>t=0 0\r\n</td></tr>
<tr><td></td><td>m=audio 0 RTP/AVP 96\r\n</td></tr>
<tr><td></td><td>a=rtpmap:96 AppleLossless\r\n</td></tr>
<tr><td></td><td>a=fmtp:96 {Frames per packet} 0 16 40 10 14 2 255 0 0 44100\r\n</td></tr>
<tr><td></td><td>a=rsaaeskey:{AES key in base64 w/o padding}\r\n</td></tr>
<tr><td></td><td>a=aesiv:{AES IV in base64 w/o padding}\r\n</td></tr>
<tr><td></td><td>\r\n</td></tr>
</table>

### FLUSH

<table><tr><td>Headers</td><td>RTP-Info: seq={Last RTP seqnum};rtptime={Last RTP time}</td></tr></table>

### OPTIONS

<table>
<tr><td>URI</td><td>*</td></tr>
<tr><td>Headers</td><td>Apple-Challenge: {16 random bytes in base64 w/o padding}</td></tr>
</table>

### RECORD

<table>
<tr><td>Headers</td><td>Range: ntp=0-</td></tr>
<tr><td></td><td>RTP-Info: seq={Note 1};rtptime={Note 2}</td></tr>
</table>
Note 1: Initial value for the RTP Sequence Number, random 16 bit value

Note 2: Initial value for the RTP Timestamps, random 32 bit value

### SET\_PARAMETER

#### Setting volume

<table>
<tr><td>Headers</td><td>Content-Type: text/parameters</td></tr>
<tr><td>Body</td><td>volume: %f</td></tr>
</table>
	
Volume is either -144.0 (muted) or (-30.0)..(0.0).

#### Set progress

<table>
<tr><td>Headers</td><td>Content-Type: text/parameters</td></tr>
<tr><td>Body</td><td>progress: %f/%f/%f</td></tr>
</table>

Values are RTP timestamp as unsigned integers (TODO).

#### Set DAAP metadata

<table>
<tr><td>Headers</td><td>Content-Type: application/x-dmap-tagged</td></tr>
<tr><td></td><td>[RTP-Info](#ANNOUNCE)</td></tr>
<tr><td>Body</td><td>DAAP metadata</td></tr>
</table>

### SETUP
<table>
<tr><td>Headers</td><td>Transport: RTP/AVP/UDP;unicast;interleaved=0-1;mode=record;control_port={Control port};timing_port={Timing port}</td></tr>
</table>

Get server\_port, control\_port and timing\_port from Transport response header. Get Session response header and use it as server session ID. The Audio-Jack-Status header is part of this response too.

### TEARDOWN

Nothing special.

### Rogue Amoeba extensions

#### X\_RA\_SET\_ALBUM\_ART

Use this only if server wants PList metadata. Use the SET\_PARAMETER method if DAAP metadata is requested.

<table>
<tr><td>Headers</td><td>Content-Type: {Image content type}</td></tr>
<tr><td></td><td>[RTP-Info](#ANNOUNCE)</td></tr>
<tr><td>Body</td><td>Image data</td></tr>
</table>

#### X\_RA\_SET\_PLIST\_METADATA

<table>
<tr><td>Headers</td><td>Content-Type: application/xml</td></tr>
<tr><td></td><td>[RTP-Info](#ANNOUNCE)</td></tr>
<tr><td>Body</td><td>Metadata in PList format</td></tr>
</table>

### Authentication

AirTunes 2 uses the HTTP Digest authentication method as described in RFC2617.

### Detect speaker type

If Audio-Jack-Status is in response:

```C
speaker_type() {
  if ("disconnected" in Audio-Jack-Status) {
    return unplugged;

  } else if ("connected" in Audio-Jack-Status) {
    if ("digital" in Audio-Jack-Status) {
      return digital;
    }

    return analog;
  }

  return unknown;
}
```

### Detect metadata and audio latency

If Apple-Response, Server or Audio-Latency in response:

```C
if (Apple-Response in response) {
  lowercase_password = False;
  audio_format = EncryptedALAC;
  wants_album_art = False;
  wants_metadata = False;
  wants_progress = False;
  has_bad_latency_header = False;
}

if (Server in response) {
  lowercase_password = True;
  has_bad_latency_header = True;

  if (not Apple-Response in response) {
    audio_format = UnencryptedALAC;
    wants_album_art = DAAP;
    wants_metadata = DAAP;
    wants_progress = True;
  }
}

if (Audio-Latency in response) {
  if (not has_bad_latency_header) {
    audio_latency = Audio-Latency;
  } else {
    if (Audio-Latency == 322 or
        Audio-Latency == 15049) {
      audio_latency = 11025;
    }

    /* Why always 11025? */
    audio_latency = 11025;
  }
}
```

## Timing

The server will send Timing request UDP packets to the timing port. The sender will answer to this Timing request with a Timing response UDP packet sent to the server timing port.

### Replying to timing packet

```C
on_timing_packet(TimingPacket req) {
 assert req.header.payload_type == PAYLOAD_TIMING_REQUEST;

 TimingPacket res;
 res.header = req.header;
 res.header.payload_type = PAYLOAD_TIMING_RESPONSE;
 /* these 3 times are NTP times (ie 64 bit values) */
 res.reference_time = req.send_time;
 res.received_time = time_now();
 res.send_time = time_now();
 /* TODO: is req.send_time the time on the server? the (virtual) NTP time
  * of the audio packet that is being played by the server? Is one of the
  * other timestamp the time on the sender, and the other one, some kind of
  * "common time" to be used by the server and the sender?
  */

 send(res);
}
```

## Sync

Sync packets are sent once per second or when adding a speaker. They are sent to the device control port as UDP packets. The timestamp argument corresponds to the RTP timestamp of the next audio packet that will be sent. The latency argument is gathered from the Audio-Latency RTSP header. First is set on the first packet and after a FLUSH.

### Sending sync packet

```C
send_sync(uint32_t timestamp, uint32_t latency, bool first) {
 SyncPacket packet;
 packet.header.payload_type = PAYLOAD_SYNC;
 packet.header.marker = True;
 packet.header.seqnum = 7; /* Why fixed? */

 if (first) {
   packet.header.extension = True;
 }

 packet.now_minus_latency = timestamp - latency;
 packet.now = timestamp;
 packet.time_last_sync = time_of_last_sync_packet;
}
```

## Audio

### Audio packet

Header:

```C
/* The first 4 bytes are an RtpHeader */
{ 0x80, 0x60, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00,
  {A}, {B}, {C}, {D} }
```

{A}, {B}, {C}, and {D} are four random bytes that are generated per-session.

### Audio codec

<table>
<tr><td>Codec</td><td>Apple Lossless (ALAC)</td></tr>
<tr><td>Sample size</td><td>16 Bit</td></tr>
<tr><td>Channels</td><td>2</td></tr>
<tr><td>Sample rate</td><td>44100</td></tr>
</table>

### Packetizing audio

1. Collect FRAMES_PER_PACKET frames from input data (each frame is 2 bytes)
2. Encode input frames using ALAC codec
3. Encode packet data
	- Raw L16
		1. Convert raw input data to big endian (it's an array of uint16)
		2. Copy audio header and converted audio data into one buffer
		3. Set 2nd byte of buffer to 0xa
	- Unencrypted ALAC
		1. Copy audio header to buffer
		2. Append ALAC encoded audio data to buffer
	- Encrypted ALAC
		1. Encrypt ALAC encoded audio data (only complete 16 byte blocks, the rest stays unencrypted)
		2. Copy audio header to buffer
		3. Append encrypted audio data to buffer

## Metadata

### DAAP metadata

<table>
<tr><td>Content-type</td><td>application/x-dmap-tagged</td></tr>
<tr><td>Item name field</td><td>dmap.itemname</td></tr>
<tr><td>Artist field</td><td>daap.songartist</td></tr>
<tr><td>Album field</td><td>daap.songalbum</td></tr>
</table>

### PList metadata

<table>
<tr><td>Content-type</td><td>application/xml</td></tr>
<tr><td>Title field</td><td>title</td></tr>
<tr><td>Artist field</td><td>artist</td></tr>
<tr><td>Album field</td><td>album</td></tr>
</table>

## Zeroconf TXT record

|Field|Description|
|---|---|
|txtvers|TXT record version (always 1)|
|pw	|true if password required, false otherwise|
|sr	|Audio sample rate|
|ss	|Audio bit rate|
|ch	|Number of audio channels|
|tp	|Protocol (UDP [TODO: or TCP?])|

## Rogue Amoeba extensions

|Field|Description|
|---|---|
|rast|afs if Airfoil speaker|
|ramach|{Platform name}.{OS major version}|
|raver|Library version|
|raAudioFormats|ALAC or L16|
