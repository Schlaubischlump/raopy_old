import audiotools
from audiotools.pcm import FrameList
from audiotools.pcmconverter import BufferedPCMReader

from ..config import FRAMES_PER_PACKET
from ..exceptions import UnsupportedFileType


class AudioFile(object):
    def __init__(self, file_path):
        """
        :param file_path: path to audio file
        """
        # check if the file format is supported
        with open(file_path, "rb") as f:
            supported = audiotools.file_type(f) in audiotools.AVAILABLE_TYPES
            if not supported:
                raise UnsupportedFileType()

        # open the audiofile and extract the pcm stream
        self.file = audiotools.open(file_path)
        if not self.file.supports_to_pcm():
            raise UnsupportedFileType()

        # is the file seekable
        self.seekable = self.file.seekable()

        # create a pcm reader
        pcm = self.file.to_pcm()
        if self.seekable:
            self._pcm = pcm
        else:
            # load the whole file into memory if seeking is not available
            self._data = self._load(pcm)

        # save the last frame number
        self._last_frame = 0

    def _load(self, pcm):
        """
        If the backend for this file type supports seeking, do nothing. Otherwise try to load the whole file into
        memory. (If you have a better idea let me know...)
        :param pcm: pcmreader instance
        """
        if self.seekable:
            return

        # stores all frames as binary data in a list
        data = []
        reader = BufferedPCMReader(pcm)

        frame_list = reader.read(FRAMES_PER_PACKET)
        while frame_list.frames != 0:
            data.append(frame_list.to_bytes(False, True))
            frame_list = reader.read(FRAMES_PER_PACKET)

        return data

    def _seek(self, frame_number):
        """
        Seek to a specific frame.
        :param frame_number: number of the frame.
        """
        self._last_frame = max(frame_number, 0)
        if self.seekable:
            self._pcm.seek(frame_number)
        else:
            self._last_frame = min(self._last_frame, len(self._data))

    def _next_frame(self):
        """
        Return the next frame.
        """
        if self.seekable:
            # read the right amount of data (See: BufferedPCMReader_read)
            frame_list = FrameList(self._pcm, self._pcm.channels, self._pcm.bits_per_sample, FRAMES_PER_PACKET);
            frames_read = self._pcm.read(FRAMES_PER_PACKET)
            frame_list.frames = frames_read

            # reached the end of the stream
            if frame_list.frames == 0:
                return None

            self._last_frame += 1
            return frame_list.to_bytes(False, True)
        else:
            # reached the end of the frame_list
            if self._last_frame >= len(self._data):
                return None

            self._last_frame += 1
            return self._data[self._last_frame]

    def get_frame(self, frame_number):
        """
        Get the pcm frame data at the given number from the framelist.
        :param frame_number: frame number
        :return: frame data in bytes
        """
        if frame_number == self._last_frame:
            return self._next_frame()

        # seek to the correct frame
        self._seek(frame_number)
        return self._next_frame()

    def supports_metadata(self):
        """
        :return: True if the metadata can be extracted, False otherwise
        """
        return self.file.supports_metadata()