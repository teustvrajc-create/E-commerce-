"""Агрегация выручки по месяцам и визуализация."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def monthly_revenue_series(df: pd.DataFrame) -> pd.Series:
    """
    Считает суммарную выручку по календарным месяцам.

    Parameters
    ----------
    df:
        Очищенные данные с order_date и line_revenue.

    Returns
    -------
    pd.Series
        Индекс — период (месяц), значения — выручка.
    """
    tmp = df.copy()
    tmp["month"] = tmp["order_date"].dt.to_period("M")
    revenue = tmp.groupby("month", sort=True)["line_revenue"].sum()
    return revenue


def plot_monthly_revenue(
    monthly_revenue: pd.Series,
    output_path: Path | None = None,
) -> None:
    """
    Строит линейный график выручки по месяцам (Seaborn + Matplotlib).

    Parameters
    ----------
    monthly_revenue:
        Ряд из monthly_revenue_series.
    output_path:
        Если задан — PNG сохраняется на диск.
    """
    # PeriodIndex -> метки для оси X
    x = monthly_revenue.index.astype(str).tolist()
    y = monthly_revenue.values

    sns.set_theme(style="whitegrid", context="notebook")
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(x=x, y=y, marker="o", ax=ax)
    ax.set_title("Выручка по месяцам")
    ax.set_xlabel("Месяц")
    ax.set_ylabel("Выручка")
    plt.xticks(rotation=45, ha="right")
    fig.tight_layout()

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150)
    plt.close(fig)
