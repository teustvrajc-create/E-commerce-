"""RFM-сегментация клиентов."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd


def _quintile_score_5_best(
    series: pd.Series,
    *,
    low_value_is_best: bool,
) -> pd.Series:
    """
    Присваивает баллы 1–5: чем «лучше» значение метрики, тем выше балл.

    Для Recency «лучше» меньшее число дней (low_value_is_best=True).
    Для Frequency/Monetary «лучше» большее значение (low_value_is_best=False).

    Используется ранжирование + квантили, чтобы устойчиво обрабатывать выбросы и дубликаты.
    """
    ranks = series.rank(method="first", ascending=low_value_is_best)
    # Меньший rank = лучше. Первые квантили (лучшие) получают метку 5.
    cuts = pd.qcut(ranks, q=5, labels=[5, 4, 3, 2, 1], duplicates="drop")
    return cuts.astype(int)


def assign_rfm_segment(row: pd.Series) -> str:
    """
    Назначает сегмент по комбинации R/F/M баллов (упрощённая RFM-таблица).

    Обозначения: r, f, m — целые от 1 до 5.
    """
    r, f, m = int(row["R_score"]), int(row["F_score"]), int(row["M_score"])

    if r >= 4 and f >= 4 and m >= 4:
        return "Чемпионы"
    if r >= 3 and f >= 4 and m >= 4:
        return "Лояльные"
    if r >= 4 and f <= 2 and m <= 2:
        return "Новички"
    if r >= 3 and f <= 2:
        return "Перспективные"
    if r <= 2 and f >= 3 and m >= 3:
        return "Не терять (at risk)"
    if r <= 2 and f >= 4 and m >= 4:
        return "Нельзя упустить"
    if r <= 2 and f <= 2 and m <= 2:
        return "Спящие"
    return "Остальные"


def compute_rfm(
    df: pd.DataFrame,
    reference_date: date | datetime | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Строит RFM-таблицу на уровне клиента.

    - Recency: «текущая дата» минус дата последней покупки клиента (в днях).
    - Frequency: общее количество заказов клиента (число уникальных order_id).
    - Monetary: суммарные траты клиента по полю line_revenue.

    Если reference_date не задана, берётся день, следующий за последней датой в данных
    (отчёт на конец наблюдаемого периода — стандарт для годовых выгрузок).

    Parameters
    ----------
    df:
        Очищенные данные: order_id, customer_id, order_date, line_revenue.
    reference_date:
        Точка отсчёта для Recency.

    Returns
    -------
    pd.DataFrame
        Одна строка на клиента: last_order_date, frequency, monetary, recency_days, баллы, сегмент.
    """
    if reference_date is None:
        reference_date = pd.Timestamp(df["order_date"].max()).normalize() + pd.Timedelta(days=1)
    else:
        reference_date = pd.Timestamp(reference_date).normalize()

    per_order = df.groupby(["customer_id", "order_id"], as_index=False)["order_date"].max()
    freq = per_order.groupby("customer_id")["order_id"].nunique().rename("frequency")

    last_order = df.groupby("customer_id")["order_date"].max().rename("last_order_date")
    monetary = df.groupby("customer_id")["line_revenue"].sum().rename("monetary")

    rfm = pd.concat([last_order, freq, monetary], axis=1)
    rfm["recency_days"] = (reference_date - rfm["last_order_date"]).dt.days

    rfm["R_score"] = _quintile_score_5_best(rfm["recency_days"], low_value_is_best=True)
    rfm["F_score"] = _quintile_score_5_best(rfm["frequency"], low_value_is_best=False)
    rfm["M_score"] = _quintile_score_5_best(rfm["monetary"], low_value_is_best=False)

    rfm["segment"] = rfm.apply(assign_rfm_segment, axis=1)
    rfm.reset_index(inplace=True)
    return rfm
