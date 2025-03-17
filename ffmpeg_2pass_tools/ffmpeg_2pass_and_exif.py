#!/usr/bin/env python3

import dataclasses
import glob
import os
import re
import sys
from typing import Iterable

from ffmpeg_2pass_tools import highlight


@dataclasses.dataclass
class PositionedArgument:
  val: str
  pos: int


class CommandProcessor:
  """Processes the command line arguments for ffmpeg."""
  args: list[str]

  def __init__(self, args: Iterable[str] | None = None) -> None:
    self.args = list(args) if args else sys.argv[1:]

  def find_arg_position(self,
                        regex: str | re.Pattern,
                        backwards=False) -> int | None:
    """Finds the position of an argument that matches a specific regex."""
    if isinstance(regex, str):
      regex = re.compile(regex)
    rang = range(len(self.args) - 1)
    if backwards:
      rang = range(len(self.args) - 2, -1, -1)
    for i in rang:
      if regex.fullmatch(self.args[i]):
        return i
    return None

  def find_arg_after(self,
                     regex: str | re.Pattern,
                     backwards=False) -> PositionedArgument | None:
    """Finds the argument immediately after a specific regex."""
    pos = self.find_arg_position(regex, backwards)
    if pos is None:
      return None
    return PositionedArgument(val=self.args[pos + 1], pos=pos + 1)

  def find_bitrate(self) -> str | None:
    """Finds the bitrate for video from the command line arguments."""
    bv_arg = self.find_arg_after('-b:v')
    return bv_arg.val if bv_arg else None

  def find_encoder(self) -> str | None:
    """Finds the encoder for video from the command line arguments."""
    cv_arg = self.find_arg_after('-c:v')
    return cv_arg.val if cv_arg else None

  def find_x265_params(self) -> str | None:
    """Finds the encoder for video from the command line arguments."""
    arg = self.find_arg_after('-x265-params')
    return arg.val if arg else None

  def find_output_format(self) -> str | None:
    """Finds the output file format from the command line arguments."""
    f_arg = self.find_arg_after('-f', backwards=True)
    i_arg = self.find_arg_after('-i')
    if f_arg and i_arg and f_arg.pos > i_arg.pos:
      return f_arg.val
    return None

  def find_output(self) -> str | None:
    """Finds the output file from the command line arguments.

    It works if the output ends with .mp4 or .mov; mistakes can occur if there
    is any side input video doesn't come with `-i`.
    """
    regex = re.compile(r'\.(mov|mp4)$', re.IGNORECASE)
    for i in range(len(self.args) - 1, -1, -1):
      if regex.findall(self.args[i]):
        return self.args[i] if self.args[i - 1] != '-i' else None
    return None

  def find_one_input(self) -> str | None:
    """Finds the input file after the `-i` argument.

    If the input file is a media file, it will return the file name directly.

    If the input file looks like a printf pattern with a `%`, for example
    `ABC%2d.jpg`, it will find the **last** file that matches `ABC??.jpg`.

    If the input is a text file used by the `-f concat` option, it will return
    the **last** file in the list.
    """
    i_arg = self.find_arg_after('-i')
    if not i_arg:
      return None
    f_arg = self.find_arg_after('-f')
    if f_arg and f_arg.val == 'image2':
      if one_input := self._find_one_input_from_image2(i_arg.val):
        return one_input
    if f_arg and f_arg.val == 'concat':
      if one_input := self._find_one_input_from_concat(i_arg.val):
        return one_input
    return i_arg.val

  def _find_one_input_from_image2(self, printf_pattern: str) -> str | None:
    """Finds the last file that matches a printf pattern.

    If the input specification looks like a printf pattern with a `%`, for
    example `ABC%2d.jpg`, it will find the **last** file that matches
    `ABC??.jpg`, but not pass `-frames:v` frames (if specified).
    """
    start_number = self._find_start_number(printf_pattern)
    print('start_number: ', start_number)
    if start_number is None:
      return None
    max_frames = 1_000_000
    if arg:= self.find_arg_after('-frames:v'):
      max_frames = int(arg.val)
    num = -1
    for num in range(start_number, start_number + max_frames):
      path = printf_pattern % num
      if not os.path.exists(path):
        num -= 1
        break
    return printf_pattern % num

  def _find_start_number(self, printf_pattern: str) -> int | None:
    """Finds the start number for a printf pattern."""
    attempts = [0, 1, 2, 3, 4]
    if arg := self.find_arg_after('-start_number'):
      attempts.insert(0, int(arg.val))
    for num in attempts:
      path_attempt = printf_pattern % num
      if os.path.exists(path_attempt):
        return num
    return None

  @staticmethod
  def _find_one_input_from_concat(playlist_path: str) -> str | None:
    """Finds the last video file in a playlist file."""
    with open(playlist_path, 'rt') as f:
      lines = f.readlines()
    for i in range(len(lines) - 1, -1, -1):
      matches = re.findall("file '(.+)'", lines[i])
      if matches:
        return matches[0]
    return None


