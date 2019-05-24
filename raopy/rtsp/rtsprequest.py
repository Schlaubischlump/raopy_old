from hashlib import md5
from collections import namedtuple
from ..util import to_bytes, to_unicode

DigestInfo = namedtuple("DigestInfo", ["username", "realm", "password", "nonce"])


class RTSPRequest(object):
    def __init__(self, uri, method, header, body=None, digest_info=None):
        """
        Convert a header dictionary to bytes which can be send using a socket.
        :param uri: receiver uri
        :param method: method to send (RTSPStatus)
        :param headers: dictionary containing the header information
        :param body: body data
        :param digest_info: DigestInfo tuple for authentication
        """
        # create header
        h = to_bytes("{0} {1} RTSP/1.0\r\n".format(str(method), uri))
        for key, value in header.items():
            h += to_bytes(key) + b": " + to_bytes(value) + b"\r\n"

        # append digest information if the airplay communication requires a password
        if digest_info:
            user, realm, pwd, nonce, = digest_info.username, digest_info.realm, digest_info.password, digest_info.nonce
            ha1 = md5("{0}:{1}:{2}".format(user, realm, pwd).encode('utf-8')).hexdigest()
            ha2 = md5("{0}:{1}".format(str(method), uri).encode('utf-8')).hexdigest()
            di_response = md5("{0}:{1}:{2}".format(ha1, nonce, ha2).encode('utf-8')).hexdigest()

            h += to_bytes('Authorization: Digest username="{0}", realm="{1}", nonce="{2}", uri="{3}", response="{4}"'
                          '\r\n'.format(user, realm, nonce, uri, di_response))

        # create body
        self._body = b""

        if body:
            self._body = to_bytes(body)
            # add Content-Length field to header
            h += to_bytes("Content-Length: {0} \r\n".format(len(self._body)))

        self._head = h

    def to_data(self):
        return self._head + b"\r\n" + self._body

    def __repr__(self):
        if self._body:
            try:
                body = to_unicode(self._body)
            except:
                body = str(self._body)
        else:
            body = ""
        return to_unicode(self._head.replace(b"\r\n", b"\n"))+body
