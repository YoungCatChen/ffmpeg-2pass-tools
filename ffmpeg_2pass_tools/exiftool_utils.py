import atexit
import exiftool

_exiftool_helper = exiftool.ExifToolHelper(common_args=[])
atexit.register(_exiftool_helper.terminate)


def singleton() -> exiftool.ExifToolHelper:
  return _exiftool_helper


def get_time(fname: str) -> float:
  result = singleton().execute(fname, '-dateFormat', '%s', '-printFormat',
                               '$DateTimeOriginal.$SubSecTimeOriginal')
  result = result.strip()
  return float(result) if result else 0.0
