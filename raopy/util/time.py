from datetime import datetime

from ..exceptions import MissingNtpReferenceTime


def milliseconds_since_1970():
    """
    :return: milliseconds since 01.01.1970 as integer
    """
    return int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()*1000)


class NtpTime(object):
    """
    Provide Ntp Timestamps with a fixed reference time.
    """
    __slots__ = ["second", "fraction"]

    reference_time = None

    def __init__(self, second, fraction):
        self.second = second
        self.fraction = fraction

    def __iter__(self):
        """
        Support unpacking.
        :return: iterator for slots
        """
        return (x for x in [self.second, self.fraction])

    def __str__(self):
        return "({0}, {1})".format(self.second, self.fraction)

    def __repr__(self):
        return str(self)

    @classmethod
    def initialize(self):
        # 2208988800 corresponds to the seconds from 1.1.1900 to 1.1.1970
        NtpTime.reference_time = milliseconds_since_1970() - 2208988800000

    @classmethod
    def get_timestamp(cls):
        """
        Calculate the current timestamp based on the reference time.
        :return: current ntp timestamp
        """
        if NtpTime.reference_time is None:
            raise MissingNtpReferenceTime("Use NtpTime.initialize to set a reference time.")

        time = milliseconds_since_1970() - NtpTime.reference_time
        sec = int(time/1000)
        frac = int((time - sec*1000)*4294967.296)
        return cls(sec, frac)
