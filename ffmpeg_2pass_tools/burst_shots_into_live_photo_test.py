import unittest

from ffmpeg_2pass_tools import burst_shots_into_live_photo
from ffmpeg_2pass_tools import image_file


class BurstSeriesTest(unittest.TestCase):

  def test_find_all_series__simple(self):
    images = [
        image_file.TestImageFile('IMG_001.jpg', 0.0),
        image_file.TestImageFile('IMG_002.jpg', 0.0),
        image_file.TestImageFile('IMG_003.jpg', 0.0),
        image_file.TestImageFile('IMG_005.jpg', 0.0),
        image_file.TestImageFile('IMG_006.jpg', 0.0),
    ]
    series = burst_shots_into_live_photo.BurstSeries.find_all_series(images, 1)
    self.assertEqual(len(series), 2)
    self.assertEqual(series[0].first_seq, 1)
    self.assertEqual(series[0].last_seq, 3)
    self.assertEqual(series[1].first_seq, 5)
    self.assertEqual(series[1].last_seq, 6)

  def test_find_all_series__new_series_by_sequence_number(self):
    images = [
        image_file.TestImageFile('IMG_001.jpg', 0.0),
        image_file.TestImageFile('IMG_003.jpg', 0.0),
        image_file.TestImageFile('IMG_005.jpg', 0.0),
    ]
    series = burst_shots_into_live_photo.BurstSeries.find_all_series(images, 1)
    self.assertEqual(len(series), 3)

  def test_find_all_series__new_series_by_image_time(self):
    images = [
        image_file.TestImageFile('IMG_001.jpg', 0.0),
        image_file.TestImageFile('IMG_002.jpg', 0.5),
        image_file.TestImageFile('IMG_003.jpg', 2.0),
    ]
    series = burst_shots_into_live_photo.BurstSeries.find_all_series(images, 1)
    self.assertEqual(len(series), 2)

  def test_find_all_series__new_series_by_pattern(self):
    images = [
        image_file.TestImageFile('DSC_001.jpg', 0.0),
        image_file.TestImageFile('IMA_002.jpg', 0.0),
        image_file.TestImageFile('IMA_003.jpg', 0.0),
    ]
    series = burst_shots_into_live_photo.BurstSeries.find_all_series(images, 1)
    self.assertEqual(len(series), 2)

  def test_find_all_series__min_number_of_images(self):
    images = [
        image_file.TestImageFile('DSC_001.jpg', 0.0),
        image_file.TestImageFile('IMA_002.jpg', 0.0),
        image_file.TestImageFile('IMA_003.jpg', 0.0),
    ]
    series = burst_shots_into_live_photo.BurstSeries.find_all_series(images, 2)
    self.assertEqual(len(series), 1)


if __name__ == '__main__':
  unittest.main()
