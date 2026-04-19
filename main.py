"""Оркестрация пайплайна: данные → очистка → метрики → графики → инсайты."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Консоль Windows (cp1251): вывод кириллицы без ошибок при наличии UTF-8 у потока.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except OSError:
        pass

from ecommerce_analytics.cleaning import clean_sales
from ecommerce_analytics.config import DEFAULT_DATA_PATH, DEFAULT_OUTPUT_DIR
from ecommerce_analytics.insights import print_business_insights
from ecommerce_analytics.loader import load_sales
from ecommerce_analytics.products import top_products_by_quantity
from ecommerce_analytics.revenue import monthly_revenue_series, plot_monthly_revenue
from ecommerce_analytics.rfm import compute_rfm
from ecommerce_analytics.sample_data import ensure_sample_sales_csv


def parse_args() -> argparse.Namespace:
    """Парсинг аргументов CLI."""
    p = argparse.ArgumentParser(description="Аналитика e-commerce (очистка, топы, RFM).")
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
    seg_counts = rfm["segment"].value_counts()
    print(seg_counts.to_string())

    print_business_insights(monthly, rfm)


if __name__ == "__main__":
    main()
