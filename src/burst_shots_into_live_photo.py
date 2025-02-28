import argparse
import dataclasses
import gooey
import os
import re
import sys
from typing import Callable, Collection, Iterable, Sequence, cast

import ffmpeg_2pass_and_exif
import get_ffmpeg_input_flags
import highlight


def main() -> int:
  args = parse_args()
  bursts = scan_for_image_files(args.bursts)
  stills = scan_for_image_files(args.stills)

  if not bursts or not stills:
    print('Error: No files found from bursts or stills.')
    return 2
  if intersection := set(bursts) & set(stills):
    print('Error: Some files are in both bursts and stills:', intersection)
    return 2
  highlight.print(
      f'\nSpecified {len(bursts)} burst shots and {len(stills)} still images.')

  execcmd = highlight.ExecCmd(dry_run=args.dry_run)
  burst_series = BurstSeries.find_all_series(ImageFile(b) for b in bursts)
  highlight.print('\nFound %d burst series. They are: ' % len(burst_series))
  for series in burst_series:
    print(f'{series.path_pattern} - {len(series.images)} images '
          f'({series.first_seq} - {series.last_seq})')
  for series in burst_series:
    series.make_video(args.ffargs, execcmd=execcmd)

  still_dict: dict[int, list[str]] = {}
  for still in stills:
    img = ImageFile(still)
    still_dict.setdefault(img.sequence_num, []).append(still)

  for series in burst_series:
    for burst_image in series.images:
      for still_image in still_dict.get(burst_image.sequence_num, []):
        highlight.print(
            f'\nAttaching {series.video} (from burst shots '
            f'{series.first_seq} - {series.last_seq}) to {still_image} ...')
        # TODO
        pass

  return 0


@dataclasses.dataclass
class Args:
  bursts: list[str]
  stills: list[str]
  dry_run: bool
  ffargs: list[str]


def parse_args() -> Args:
  parser = gooey.GooeyParser(
      description=('Convert burst shots to a video, then attach the video '
                   'to a still image to make it a Live Photo.'),
      exit_on_error=True)

  directory_msg = (
      'If directory(-ies) are included, all images (.jpg, .jpeg, .png, '
      '.heic, .heif, .tif, .tiff) in the directories '
      'will be %s (not including sub-directories).')

  parser.add_argument(
      '--bursts',
      required=True,
      help=('Burst-mode shot images to convert to video(s). '
            'Images whose filenames are in sequence will be treated as '
            'a burst series and converted to a video. '
            'Likewise, images belonging to different sequences '
            'will be converted to separate videos. ' +
            directory_msg % 'processed'),
      widget='MultiFileChooser',
      nargs=argparse.ONE_OR_MORE)

  parser.add_argument(
      '--stills',
      required=True,
      help=('Still image(s) to be attached with the video(s). '
            'Each still image will be checked if its filename belongs '
            'to one of the sequences we found in the video(s). '
            'If so, the video will be attached to the still image '
            'to make this still image a Live Photo. '
            'Otherwise, this still image will be skipped. ' +
            directory_msg % 'checked'),
      widget='MultiFileChooser',
      nargs=argparse.ONE_OR_MORE)

  parser.add_argument(
      '-n',
      '--dry-run',
      action='store_true',
      help=('Do not actually produce any video nor Live Photo. Only print '
            'the commands that would be executed.'))

  parser.add_argument(
      '--ffargs',
      required=True,
      help=('Arguments for ffmpeg. '
            'Example: -c:v libx264 -b:v 2M -preset slow -f mov'),
      widget='Textarea',
      nargs=argparse.REMAINDER)

  args = parser.parse_args()
  # print(args)  # For debugging
  return args


def scan_for_image_files(paths: Iterable[str]) -> list[str]:
  image_exts = ('.jpg', '.jpeg', '.png', '.heic', '.heif', '.tif', '.tiff')
  files = []
  for path in paths:
    if os.path.isdir(path):
      for file in os.listdir(path):
        if file.lower().endswith(image_exts):
          files.append(os.path.join(path, file))
    elif os.path.isfile(path):
      files.append(path)
    else:
      highlight.warn(f'Invalid path: {path} . Does the file/directory exist?')
  return files


class ImageFile:
  path: str
  """The path to the image file."""

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
    matched = re.search(r'(\d{3,})', os.path.basename(path))
    if matched:
      matched_str = matched.group(1)
      self.sequence_num = int(matched_str)
      self.path_pattern = os.path.join(
          os.path.dirname(path),
          os.path.basename(path).replace(matched_str, '*'))
    else:
      self.sequence_num = -1
      self.path_pattern = path


@dataclasses.dataclass
class BurstSeries:
  images: list[ImageFile]
  video: str | None = None

  @property
  def path_pattern(self) -> str:
    assert self.images
    return self.images[0].path_pattern

  @property
  def first_seq(self) -> int:
    assert self.images
    return self.images[0].sequence_num

  @property
  def last_seq(self) -> int:
    assert self.images
    return self.images[-1].sequence_num

  @staticmethod
  def find_all_series(images: Iterable[ImageFile]) -> list['BurstSeries']:
    """Finds all burst series from the given images.

    Only series with 4 or more images will be returned.
    """
    images = sorted(images, key=lambda x: (x.path_pattern, x.sequence_num))
    all_series: list[BurstSeries] = []
    for i, img in enumerate(images):
      if (i == 0 or img.path_pattern != images[i - 1].path_pattern or
          img.sequence_num != images[i - 1].sequence_num + 1):
        all_series.append(BurstSeries([img]))
      else:
        all_series[-1].images.append(img)
    return [series for series in all_series if len(series.images) >= 4]

  def make_video(self,
                 ffmpeg_args: Iterable[str],
                 execcmd: highlight.ExecCmd | None = None) -> None:
    """Converts the images in this burst series to a video."""
    highlight.print(f'\nConverting {self.path_pattern} '
                    f'({len(self.images)} images) to a video...')
    input_flags = get_ffmpeg_input_flags.get_ffmpeg_input_flags(
        [img.path for img in self.images])
    result = ffmpeg_2pass_and_exif.ffmpeg_2pass_and_exif(
        (input_flags + list(ffmpeg_args)), execcmd=execcmd)
    self.video = result.output_path


if __name__ == '__main__':
  if len(sys.argv) == 1:
    main2 = gooey.Gooey(
        program_name='Burst Shots onto Live Photo',
        optional_cols=1,
        show_restart_button=False,
    )(main)
    main = cast(Callable[[], int], main2)
  # Gooey reruns the script with this parameter for the actual execution.
  # Since we don't use decorator to enable commandline use, remove this parameter
  # and just run the main when in commandline mode.
  if '--ignore-gooey' in sys.argv:
    sys.argv.remove('--ignore-gooey')
  sys.exit(main())
