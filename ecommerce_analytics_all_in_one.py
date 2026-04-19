"""
Полный анализ e-commerce в одном файле: очистка, топ-10 товаров, график выручки, RFM, инсайты.
Запуск: python ecommerce_analytics_all_in_one.py
        python ecommerce_analytics_all_in_one.py --csv path\\to\\file.csv --out path\\to\\output
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# ---------------------------------------------------------------------------
# Пути (корень = каталог, где лежит этот скрипт)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "sales_yearly.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"

# Консоль Windows: корректный вывод UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Генерация тестового CSV
# ---------------------------------------------------------------------------


def ensure_sample_sales_csv(target_path: Path, random_seed: int = 42) -> None:
    """
    Создаёт CSV с синтетическими продажами за один календарный год, если файл отсутствует.

    Колонки: order_id, order_date, customer_id, product_id, product_name,
    quantity, unit_price (как в типичном экспорте e-commerce).

    Parameters
    ----------
    target_path:
        Путь для сохранения файла (каталоги создаются при необходимости).
    random_seed:
        Seed ГПСЧ для воспроизводимости.
    """
    if target_path.exists():
        return

    target_path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(random_seed)

    start = pd.Timestamp("2025-01-01")
    end = pd.Timestamp("2025-12-31")

    n_orders = 800
    customer_ids = [f"C{i:04d}" for i in range(1, 201)]
    products = [
        ("P001", "Футболка базовая"),
        ("P002", "Джинсы slim"),
        ("P003", "Кроссовки run"),
        ("P004", "Рюкзак городской"),
        ("P005", "Кепка логотип"),
        ("P006", "Худи oversize"),
        ("P007", "Шорты спорт"),
        ("P008", "Носки набор"),
        ("P009", "Куртка ветровка"),
        ("P010", "Сумка через плечо"),
    ]

    rows: list[dict[str, object]] = []
    order_counter = 1
    delta_days = (end - start).days

    for _ in range(n_orders):
        order_id = f"ORD-{order_counter:05d}"
        order_counter += 1
        order_date = start + pd.Timedelta(days=int(rng.integers(0, delta_days + 1)))
        cust = rng.choice(customer_ids)
        n_lines = int(rng.integers(1, 5))

        for _line in range(n_lines):
            pid, pname = products[int(rng.integers(0, len(products)))]
            qty = int(rng.integers(1, 6))
            price = round(float(rng.uniform(5.0, 120.0)), 2)
            rows.append(
                {
                    "order_id": order_id,
                    "order_date": order_date.strftime("%Y-%m-%d"),
                    "customer_id": cust,
                    "product_id": pid,
                    "product_name": pname,
                    "quantity": qty,
                    "unit_price": price,
                }
            )

    df = pd.DataFrame(rows)
    df.sort_values(["order_date", "order_id"], inplace=True)
    df.to_csv(target_path, index=False)


# ---------------------------------------------------------------------------
# Загрузка и очистка
# ---------------------------------------------------------------------------


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

    string_cols = ["order_id", "customer_id", "product_id", "product_name"]
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
    out = out.drop_duplicates()
    out.sort_values(["order_date", "order_id"], inplace=True)
    out.reset_index(drop=True, inplace=True)
    return out


# ---------------------------------------------------------------------------
# Топ товаров и выручка по месяцам
# ---------------------------------------------------------------------------


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
        Таблица с колонками product_id, product_name, total_quantity.
    """
    grouped = (
        df.groupby(["product_id", "product_name"], as_index=False)["quantity"]
        .sum()
        .rename(columns={"quantity": "total_quantity"})
    )
    grouped = grouped.sort_values("total_quantity", ascending=False).head(top_n)
    grouped.reset_index(drop=True, inplace=True)
    return grouped


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
    return tmp.groupby("month", sort=True)["line_revenue"].sum()


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


# ---------------------------------------------------------------------------
# RFM
# ---------------------------------------------------------------------------


def _quintile_score_5_best(
    series: pd.Series,
    *,
    low_value_is_best: bool,
) -> pd.Series:
    """
    Присваивает баллы 1–5: чем «лучше» значение метрики, тем выше балл.

    Для Recency «лучше» меньшее число дней (low_value_is_best=True).
    Для Frequency/Monetary «лучше» большее значение (low_value_is_best=False).
    """
    ranks = series.rank(method="first", ascending=low_value_is_best)
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

    Если reference_date не задана, берётся день, следующий за последней датой в данных.

    Parameters
    ----------
    df:
        Очищенные данные: order_id, customer_id, order_date, line_revenue.
    reference_date:
        Точка отсчёта для Recency.

    Returns
    -------
    pd.DataFrame
        Одна строка на клиента с полями recency_days, frequency, monetary, сегмент.
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


# ---------------------------------------------------------------------------
# Инсайты и точка входа
# ---------------------------------------------------------------------------


def print_business_insights(
    monthly_revenue: pd.Series,
    rfm: pd.DataFrame,
) -> None:
    """
    Печатает короткие инсайты: лучший месяц по выручке и наиболее лояльный сегмент.

    Лояльность — сегмент с максимальной средней частотой заказов среди «Чемпионы» и
    «Лояльные»; если их нет — среди всех сегментов.

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


def parse_args() -> argparse.Namespace:
    """Парсинг аргументов CLI."""
    p = argparse.ArgumentParser(description="Аналитика e-commerce (один файл).")
    p.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help="Путь к CSV с продажами (если файла нет — будет создан тестовый).",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Каталог для графиков.",
    )
    return p.parse_args()


def main() -> None:
    """Запускает полный сценарий анализа."""
    args = parse_args()
    ensure_sample_sales_csv(args.csv)

    print(f"Загрузка данных: {args.csv}")
    raw = load_sales(args.csv)
    print(f"Строк после загрузки: {len(raw)}")

    clean = clean_sales(raw)
    print(f"Строк после очистки: {len(clean)}")

    print("\n--- Топ-10 товаров по количеству ---")
    top10 = top_products_by_quantity(clean, top_n=10)
    print(top10.to_string(index=False))

    monthly = monthly_revenue_series(clean)
    chart_path = args.out / "revenue_monthly.png"
    plot_monthly_revenue(monthly, output_path=chart_path)
    print(f"\nГрафик выручки по месяцам сохранён: {chart_path}")

    rfm = compute_rfm(clean)
    print("\n--- RFM: первые 10 клиентов ---")
    print(
        rfm[
            [
                "customer_id",
                "recency_days",
                "frequency",
                "monetary",
                "R_score",
                "F_score",
                "M_score",
                "segment",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )

    print("\n--- Распределение по RFM-сегментам ---")
    print(rfm["segment"].value_counts().to_string())

    print_business_insights(monthly, rfm)


if __name__ == "__main__":
    main()
