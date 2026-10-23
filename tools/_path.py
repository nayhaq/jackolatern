"""Lets tools/ scripts import the jack-o-intern modules one folder up."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
