"""Run the Build468 benchmark from a source archive or an installed runtime."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eagleeye.application.benchmark468 import main

if __name__ == "__main__":
    main()
