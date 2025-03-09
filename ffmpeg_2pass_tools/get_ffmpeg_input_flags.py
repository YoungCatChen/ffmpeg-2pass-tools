#!/usr/bin/env python3

import enum
import re
import sys
import tempfile
from typing import IO, Sequence

from ffmpeg_2pass_tools import exiftool_utils
from ffmpeg_2pass_tools import image_file


class ColorSpace(enum.Enum):
  UNKNOWN = 0
  SRGB = 1
  P3 = 2

  @property
  def flags_for_input(self) -> list[str]:
    if self not in {self.SRGB, self.P3}:
      return []
    flags = ['-colorspace', 'bt709', '-color_primaries']
    flags.append('bt709' if self == self.SRGB else 'smpte432')
    flags += ['-color_trc', 'iec61966-2-1']
    return flags

  @property
  def flags_for_output(self) -> list[str]:
    if self in {self.SRGB, self.P3}:
      return ['-colorspace', 'bt709']
    else:
      return []

  @classmethod
  def guess(cls, fname: str) -> 'ColorSpace':
    try:
      result = exiftool_utils.singleton().execute('-q', '-printFormat',
                                                  '$ProfileDescription', fname)
      result = str(result)
      if 'sRGB' in result:
        return cls.SRGB
      elif 'P3' in result:
        return cls.P3
    except FileNotFoundError:
      pass
    return cls.UNKNOWN


class Image2Input:
  start: int
  num_frames: int
  pattern: str
  framerate: int

  def __init__(self, files: Sequence[str]):
    assert files
    assert len(files) >= 2
    self.start, self.pattern = (image_file.ImageFile.get_sequence_and_pattern(
        files[0]))
    last_seq, last_pattern = image_file.ImageFile.get_sequence_and_pattern(
        files[-1])
    assert self.pattern == last_pattern
    assert last_seq > self.start
    self.num_frames = last_seq - self.start + 1
    self.framerate = self.guess_framerate(files)

  @property
  def flags(self) -> list[str]:
    return [
        '-f',
        'image2',
        '-r',
        str(self.framerate),
        '-start_number',
        str(self.start),
        '-i',
        self.pattern,
        '-frames:v',
        str(self.num_frames),
    ]

  @staticmethod
  def guess_framerate(files: Sequence[str]) -> int:
    if len(files) < 2:
      return 10

    try:
      time1 = exiftool_utils.get_time(files[0])
      time2 = exiftool_utils.get_time(files[-1])
    except:
      return 10
    if time2 <= time1:
      return 10

    fr = 1.0 / ((time2 - time1) / (len(files) - 1))
    # print(f'@@@ framerate:', fr)
    fr = round(fr)

    mapping = [
        [-1, 1],  # example: if -1 <= fr < 1, return 1
        [1, fr],
        [7, 8],
        [9, 10],
        [11, 12],  # example: if 11 <= fr < 14, return 12
        [14, 15],
        [18, 20],
        [23, 25],
        [27, 30],
        [45, 30],
    ]

    for i in range(1, len(mapping)):
      if fr <= mapping[i][0]:
        return mapping[i - 1][1]
    return 60


class ConcatInput:
  playlist: list[tuple[str, float]]  # path and duration
  _tmp_path: str = ''

  def __init__(self, files: Sequence[str]):
    self.playlist = []

    exif_result = exiftool_utils.singleton().execute(
        '-q', '-dateFormat', '%s', '-printFormat',
        '$FilePath /// $DateTimeOriginal.$SubSecTimeOriginal', *files)

    paths_and_times = [(parts[0], float(parts[1]))
                       for line in str(exif_result).strip().split('\n')
                       if (parts := line.split(' /// ')) and len(parts) == 2]
    assert len(paths_and_times) >= 2

    for i in range(len(paths_and_times) - 1):
      path, time = paths_and_times[i]
      _, next_time = paths_and_times[i + 1]
      duration = round(max(next_time - time, 1 / 60), 6)
      self.playlist.append((path, duration))

    self.playlist.append((paths_and_times[-1][0], self.playlist[-1][1]))

  @property
  def flags(self) -> list[str]:
    if not self._tmp_path:
      with tempfile.NamedTemporaryFile(delete=False,
                                       mode='wt',
                                       prefix='get_ffmpeg_input_flags.',
                                       suffix='.tmp') as tmp_file:
        self._tmp_path = tmp_file.name
        self._write_playlist(tmp_file)
    return ['-f', 'concat', '-safe', '0', '-i', self._tmp_path]

  def _write_playlist(self, opened_file: IO[str]):
    for path, duration in self.playlist:
      opened_file.write(f"file '{path}'\n")
      opened_file.write(f"duration {duration}\n")
    opened_file.write(f"file '{self.playlist[-1][0]}'\n")


def is_video(fname: str) -> bool:
  return bool(re.search(r'\.(mp4|m4v|mov|avi|webm)$', fname, re.IGNORECASE))


def get_ffmpeg_input_flags(files: Sequence[str]) -> list[str]:
  if not files:
    raise ValueError('No input files.')
  if is_video(files[0]):
    return ['-i', files[0]]

  space = ColorSpace.guess(files[0])
  flags = space.flags_for_input
  if len(files) == 1:
    flags += ['-i', files[0]]
  else:
    input_settings = Image2Input(files)
    # input_settings = ConcatInput(files)
    flags += input_settings.flags
  flags += space.flags_for_output
  return flags


def main(argv: Sequence[str]) -> int:
  files = argv[1:]
  flags = get_ffmpeg_input_flags(files)
  if not flags:
    return 2
  print('\n'.join(flags))
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))
