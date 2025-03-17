import builtins
import subprocess
from typing import Sequence


def print(*args, **kwargs) -> None:
  """Prints the arguments in cyan."""
  builtins.print('\033[1;36m', end='')
  builtins.print(*args, **kwargs, end='')
  builtins.print('\033[m')


def warn(*args, **kwargs) -> None:
  """Prints the arguments in red."""
  builtins.print('\033[1;31m', end='')
  builtins.print(*args, **kwargs, end='')
  builtins.print('\033[m')


class ExecCmd:
  """Prints and runs a command. Exit if the command fails."""

  def __init__(self, dry_run=False):
    self.dry_run = dry_run

  def run(self, cmd: Sequence[str]) -> None:
    builtins.print()
    print(*cmd)
    if self.dry_run:
      return
    try:
      result = subprocess.run(cmd)
    except KeyboardInterrupt:
      exit(130)
    if result.returncode != 0:
      exit(result.returncode)
