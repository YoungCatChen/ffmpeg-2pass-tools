#!/usr/bin/env python3

import enum
import exiftool
import re
import sys
import tempfile
from typing import Sequence

exiftool_helper = exiftool.ExifToolHelper(common_args=[])


class ColorSpace(enum.Enum):
  UNKNOWN = 0
  SRGB = 1
  P3 = 2

  @classmethod
  def guess(cls, fname: str) -> 'ColorSpace':
    try:
      result = exiftool_helper.execute('-q', '-printFormat',
                                       '$ProfileDescription', fname)
      result = str(result)
      if 'sRGB' in result:
        return cls.SRGB
      elif 'P3' in result:
        return cls.P3
    except FileNotFoundError:
      pass
    return cls.UNKNOWN


def print_colorspace_for_input(space: ColorSpace) -> None:
  if space in {ColorSpace.SRGB, ColorSpace.P3}:
    print('-colorspace\nbt709\n-color_primaries')
    print('bt709' if space == ColorSpace.SRGB else 'smpte432')
    print('-color_trc\niec61966-2-1')


def print_colorspace_for_output(space: ColorSpace) -> None:
  if space in {ColorSpace.SRGB, ColorSpace.P3}:
    print('-colorspace\nbt709')


def get_time(fname: str) -> float:
  result = exiftool_helper.execute(fname, '-dateFormat', '%s', '-printFormat',
                                   '$DateTimeOriginal.$SubSecTimeOriginal')
  result = result.strip()
  return float(result) if result else 0.0


def guess_framerate(files: Sequence[str]) -> int:
  if len(files) < 2:
    return 10

  try:
    time1 = get_time(files[0])
    time2 = get_time(files[-1])
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
      [45, 30]
  ]

  for i in range(1, len(mapping)):
    if fr <= mapping[i][0]:
      return mapping[i - 1][1]
  return 60


def process_multiple_image_inputs_using_framerate(files: Sequence[str]) -> None:
  file = files[0]
  matches = re.findall(r'(\d\d+)(\D+)$', file)
  if not matches:
    return
  start, rest = matches[0]
  num_len = len(start)
  pattern = file.replace(start + rest, f'%0{num_len}d{rest}')
  framerate = guess_framerate(files)
  print(f'-f\nimage2\n-r\n{framerate}\n-start_number\n{start}\n-i\n{pattern}')


def process_multiple_image_inputs_using_concat(argv: Sequence[str]) -> None:
  result = exiftool_helper.execute(
      '-q', '-dateFormat', '%s', '-printFormat',
      '$FilePath /// $DateTimeOriginal.$SubSecTimeOriginal', *argv)

  paths_and_times = str(result).strip().split('\n')
  file_path = None
  last_time = None
  last_duration = 1 / 60

  with tempfile.NamedTemporaryFile(delete=False,
                                   mode='wt',
                                   prefix='get_ffmpeg_input_flags.',
                                   suffix='.tmp') as tmp_file:
    tmp_path = tmp_file.name

    for line in paths_and_times:
      parts = line.split(' /// ')
      if len(parts) != 2:
        continue
      file_path, time_str = parts
      try:
        time_val = float(time_str)
      except ValueError:
        continue

      if last_time:
        last_duration = round(max(time_val - last_time, 1 / 60), 6)
        tmp_file.write(f"duration {last_duration}\n")

      tmp_file.write(f"file '{file_path}'\n")
      last_time = time_val

    if last_time and file_path:
      tmp_file.write(f"duration {last_duration}\n")
      tmp_file.write(f"file '{file_path}'\n")

  print("-f")
  print("concat")
  print("-safe")
  print("0")
  print("-i")
  print(tmp_path)


def is_video(fname: str) -> bool:
  return bool(re.search(r'\.(mp4|m4v|mov|avi|webm)$', fname, re.IGNORECASE))


def main(argv: Sequence[str]) -> int:
  files = argv[1:]
  if not files:
    return 1
  if is_video(files[0]):
    print('-i\n' + files[0])
    return 0

  space = ColorSpace.guess(files[0])
  print_colorspace_for_input(space)
  if len(files) == 1:
    print('-i\n' + files[0])
  else:
    process_multiple_image_inputs_using_framerate(files)
    # process_multiple_image_inputs_using_concat(files)
  print_colorspace_for_output(space)
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))
