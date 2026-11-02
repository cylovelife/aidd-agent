"""Compatibility entry for the frozen CYP research script.

@author cylovelife
"""

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).parent / "cyp" / Path(__file__).name), run_name="__main__")
