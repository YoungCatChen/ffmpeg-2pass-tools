from parameterized import parameterized
import unittest

import image_file


class ImageFileTest(unittest.TestCase):

  @parameterized.expand([
      ('3Digits', 'IMG_001.jpg', 1, 'IMG_%03d.jpg'),
      ('4Digits', 'IMG_0002.jpg', 2, 'IMG_%04d.jpg'),
      ('TrailingDigit', 'IMG_002-1.jpg', 2, 'IMG_%03d-1.jpg'),
      ('WithFolder', 'folder_005/IMG_002.jpg', 2, 'folder_005/IMG_%03d.jpg'),
      ('NoSeqFor2Digits', 'IMG_01.jpg', -1, 'IMG_01.jpg'),
      ('NoSeqFor2Digits', 'folder_005/IMG_01.jpg', -1, 'folder_005/IMG_01.jpg'),
  ])
  def test_get_sequence_and_pattern(self, _, path: str, expected_seq_num: int,
                                    expected_path_pattern: str):
    self.assertEqual(image_file.ImageFile.get_sequence_and_pattern(path),
                     (expected_seq_num, expected_path_pattern))


if __name__ == '__main__':
  unittest.main()
