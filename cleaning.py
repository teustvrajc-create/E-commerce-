"""Очистка и подготовка данных для анализа."""

from __future__ import annotations

import pandas as pd


def clean_sales(df: pd.DataFrame) -> pd.DataFrame:
    """
    Приводит таблицу продаж к аналитическому виду: типы, валидность, вычисляемые поля.

    Действия:
    - приведение дат и строковых идентификаторов;
    - удаление строк с пропусками в ключевых полях;
    - фильтрация некорректных количеств и цен;
    - расчёт выручки по строке заказа.

    Parameters
    ----------
    df:
        Исходный DataFrame (ожидаются колонки order_date, quantity, unit_price и др.).

    Returns
    -------
    pd.DataFrame
        Очищенная таблица с колонкой line_revenue.
    """
    out = df.copy()

    string_cols = [
        "order_id",
        "customer_id",
        "product_id",
        "product_name",
    ]
    for col in string_cols:
        if col in out.columns:
            out[col] = out[col].astype(str).str.strip()

    out["order_date"] = pd.to_datetime(out["order_date"], errors="coerce")

    out["quantity"] = pd.to_numeric(out["quantity"], errors="coerce")
    out["unit_price"] = pd.to_numeric(out["unit_price"], errors="coerce")

    key_cols = ["order_id", "order_date", "customer_id", "product_id", "quantity", "unit_price"]
    out = out.dropna(subset=[c for c in key_cols if c in out.columns])

    out = out[(out["quantity"] > 0) & (out["unit_price"] >= 0)]

    out["line_revenue"] = out["quantity"] * out["unit_price"]

    # Удаление полных дубликатов строк (частая проблема выгрузок).
    out = out.drop_duplicates()

    out.sort_values(["order_date", "order_id"], inplace=True)
    out.reset_index(drop=True, inplace=True)
    return out
