"""Аналитика по товарам (топы по количеству)."""

from __future__ import annotations

import pandas as pd


def top_products_by_quantity(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """
    Возвращает топ товаров по суммарному количеству проданных единиц.

    Parameters
    ----------
    df:
        Очищенные данные с колонками product_id, product_name, quantity.
    top_n:
        Сколько позиций вернуть (по умолчанию 10).

    Returns
    -------
    pd.DataFrame
        Таблица с колонками product_id, product_name, total_quantity, упорядоченная по убыванию.
    """
    grouped = (
        df.groupby(["product_id", "product_name"], as_index=False)["quantity"]
        .sum()
        .rename(columns={"quantity": "total_quantity"})
    )
    grouped = grouped.sort_values("total_quantity", ascending=False).head(top_n)
    grouped.reset_index(drop=True, inplace=True)
    return grouped
