#!/usr/bin/env python3

import dataclasses
import glob
import os
import re
import subprocess
import sys
from typing import Sequence


@dataclasses.dataclass
class PositionedArgument:
  val: str
  pos: int


class CommandProcessor:
  """Processes the command line arguments for ffmpeg."""
  args: list[str]

  def __init__(self) -> None:
    self.args = sys.argv[1:]

  def find_arg_after(self,
                     regex: str | re.Pattern,
                     backwards=False) -> PositionedArgument | None:
    """Finds the argument immediately after a specific regex."""
    if isinstance(regex, str):
      regex = re.compile(regex)
    rang = range(len(self.args) - 1)
    if backwards:
      rang = range(len(self.args) - 2, -1, -1)
    for i in rang:
      if regex.fullmatch(self.args[i]):
        return PositionedArgument(val=self.args[i + 1], pos=i + 1)
    return None

  def find_bitrate(self) -> str | None:
    """Finds the bitrate for video from the command line arguments."""
    bv_arg = self.find_arg_after('-b:v')
    return bv_arg.val if bv_arg else None

  def find_encoder(self) -> str | None:
    """Finds the encoder for video from the command line arguments."""
    cv_arg = self.find_arg_after('-c:v')
    return cv_arg.val if cv_arg else None

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

  def find_input(self) -> str | None:
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

    if '%' in i_arg.val:
      # now this is a printf pattern. Convert it into a glob pattern.
      regex = r'%(\d+)d'

      def replace_match(match):
        width = int(match.group(1))
        return '?' * width

      glob_pattern = re.sub(regex, replace_match, i_arg.val)

      # find all files and return the last one.
      files = glob.glob(glob_pattern)
      files.sort()
      return files[-1] if files else None

    f_arg = self.find_arg_after('-f', backwards=True)
    if f_arg and f_arg.val == 'concat':
      # this is a text file used by the `-f concat` option. Read the list.
      with open(i_arg.val, 'rt') as f:
        lines = f.readlines()
      for i in range(len(lines) - 1, -1, -1):
        matches = re.findall("file '(.+)'", lines[i])
        if matches:
          return matches[0]

    # Otherwise, assume this is a media file. Return it as-is.
    return i_arg.val


class ExecCmd:
  """Prints and runs a command."""

  def __init__(self, dry_run=False):
    self.dry_run = dry_run

  def run(self, cmd: Sequence[str]) -> None:
    print('\n\033[1;36m' + ' '.join(cmd) + '\033[0m')
    if not self.dry_run:
      try:
        result = subprocess.run(cmd)
      except KeyboardInterrupt:
        exit(130)
      if result.returncode != 0:
        exit(result.returncode)


def main():
  cp = CommandProcessor()
  input = cp.find_input()
  output_spec = cp.find_output()
  output_format = cp.find_output_format() or 'mp4'
  bitrate = cp.find_bitrate()
  encoder = cp.find_encoder()
  dry_run = '-n' in cp.args

  # checks.
  if not input:
    sys.stderr.write('Cannot find input file/pattern after an `-i` argument. ' +
                     'Exiting.\n')
    exit(1)

  if output_spec:
    sys.stderr.write(f'Output file `{output_spec}` is detected from the ' +
                     'arguments. The output file name will be determined by ' +
                     'input file and bitrate etc. and must not be specified ' +
                     'manually. Exiting.\n')
    exit(1)

  if encoder not in ['libx264', 'libx265']:
    sys.stderr.write('Cannot find video encoder after an `-c:v` argument, or ' +
                     'the encoder specified is not either libx264 or ' +
                     'libx265. Exiting.\n')
    exit(1)

  if encoder == 'libx265':
    tag_arg = cp.find_arg_after('-tag:v')
    if not tag_arg or tag_arg.val != 'hvc1':
      sys.stderr.write('libx265 is specified as video encoder but ' +
                       '`-tag:v hvc1` is not specified. The resulting video ' +
                       'will have issue in playing. Exiting.\n')
      exit(1)

  # assemble the output path.
  output_path = os.path.splitext(input)[0] + '.' + encoder.replace('lib', '')
  if bitrate:
    output_path += f'.{bitrate}bps'
  output_path += '.' + output_format

  # run the commands.
  execcmd = ExecCmd(dry_run)
  os.nice(10)
  cmd = ['ffmpeg', '-nostdin', '-hide_banner'] + cp.args

  if encoder == 'libx264':
    execcmd.run(cmd + '-map -0? -map 0:v -pass 1 -f null /dev/null'.split(' '))
    execcmd.run(cmd + ['-pass', '2', output_path])
  else:
    execcmd.run(
        cmd +
        '-map -0? -map 0:v -x265-params pass=1 -f null /dev/null'.split(' '))
    execcmd.run(cmd + ['-x265-params', 'pass=2', output_path])

  execcmd.run(
      ['exiftool', '-tagsFromFile', input, '-overwrite_original', output_path])


if __name__ == '__main__':
  main()
