"""把 src/ 注入 sys.path，未 pip install -e . 也能 import canteen.*。

pytest 无条件先收集 repo 根 conftest（不受 testpaths 限制），故对 tests/ 全量生效。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
