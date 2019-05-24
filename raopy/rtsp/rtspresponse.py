import re
from ..util import to_unicode


class RTSPResponse(object):
    """
    Parse an rtsp response
    """
    def __init__(self, protocol, protocol_version, code, status):
        self.protocol = protocol
        self.protocol_version = protocol_version
        self.code = code
        self.status = status
        self.headers = {}
        self.body = b""

    @classmethod
    def parse_response_header(cls, response_str):
        """
        Parse the rtps response into a dictionary.
        :param response: received rtsp data
        :return: dictionary with response data
        """
        res_arr = to_unicode(response_str).split("\r\n")
        # check the first line for the response code
        protocol, version, code, status = re.search('(\w+)/(\d+\.\d+)\s(\d+)\s(.*)', res_arr[0]).groups()

        res = cls(protocol, version, int(code), status)
        for header_entry in res_arr[1:]:
            if header_entry:
                key, value = re.search("([^:]+): (.*)", header_entry).groups()
                if key.strip():
                    res.headers[key] = value

        return res

    def __repr__(self):
        s = "{0}/{1} {2} {3}\n".format(self.protocol, self.protocol_version, self.code, self.status)
        s += "\n".join(["{0}: {1}".format(k, v) for k, v in self.headers.items()])
        if self.body:
            try:
                body = to_unicode(self.body)
            except:
                body = str(self.body)
        else:
            body = ""
        return s + "\n" + body