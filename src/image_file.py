import os
import re

import exiftool_utils


class ImageFile:
  path: str
  """The path to the image file."""

  _time: float | None = None
  """The time of the image file taken in seconds since the epoch."""

  sequence_num: int
  """The sequence number from the filename.

  The last number that has 3+ digits are considered as the sequence number.
  e.g. IMG_123.jpg's sequence number is 123, and IMG_123-1.jpg's is still 123.
  Any number from the directory name is not considered as the sequence number.
  e.g. /path/to/456/IMG_123.jpg's sequence number is 123, not 456.
  If no sequence is found, it's set to -1.
  """

  path_pattern: str
  """The glob pattern of the path, excluding the sequence number.

  e.g. /path/to/456/IMG_123.jpg's path_pattern is /path/to/456/IMG_*.jpg.
  """

  def __init__(self, path: str):
    self.path = path
    self.sequence_num, self.path_pattern = self.get_sequence_and_pattern(path)

  @property
  def time(self) -> float:
    if self._time is None:
      self._time = exiftool_utils.get_time(self.path)
    return self._time

  @staticmethod
  def get_sequence_and_pattern(path: str) -> tuple[int, str]:
    matched = re.search(r'(\d{3,})', os.path.basename(path))
    if matched:
      matched_str = matched.group(1)
      number_format = f'%0{len(matched_str)}d'
      return int(matched_str), os.path.join(
          os.path.dirname(path),
          os.path.basename(path).replace(matched_str, number_format))
    return -1, path


class TestImageFile(ImageFile):

  def __init__(self, path, time):
    super().__init__(path)
    self._time = time
