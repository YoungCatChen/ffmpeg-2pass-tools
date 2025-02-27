import gooey
import sys
from typing import Callable, cast


def main():
  parser = gooey.GooeyParser(
      description=('Convert burst shots to a video, then attach the video '
                   'to a still image to make it a Live Photo.'),
      exit_on_error=True)

  parser.add_argument('--images',
                      required=True,
                      help='Images to convert. May include directories.',
                      widget='MultiFileChooser',
                      nargs='+')
  parser.add_argument('--bursts',
                      required=True,
                      help='Burst shots to convert. May include directories.',
                      widget='MultiFileChooser',
                      nargs='+')
  parser.add_argument('--ffargs',
                      required=True,
                      help='Arguments for ffmpeg',
                      widget='Textarea',
                      nargs='+')
  args = parser.parse_args()
  print(args)
  # TODO


if __name__ == '__main__':
  if len(sys.argv) == 1:
    main2 = gooey.Gooey(
        program_name='Burst Shots onto Live Photo',
        optional_cols=1,
        show_restart_button=False,
    )(main)
    main = cast(Callable[[], None], main2)
  # Gooey reruns the script with this parameter for the actual execution.
  # Since we don't use decorator to enable commandline use, remove this parameter
  # and just run the main when in commandline mode.
  if '--ignore-gooey' in sys.argv:
    sys.argv.remove('--ignore-gooey')
  main()
