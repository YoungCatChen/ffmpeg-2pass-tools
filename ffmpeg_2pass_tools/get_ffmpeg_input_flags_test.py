import exiftool
from parameterized import param, parameterized
import tempfile
from typing import Sequence
import unittest
from unittest import mock

from ffmpeg_2pass_tools import exiftool_utils
from ffmpeg_2pass_tools import get_ffmpeg_input_flags


class TestImage2Input(get_ffmpeg_input_flags.Image2Input):

  def __init__(self, pattern: str, framerate: int, start: int, num_frames: int):
    self.pattern = pattern
    self.framerate = framerate
    self.start = start
    self.num_frames = num_frames


class TestConcatInput(get_ffmpeg_input_flags.ConcatInput):

  def __init__(self, playlist: list[tuple[str, float]]):
    self.playlist = playlist


class Image2InputTest(unittest.TestCase):

  def test_flags(self):
    image2_input = TestImage2Input('%2d.jpg', 8, 12, 34)
    self.assertEqual(' '.join(image2_input.flags),
                     '-f image2 -r 8 -start_number 12 -i %2d.jpg -frames:v 34')

  @parameterized.expand([
      ('Short 1fps', [100, 101], 1),
      ('Short 4fps', [100, 100.25], 4),
      ('Longer', [100, 100.25, 100.5, 100.75, 101], 4),
      ('Uneven Time', [100, 100.25, 100.5, 100.75, 100.76], 5),
      ('Round 19 To 20', [100, 100.051], 20),
      ('Min At 1', [100, 110], 1),
      ('Max At 60', [100, 100.00001], 60),
      ('Default 10 For Wrong Order', [100, 99], 10),
      ('Default 10 For One File', [100], 10),
      ('Default 10 For No File', [], 10),
  ])
  @mock.patch.object(exiftool_utils, 'get_time')
  def test_guess_framerate(self, _, timestamps: Sequence[float],
                           expected_framerate: float, get_time_func):
    get_time_func.side_effect = lambda filepath: float(filepath)
    filenames = [str(ts) for ts in timestamps]
    self.assertEqual(
        get_ffmpeg_input_flags.Image2Input.guess_framerate(filenames),
        expected_framerate)

  def test_constructor__not_enough_files(self):
    with self.assertRaises(Exception):
      get_ffmpeg_input_flags.Image2Input([])
    with self.assertRaises(Exception):
      get_ffmpeg_input_flags.Image2Input(['single_file'])

  def test_constructor__no_pattern_found(self):
    with self.assertRaises(Exception):
      get_ffmpeg_input_flags.Image2Input(['1.jpg', '2.jpg', '3.jpg'])


class ConcatInputTest(unittest.TestCase):

  @parameterized.expand([
      param('Simple',
            exif_info=['file1 /// 100', 'file2 /// 100.1'],
            expected=[('file1', 0.1), ('file2', 0.1)]),
      param('Simple',
            exif_info=['file1 /// 100', 'file2 /// 100.1', 'file3 /// 100.3'],
            expected=[('file1', 0.1), ('file2', 0.2), ('file3', 0.2)]),
      param('Min Duration 1/60',
            exif_info=['file1 /// 100', 'file2 /// 100.00001'],
            expected=[('file1', 0.016667), ('file2', 0.016667)]),
      param('Wrong Order',
            exif_info=['file1 /// 100', 'file2 /// 99.9'],
            expected=[('file1', 0.016667), ('file2', 0.016667)]),
      param('Directory and Space in Path',
            exif_info=['dir/file1 (1) /// 100', 'dir/file2 (1) /// 100.1'],
            expected=[('dir/file1 (1)', 0.1), ('dir/file2 (1)', 0.1)]),
  ])
  @mock.patch.object(exiftool.ExifToolHelper, 'execute')
  def test_constructor(self, _, execute_func, exif_info=None, expected=None):
    execute_func.return_value = '\n'.join(exif_info or [])
    concat_input = get_ffmpeg_input_flags.ConcatInput(['dummy1', 'dummy2'])
    self.assertEqual(concat_input.playlist, expected)

  @mock.patch.object(exiftool.ExifToolHelper, 'execute')
  def test_constructor__not_enough_files(self, execute_func):
    execute_func.return_value = ''
    with self.assertRaises(Exception):
      get_ffmpeg_input_flags.ConcatInput(['dummy1', 'dummy2'])
    execute_func.return_value = 'file1 /// 100'
    with self.assertRaises(Exception):
      get_ffmpeg_input_flags.ConcatInput(['dummy1', 'dummy2'])

  def test_flags(self):
    with tempfile.TemporaryFile(mode='wt') as tmp_file:
      with mock.patch.object(tempfile,
                             'NamedTemporaryFile',
                             return_value=tmp_file):
        concat_input = TestConcatInput([('file1', 0.1), ('file2', 0.2)])
        self.assertEqual(concat_input.flags,
                         ['-f', 'concat', '-safe', '0', '-i', tmp_file.name])

  def test_write_playlist(self):
    with tempfile.TemporaryFile(mode='w+t') as tmp_file:
      concat_input = TestConcatInput([('file1', 0.1), ('file2', 0.2)])
      concat_input._write_playlist(tmp_file)
      tmp_file.seek(0)
      self.assertEqual(tmp_file.read(), ("file 'file1'\nduration 0.1\n"
                                         "file 'file2'\nduration 0.2\n"
                                         "file 'file2'\n"))


if __name__ == '__main__':
  unittest.main()
