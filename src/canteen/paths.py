"""repo-root 派生路径的唯一真相源（spec §5.1）。"""
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent       # .../src/canteen
REPO_ROOT = PACKAGE_ROOT.parents[1]                  # parents[0]=src, parents[1]=repo 根
FRONTEND_ROOT = REPO_ROOT / "frontend"
DATABASE_DIR = REPO_ROOT / "database"
DB_PATH = DATABASE_DIR / "simulation.db"
