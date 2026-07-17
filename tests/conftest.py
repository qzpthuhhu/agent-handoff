"""pytest 配置:加 sys.path。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mcp-server" / "src"))
sys.path.insert(0, str(_ROOT / "server"))
