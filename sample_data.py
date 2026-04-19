"""Генерация тестового CSV, если входного файла нет."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def ensure_sample_sales_csv(target_path: Path, random_seed: int = 42) -> None:
    """
    Создаёт CSV с синтетическими продажами за один календарный год, если файл отсутствует.

    Колонки: order_id, order_date, customer_id, product_id, product_name,
    category (міндетті емес / опционально), quantity, unit_price.

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

    # Один полный год с 1 января (можно сменить на последние 365 дней от «сегодня»).
    start = pd.Timestamp("2025-01-01")
    end = pd.Timestamp("2025-12-31")

    n_orders = 800
    customer_ids = [f"C{i:04d}" for i in range(1, 201)]
    # (product_id, name, category) — санат фильтрі үшін
    products = [
        ("P001", "Футболка базовая", "Одежда"),
        ("P002", "Джинсы slim", "Одежда"),
        ("P003", "Кроссовки run", "Обувь"),
        ("P004", "Рюкзак городской", "Аксессуары"),
        ("P005", "Кепка логотип", "Аксессуары"),
        ("P006", "Худи oversize", "Одежда"),
        ("P007", "Шорты спорт", "Одежда"),
        ("P008", "Носки набор", "Одежда"),
        ("P009", "Куртка ветровка", "Одежда"),
        ("P010", "Сумка через плечо", "Аксессуары"),
    ]

    rows: list[dict[str, object]] = []
    order_counter = 1

    delta_days = (end - start).days

    for _ in range(n_orders):
        order_id = f"ORD-{order_counter:05d}"
        order_counter += 1
        order_date = start + pd.Timedelta(days=int(rng.integers(0, delta_days + 1)))
        cust = rng.choice(customer_ids)
        n_lines = int(rng.integers(1, 5))  # 1–4 позиции в заказе

        for _line in range(n_lines):
            pid, pname, pcat = products[int(rng.integers(0, len(products)))]
            qty = int(rng.integers(1, 6))
            price = float(rng.uniform(5.0, 120.0))
            price = round(price, 2)
            rows.append(
                {
                    "order_id": order_id,
                    "order_date": order_date.strftime("%Y-%m-%d"),
                    "customer_id": cust,
                    "product_id": pid,
                    "product_name": pname,
                    "category": pcat,
                    "quantity": qty,
                    "unit_price": price,
                }
            )

    df = pd.DataFrame(rows)
    df.sort_values(["order_date", "order_id"], inplace=True)
    df.to_csv(target_path, index=False)
