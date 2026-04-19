"""Краткие выводы по результатам анализа."""

from __future__ import annotations

import pandas as pd


def print_business_insights(
    monthly_revenue: pd.Series,
    rfm: pd.DataFrame,
) -> None:
    """
    Печатает короткие инсайты: лучший месяц по выручке и наиболее лояльный сегмент.

    Лояльность здесь трактуется как сегмент с максимальной средней частотой заказов
    среди сегментов «Чемпионы» и «Лояльные» (если такие есть); иначе — сегмент с
    максимальной средней частотой в целом.

    Parameters
    ----------
    monthly_revenue:
        Ряд выручки по месяцам (индекс Period[M]).
    rfm:
        Результат compute_rfm.
    """
    if monthly_revenue.empty:
        best_month = "— (нет данных)"
        best_revenue = float("nan")
    else:
        idxmax = monthly_revenue.idxmax()
        best_month = str(idxmax)
        best_revenue = float(monthly_revenue.loc[idxmax])

    premium = rfm[rfm["segment"].isin(["Чемпионы", "Лояльные"])]
    pool = premium if not premium.empty else rfm
    if pool.empty:
        loyal_segment = "—"
        mean_freq = float("nan")
    else:
        seg_stats = pool.groupby("segment")["frequency"].mean().sort_values(ascending=False)
        loyal_segment = str(seg_stats.index[0])
        mean_freq = float(seg_stats.iloc[0])

    print("\n=== Краткие инсайты ===")
    print(
        f"- Самый прибыльный месяц: {best_month} "
        f"(выручка около {best_revenue:,.2f} в единицах суммы из CSV)."
    )
    print(
        f'- Наиболее "лояльная" группа (повторные покупки): "{loyal_segment}" '
        f"(средняя частота заказов в сегменте около {mean_freq:.2f})."
    )
