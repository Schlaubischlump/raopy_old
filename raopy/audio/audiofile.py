import os

import audiotools
from audiotools.pcm import FrameList, empty_framelist
from audiotools.pcmconverter import BufferedPCMReader

from ..config import FRAMES_PER_PACKET
from ..exceptions import UnsupportedFileType


class AudioFile(object):
    def __init__(self, file_path):
        """
        :param file_path: path to audio file
        """
        # check if the file format is supported
        if not os.path.isfile(file_path):
            raise ValueError("Could not find file {0}".format(file_path))

        with open(file_path, "rb") as f:
            supported = audiotools.file_type(f) in audiotools.AVAILABLE_TYPES
            if not supported:
                raise UnsupportedFileType("File format not supported.")

        # open the audiofile and extract the pcm stream
        self.file = audiotools.open(file_path)
        if not self.file.supports_to_pcm():
            raise UnsupportedFileType("Can not extract the pcm stream.")

        # is the file seekable
        self.seekable = self.file.seekable()
        # the total number of frames in this file
        self._num_frames = self.file.total_frames()

        # create a pcm reader
        pcm = self.file.to_pcm()
        if self.seekable:
            self._pcm = pcm
        else:
            # load the whole file into memory if seeking is not available
            self._data = self._load(pcm)
            # Todo: just for debugging
            self._num_frames = len(self._data)

        # save the last frame number
        self._next_frame_number = 0

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
        # Todo: debug to shorten the music file
        i = 0
        while frame_list.frames != 0:# and i < 1025:
            data.append(frame_list.to_bytes(False, True))
            frame_list = reader.read(FRAMES_PER_PACKET)
            i += 1

        return data

    def _seek(self, frame_number):
        """
        Seek to a specific frame.
        :param frame_number: number of the frame.
        """
        self._next_frame_number = min(max(frame_number, 0), self.total_frames)

        if self.seekable:
            self._pcm.seek(frame_number)

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

            self._next_frame_number += 1
            return frame_list.to_bytes(False, True)
        else:
            # reached the end of the frame_list
            if self._next_frame_number >= len(self._data):
                return None

            frame_data = self._data[self._next_frame_number]
            self._next_frame_number += 1
            return frame_data

    @property
    def total_frames(self):
        """
        :return: The total number of frames in the audio file.
        """
        return self._num_frames

    def get_frame(self, frame_number):
        """
        Get the pcm frame data at the given number from the framelist.
        :param frame_number: frame number
        :return: frame data in bytes
        """
        # play silence if the frame number is smaller than 0
        if frame_number < 0:
            return b"\x00"*self.file.channels()*(self.file.bits_per_sample()//8)

        if frame_number == self._next_frame_number:
            return self._next_frame()

        # seek to the correct frame
        self._seek(frame_number)
        return self._next_frame()

    def supports_metadata(self):
        """
        :return: True if the metadata can be extracted, False otherwise
        """
        return self.file.supports_metadata()