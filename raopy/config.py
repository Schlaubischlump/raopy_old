DEFAULT_RTSP_TIMEOUT = 5  # RTSP servers are considered gone if no reply is received before the timeout (in seconds)
FRAMES_PER_PACKET = 352
SAMPLING_RATE = 44100  # should always be 44100 for AirTunes v2
STREAM_LATENCY = 0.05  # audio UDP packets are flushed in bursts periodically (in seconds)
SYNC_PERIOD = 126  # UDP sync packets are sent to all AirTunes devices regularly

IV = "ePRBLI0XN5ArFaaz7ncNZw" # initialization vector encoded as base64
RSA_AES_KEY = "VjVbxWcmYgbBbhwBNlCh3K0CMNtWoB844BuiHGUJT51zQS7SDpMnlbBIobsKbfEJ3SCgWHRXjYWf7VQWRYtEcfx7ejA8xDIk5PSB" \
              "YTvXP5dU2QoGrSBv0leDS6uxlEWuxBq3lIxCxpWO2YswHYKJBt06Uz9P2Fq2hDUwl3qOQ8oXb0OateTKtfXEwHJMprkhsJsGDrIc" \
              "5W5NJFMAo6zCiM9bGSDeH2nvTlyW6bfI/Q0v0cDGUNeY3ut6fsoafRkfpCwYId+bg3diJh+uzw5htHDyZ2sN+BFYHzEfo8iv4KDx" \
              "zeya9llqg6fRNQ8d5YjpvTnoeEQ9ye9ivjkBjcAfVw" # encryption key