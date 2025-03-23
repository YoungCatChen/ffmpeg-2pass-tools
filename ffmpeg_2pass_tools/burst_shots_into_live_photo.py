import argparse
import dataclasses
from re import I
import gooey
import itertools
import os
import sys
from typing import Iterable

import ffmpeg_2pass_tools.third_party as _
from MotionPhoto2 import Muxer as muxer_lib

from ffmpeg_2pass_tools import ffmpeg_2pass_and_exif
from ffmpeg_2pass_tools import exiftool_utils
from ffmpeg_2pass_tools import get_ffmpeg_input_flags
from ffmpeg_2pass_tools import highlight
from ffmpeg_2pass_tools import image_file


def main() -> int:
  if len(sys.argv) == 1:
    return gooey_main()

  # Gooey reruns the script with this parameter for the actual execution.
  # Since we don't use decorator here to enable commandline use, remove this
  # parameter and just run the main when in commandline mode.
  if '--ignore-gooey' in sys.argv:
    sys.argv.remove('--ignore-gooey')
  return normal_main()


def normal_main() -> int:
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
      f'Specified {len(bursts)} burst shots and {len(stills)} still images.')

  burst_images = [image_file.ImageFile(b) for b in bursts]
  still_images = [image_file.ImageFile(s) for s in stills]

  # Find burst series
  burst_series = BurstSeries.find_all_series(burst_images)
  highlight.print('\nFound %d burst series. They are: ' % len(burst_series))
  for series in burst_series:
    print(f'{series.path_pattern} - {len(series.images)} images '
          f'({series.first_seq} - {series.last_seq})')

  # Make videos
  execcmd = highlight.ExecCmd(dry_run=args.dry_run)
  for series in burst_series:
    series.make_video(args.ffargs, execcmd=execcmd)

  # Attach videos to stills
  attach_videos_to_stills(burst_series, still_images, dry_run=args.dry_run)

  return 0


@gooey.Gooey(
    program_name='Burst Shots onto Live Photo',
    optional_cols=1,
    show_restart_button=False,
)
def gooey_main() -> int:
  return normal_main()


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


@dataclasses.dataclass
class BurstSeries:
  """A series of burst shots.

  Images taken in burst mode are usually named in sequence, and they are considered
  as a series of burst shots.

  Images that are taken more than 1 second apart, even when their filenames
  are in sequence, are considered as different series.
  """

  images: list[image_file.ImageFile]
  video: str | None = None
  video_input_settings: object | None = None

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
  def find_all_series(images: Iterable[image_file.ImageFile],
                      min_num_images: int = 4) -> list['BurstSeries']:
    """Finds all burst series from the given images.

    Only series with `min_num_images` or more images will be returned.
    """
    all_series: list[BurstSeries] = []
    images_by_pattern = itertools.groupby(images, key=lambda x: x.path_pattern)

    for unused_pattern, image_iter in images_by_pattern:
      images = sorted(image_iter, key=lambda x: x.sequence_num)
      for i, img in enumerate(images):
        if (i == 0 or img.sequence_num != images[i - 1].sequence_num + 1 or
            img.time - images[i - 1].time > 1.0):
          all_series.append(BurstSeries([img]))
        else:
          all_series[-1].images.append(img)

    return [s for s in all_series if len(s.images) >= min_num_images]

  def make_video(self, ffmpeg_args: Iterable[str],
                 execcmd: highlight.ExecCmd) -> None:
    """Converts the images in this burst series to a video."""
    highlight.print(f'\nConverting {self.path_pattern} '
                    f'({len(self.images)} images) to a video...')
    input_flags_and_settings = get_ffmpeg_input_flags.get_ffmpeg_input_flags(
        [img.path for img in self.images])
    all_flags = input_flags_and_settings.flags + list(ffmpeg_args)
    result = ffmpeg_2pass_and_exif.ffmpeg_2pass_and_exif(all_flags,
                                                         execcmd=execcmd)
    self.video = result.output_path
    self.video_input_settings = input_flags_and_settings.settings


def attach_videos_to_stills(burst_series: Iterable[BurstSeries],
                            stills: Iterable[image_file.ImageFile],
                            dry_run=False) -> None:
  """Attaches videos to still images to make Live Photos."""
  still_dict: dict[int, list[image_file.ImageFile]] = {}
  for still in stills:
    still_dict.setdefault(still.sequence_num, []).append(still)
  for series in burst_series:
    for burst_image in series.images:
      for still in still_dict.get(burst_image.sequence_num, []):
        attach_video_to_still(series, still, dry_run=dry_run)


def attach_video_to_still(series: BurstSeries,
                          still: image_file.ImageFile,
                          dry_run=False) -> None:
  """Attaches a video to a still image to make a single Live Photo."""
  highlight.print(
      f'\nAttaching {series.video} (from burst shots '
      f'{series.first_seq} - {series.last_seq}) to {still.path} ...')

  assert series.video
  time_offset_sec = 0.0

  if isinstance(series.video_input_settings,
                get_ffmpeg_input_flags.Image2Input):
    image2_input = series.video_input_settings
    time_offset_sec = ((still.sequence_num - series.first_seq + 0.5) /
                       image2_input.framerate)
    time_offset_sec = max(0.0, time_offset_sec)

  print(f"Live photo's time offset: {time_offset_sec} sec")
  if dry_run:
    return

  muxer = muxer_lib.Muxer(
      image_fpath=still.path,
      video_fpath=series.video,
      exiftool=exiftool_utils.singleton(),
      time_offset_sec=time_offset_sec,
  )
  muxer.mux()


if __name__ == '__main__':
  sys.exit(main())
