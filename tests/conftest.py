import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "finance-video-script" / "scripts"
sys.path.insert(0, str(SCRIPTS))
