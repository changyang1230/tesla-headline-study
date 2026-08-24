"""Make `src` importable whether pytest is run from the repository root or from here."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
