"""
Запуск анализа из корня проекта без настройки PYTHONPATH:
    python run.py
    python run.py --csv path\\to\\file.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ecommerce_analytics.main import main  # noqa: E402

if __name__ == "__main__":
    main()
