import subprocess
from typing import Sequence


class ExecCmd:
  """Prints and runs a command. Exit if the command fails."""

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
