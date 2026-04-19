"""Загрузка таблицы продаж из CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_sales(csv_path: Path) -> pd.DataFrame:
    """
    Читает CSV с продажами в DataFrame.

    Parameters
    ----------
    csv_path:
        Путь к файлу.

    Returns
    -------
    pd.DataFrame
        Сырые данные без очистки.
    """
    return pd.read_csv(csv_path)
