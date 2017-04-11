from motdplayer_applications import parse_packages
from path import Path


__all__ = parse_packages(Path(__file__).parent)

from . import *
