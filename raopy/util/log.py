import logging
from enum import IntEnum


class LOG(IntEnum):
    NONE = 0 << 0  # log nothing
    RTSP = 1 << 0  # log all rtsp packages
    TIMING = 1 << 1  # log all timing packets
    CONTROL = 1 << 2  # log all control packets
    SERVICE = 1 << 3  # log all newly detected airplay devices
    RECEIVER = 1 << 4  # log all device specific information including audio pakets
    GROUP = 1 << 5  # log all raop group specific information
    ALL = 0b111111  # log all events

    def logger_name(self):
        """
        :return: name of the corresponding logger instance
        """
        if self == LOG.RTSP:
            return "RTSPLogger"
        if self == LOG.TIMING:
            return "TimingLogger"
        if self == LOG.CONTROL:
            return "ControlLogger"
        if self == LOG.SERVICE:
            return "RAOPServiceListenerLogger"
        if self == LOG.RECEIVER:
            return "RAOPReceiverLogger"
        if self == LOG.GROUP:
            return "RAOPPlaybackGroupLogger"
        return ""

    def get_logger(self):
        """
        :return: reference to the corresponding logger instance
        """
        return logging.getLogger(self.logger_name())

    @classmethod
    def items(cls):
        """
        Iterate over all LOGGER enums and the corresponding logger instances.
        """
        i = LOG.RTSP.value
        while i < LOG.ALL.value:
            log_enum = LOG(i)
            yield log_enum, log_enum.get_logger()
            i <<= 1


def set_logs_enabled(logs):
    """
    Usage: set_logs_enabled(LOG.RTSP | LOG.TIMING)

    :param logs: different logs to enable
    """
    for log_enum, logger in LOG.items():
        # enable or disable the propagation
        logger.propagate = log_enum & logs


def set_loglevel(logs, level):
    """
    Change the loglevel for all specified logs.
    Usage: set_loglevel(LOG.RTSP | LOG.TIMING, logging.DEBUG)
    :param logs: different logs to enable
    :param level: log level
    """
    min_log_level = float("Inf")

    for log_enum, logger in LOG.items():
        min_log_level = min(logger.level, min_log_level)
        # change the log level
        if log_enum & logs:
            logger.setLevel(level)

    # the basic config needs to be enabled for the lowest required loglevel
    logging.basicConfig(level=min_log_level)