class CommandlineArgumentError(Exception):
  pass


@dataclasses.dataclass
class Result:
  bitrate: str | None
  encoder: str
  output_path: str


def ffmpeg_2pass_and_exif(args: Iterable[str] | None = None,
                          execcmd: highlight.ExecCmd | None = None) -> Result:
  execcmd = execcmd or highlight.ExecCmd()
  cp = CommandProcessor(args)
  one_input = cp.find_one_input()
  output_spec = cp.find_output()
  output_format = cp.find_output_format() or 'mp4'
  bitrate = cp.find_bitrate()
  encoder = cp.find_encoder()

  # checks.
  if not one_input:
    raise CommandlineArgumentError(
        'Cannot find input file/pattern after an `-i` argument.')

  if output_spec:
    raise CommandlineArgumentError(
        f'Output file `{output_spec}` is detected from the '
        'arguments. The output file name will be determined by '
        'input file and bitrate etc. and must not be specified '
        'manually.')

  if encoder not in ['libx264', 'libx265']:
    raise CommandlineArgumentError(
        'Cannot find video encoder after an `-c:v` argument, or '
        'the encoder specified is not either libx264 or '
        'libx265.')

  if encoder == 'libx265':
    tag_arg = cp.find_arg_after('-tag:v')
    if not tag_arg or tag_arg.val != 'hvc1':
      raise CommandlineArgumentError(
          'libx265 is specified as video encoder but '
          '`-tag:v hvc1` is not specified. The resulting video '
          'will have issue in playing.')

  # assemble the output path.
  output_path = os.path.splitext(one_input)[0] + '.' + encoder.replace(
      'lib', '')
  if bitrate:
    output_path += f'.{bitrate}bps'
  output_path += '.' + output_format

  # run the commands.
  cmd = ['ffmpeg', '-nostdin', '-hide_banner'] + cp.args

  if encoder == 'libx264':
    execcmd.run(cmd + '-map -0? -map 0:v -pass 1 -f null /dev/null'.split(' '))
    execcmd.run(cmd + ['-pass', '2', output_path])
  else:
    x265_params = cp.find_x265_params() or ''
    execcmd.run(
        cmd +
        f'-map -0? -map 0:v -x265-params pass=1:{x265_params} -f null /dev/null'
        .split(' '))
    execcmd.run(cmd + ['-x265-params', f'pass=2:{x265_params}', output_path])

  execcmd.run([
      'exiftool', '-tagsFromFile', one_input, '-overwrite_original', output_path
  ])

  return Result(bitrate=bitrate, encoder=encoder, output_path=output_path)


def main() -> int:
  dry_run = '-n' in sys.argv
  try:
    ffmpeg_2pass_and_exif(sys.argv[1:], execcmd=highlight.ExecCmd(dry_run))
    return 0
  except CommandlineArgumentError as e:
    sys.stderr.write(f'Error: {e}\nExiting.\n')
    return 2


if __name__ == '__main__':
  sys.exit(main())
