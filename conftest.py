"""Put the pyRevit extension's lib/ folder on sys.path so tests can import
smart_connect, exactly as pyRevit does at runtime."""

import sys
from pathlib import Path

LIB = Path(__file__).parent / "MepTools.extension" / "lib"
sys.path.insert(0, str(LIB))
