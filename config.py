"""Константы и пути приложения."""

from __future__ import annotations

from pathlib import Path

# Корень проекта
PROJECT_ROOT = Path(__file__).resolve().parent

# Данные и артефакты по умолчанию
DEFAULT_DATA_PATH = PROJECT_ROOT / "sales_yearly.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
