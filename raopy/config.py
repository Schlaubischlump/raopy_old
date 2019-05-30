DEFAULT_RTSP_TIMEOUT = 5  # RTSP servers are considered gone if no reply is received before the timeout (in seconds)
STREAM_LATENCY = 0.05  # audio UDP packets are flushed in bursts periodically (in seconds)


# Initialization vector encoded as base64 and encryption key needed for RSA encrypted streaming (ApEx requires this)
IV = "ePRBLI0XN5ArFaaz7ncNZw"
RSA_AES_KEY = "VjVbxWcmYgbBbhwBNlCh3K0CMNtWoB844BuiHGUJT51zQS7SDpMnlbBIobsKbfEJ3SCgWHRXjYWf7VQWRYtEcfx7ejA8xDIk5PSB" \
              "YTvXP5dU2QoGrSBv0leDS6uxlEWuxBq3lIxCxpWO2YswHYKJBt06Uz9P2Fq2hDUwl3qOQ8oXb0OateTKtfXEwHJMprkhsJsGDrIc" \
              "5W5NJFMAo6zCiM9bGSDeH2nvTlyW6bfI/Q0v0cDGUNeY3ut6fsoafRkfpCwYId+bg3diJh+uzw5htHDyZ2sN+BFYHzEfo8iv4KDx" \
              "zeya9llqg6fRNQ8d5YjpvTnoeEQ9ye9ivjkBjcAfVw"


# Do not change this values unless you know what you are doing. All of the values below are more or less constant for
# AirTunes v2.
FRAMES_PER_PACKET = 352
SAMPLING_RATE = 44100  # should always be 44100 for AirTunes v2
SYNC_PERIOD = 126  # UDP sync packets are sent to all AirTunes devices regularly

# Airplay sends everything with a latency 11025 + latency set in the sync packet (RAOP_FRAME_LATENCY)
RAOP_FRAME_LATENCY = 2*SAMPLING_RATE
RAOP_LATENCY_MIN = 11025

