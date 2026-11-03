"""``python -m showsys`` works like the ``showsys`` command, exit status included."""
import sys

from .cli import main

if __name__ == '__main__':
    sys.exit(main())
