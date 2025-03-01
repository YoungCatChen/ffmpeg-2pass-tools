from parameterized import parameterized
import unittest

import burst_shots_into_live_photo


class ImageFileTest(unittest.TestCase):

  @parameterized.expand([
      ('Simple1', 'IMG_0001.jpg', 1, 'IMG_*.jpg'),
      ('Simple2', 'IMG_002.jpg', 2, 'IMG_*.jpg'),
      ('DuplicatedFile', 'IMG_002-1.jpg', 2, 'IMG_*-1.jpg'),
      ('WithFolder', 'folder_005/IMG_002.jpg', 2, 'folder_005/IMG_*.jpg'),
      ('NoSeq', 'IMG_01.jpg', -1, 'IMG_01.jpg'),
      ('NoSeqWithFolder', 'folder_005/IMG_01.jpg', -1, 'folder_005/IMG_01.jpg'),
  ])
  def test_get_sequence_and_pattern(self, _, path: str, expected_seq_num: int,
                                    expected_path_pattern: str):
    self.assertEqual(
        burst_shots_into_live_photo.ImageFile.get_sequence_and_pattern(path),
        (expected_seq_num, expected_path_pattern))


class ImageFileMock(burst_shots_into_live_photo.ImageFile):

  def __init__(self, pattern, seq, time):
    self.path_pattern = pattern
    self.sequence_num = seq
    self.time = time


class BurstSeriesTest(unittest.TestCase):

  def test_find_all_series__simple(self):
    images = [
        ImageFileMock('IMG_*.jpg', 1, 0.0),
        ImageFileMock('IMG_*.jpg', 2, 0.0),
        ImageFileMock('IMG_*.jpg', 3, 0.0),
        ImageFileMock('IMG_*.jpg', 5, 0.0),
        ImageFileMock('IMG_*.jpg', 6, 0.0),
    ]
    series = burst_shots_into_live_photo.BurstSeries.find_all_series(images, 1)
    self.assertEqual(len(series), 2)
    self.assertEqual(series[0].first_seq, 1)
    self.assertEqual(series[0].last_seq, 3)
    self.assertEqual(series[1].first_seq, 5)
    self.assertEqual(series[1].last_seq, 6)

  def test_find_all_series__new_series_by_sequence_number(self):
    images = [
        ImageFileMock('IMG_*.jpg', 1, 0.0),
        ImageFileMock('IMG_*.jpg', 3, 0.0),
        ImageFileMock('IMG_*.jpg', 5, 0.0),
    ]
    series = burst_shots_into_live_photo.BurstSeries.find_all_series(images, 1)
    self.assertEqual(len(series), 3)

  def test_find_all_series__new_series_by_image_time(self):
    images = [
        ImageFileMock('IMG_*.jpg', 1, 0.0),
        ImageFileMock('IMG_*.jpg', 2, 0.5),
        ImageFileMock('IMG_*.jpg', 3, 2.0),
    ]
    series = burst_shots_into_live_photo.BurstSeries.find_all_series(images, 1)
    self.assertEqual(len(series), 2)

  def test_find_all_series__new_series_by_pattern(self):
    images = [
        ImageFileMock('DSC_*.jpg', 1, 0.0),
        ImageFileMock('IMA_*.jpg', 2, 0.0),
        ImageFileMock('IMA_*.jpg', 3, 0.0),
    ]
    series = burst_shots_into_live_photo.BurstSeries.find_all_series(images, 1)
    self.assertEqual(len(series), 2)

  def test_find_all_series__min_number_of_images(self):
    images = [
        ImageFileMock('DSC_*.jpg', 1, 0.0),
        ImageFileMock('IMA_*.jpg', 2, 0.0),
        ImageFileMock('IMA_*.jpg', 3, 0.0),
    ]
    series = burst_shots_into_live_photo.BurstSeries.find_all_series(images, 2)
    self.assertEqual(len(series), 1)


if __name__ == '__main__':
  unittest.main()
