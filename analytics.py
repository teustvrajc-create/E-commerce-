"""
Логика обработки e-commerce данных: очистка, RFM, визуализация Plotly,
прогноз выручки (LinearRegression), экспорт Excel/PDF.
"""

from __future__ import annotations

import io
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sklearn.linear_model import LinearRegression

# --- Обязательные колонки CSV (как в исходном кейсе) ---
REQUIRED_COLUMNS = [
    "order_id",
    "order_date",
    "customer_id",
    "product_id",
    "product_name",
    "quantity",
    "unit_price",
]


class DataValidationError(Exception):
    """Ошибка проверки входного файла или таблицы."""


def validate_raw_sales(df: pd.DataFrame) -> None:
    """
    Проверяет наличие обязательных колонок и что таблица не пустая.

    Raises
    ------
    DataValidationError
        Если данные непригодны для анализа.
    """
    if df is None or df.empty:
        raise DataValidationError("Файл пустой или не содержит строк.")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(
            "Не хватает обязательных колонок: "
            + ", ".join(missing)
            + ". Ожидаются: "
            + ", ".join(REQUIRED_COLUMNS)
        )


def clean_sales(df: pd.DataFrame) -> pd.DataFrame:
    """
    Очищает данные, считает line_revenue; колонку category добавляет как «Без категории», если её нет.
    """
    out = df.copy()

    if "category" not in out.columns:
        out["category"] = "Без категории"
    else:
        out["category"] = out["category"].astype(str).str.strip().replace({"": "Без категории", "nan": "Без категории"})

    string_cols = ["order_id", "customer_id", "product_id", "product_name", "category"]
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


def filter_by_date_range(
    df: pd.DataFrame,
    start: date | datetime | pd.Timestamp | None,
    end: date | datetime | pd.Timestamp | None,
) -> pd.DataFrame:
    """Фильтрует строки по дате заказа (включительно по дню)."""
    out = df.copy()
    if start is not None:
        s = pd.Timestamp(start)
        out = out[out["order_date"] >= s]
    if end is not None:
        e = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        out = out[out["order_date"] <= e]
    out.reset_index(drop=True, inplace=True)
    return out


def filter_by_categories(df: pd.DataFrame, categories: list[str] | None) -> pd.DataFrame:
    """Оставляет только выбранные категории; если список пустой/None — без изменений."""
    if not categories:
        return df
    out = df[df["category"].isin(categories)].copy()
    out.reset_index(drop=True, inplace=True)
    return out


def top_products_by_quantity(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Топ товаров по суммарному количеству."""
    grouped = (
        df.groupby(["product_id", "product_name"], as_index=False)["quantity"]
        .sum()
        .rename(columns={"quantity": "total_quantity"})
    )
    grouped = grouped.sort_values("total_quantity", ascending=False).head(top_n)
    grouped.reset_index(drop=True, inplace=True)
    return grouped


def monthly_revenue_series(df: pd.DataFrame) -> pd.Series:
    """Суммарная выручка по месяцам."""
    tmp = df.copy()
    tmp["month"] = tmp["order_date"].dt.to_period("M")
    return tmp.groupby("month", sort=True)["line_revenue"].sum()


def _quintile_score_5_best(series: pd.Series, *, low_value_is_best: bool) -> pd.Series:
    ranks = series.rank(method="first", ascending=low_value_is_best)
    cuts = pd.qcut(ranks, q=5, labels=[5, 4, 3, 2, 1], duplicates="drop")
    return cuts.astype(int)


def assign_rfm_segment(row: pd.Series) -> str:
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
    """RFM по клиентам; точка отсчёта по умолчанию — день после последней даты в выборке."""
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


def forecast_next_month_revenue(monthly_revenue: pd.Series) -> dict[str, Any]:
    """
    Прогноз суммарной выручки на следующий календарный месяц (Linear Regression по индексу месяца).

    Returns
    -------
    dict с ключами: next_period (str), predicted_value (float), history_months (int), note (str).
    """
    if monthly_revenue.empty or len(monthly_revenue) < 2:
        return {
            "next_period": "",
            "predicted_value": float("nan"),
            "history_months": int(len(monthly_revenue)),
            "note": "Недостаточно месяцев для регрессии (нужно минимум 2).",
        }

    y = monthly_revenue.astype(float).values
    X = np.arange(len(y)).reshape(-1, 1)
    model = LinearRegression()
    model.fit(X, y)
    next_index = np.array([[len(y)]])
    pred = float(model.predict(next_index)[0])
    last_period: pd.Period = monthly_revenue.index[-1]  # type: ignore[assignment]
    next_period = (last_period + 1).strftime("%Y-%m")
    return {
        "next_period": next_period,
        "predicted_value": max(pred, 0.0),
        "history_months": len(y),
        "note": "Модель: линейная регрессия по номеру месяца (тренд).",
    }


def plotly_monthly_revenue(monthly_revenue: pd.Series) -> go.Figure:
    """Интерактивный график выручки по месяцам."""
    x = [str(p) for p in monthly_revenue.index]
    fig = px.line(
        x=x,
        y=monthly_revenue.values,
        markers=True,
        labels={"x": "Ай (жыл / ай)", "y": "Кіріс / Выручка"},
        title="Айлық кіріс / Выручка по месяцам",
    )
    fig.update_layout(template="plotly_dark", hovermode="x unified", height=420)
    return fig


def plotly_forecast_chart(monthly_revenue: pd.Series, forecast: dict[str, Any]) -> go.Figure:
    """История + точка прогноза на следующий месяц."""
    hist_x = [str(p) for p in monthly_revenue.index]
    hist_y = list(monthly_revenue.values)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hist_x,
            y=hist_y,
            mode="lines+markers",
            name="Факт",
            line=dict(width=2),
        )
    )
    fv = forecast.get("predicted_value")
    fp = forecast.get("next_period")
    if fp and fv == fv and not np.isnan(fv):  # not nan
        fig.add_trace(
            go.Scatter(
                x=[fp],
                y=[fv],
                mode="markers",
                name="Прогноз (след. ай)",
                marker=dict(size=14, symbol="star"),
            )
        )
    fig.update_layout(
        title="Прогноз выручки (Linear Regression) — келесі ай / следующий месяц",
        template="plotly_dark",
        height=420,
        hovermode="x unified",
        xaxis_title="Период",
        yaxis_title="Выручка",
    )
    return fig


def plotly_rfm_scatter(rfm: pd.DataFrame) -> go.Figure:
    """Scatter: Monetary vs Frequency, цвет = сегмент, hover — Recency и ID клиента."""
    fig = px.scatter(
        rfm,
        x="frequency",
        y="monetary",
        color="segment",
        hover_data=["customer_id", "recency_days", "R_score", "F_score", "M_score"],
        title="RFM: жиілік vs сома (көп нүктелі)",
        labels={
            "frequency": "Жиілік / Частота заказов",
            "monetary": "Сома трат / Денежная ценность",
            "segment": "Сегмент",
        },
    )
    fig.update_layout(template="plotly_dark", height=520)
    return fig


def plotly_rfm_treemap(rfm: pd.DataFrame) -> go.Figure:
    """Treemap по сегментам: размер = сумма Monetary."""
    agg = rfm.groupby("segment", as_index=False).agg(customers=("customer_id", "count"), revenue=("monetary", "sum"))
    fig = px.treemap(
        agg,
        path=["segment"],
        values="revenue",
        title="RFM сегменттері: Monetary сомасы (Treemap)",
        hover_data=["customers"],
    )
    fig.update_layout(template="plotly_dark", height=480)
    return fig


def rfm_to_excel_bytes(rfm: pd.DataFrame) -> bytes:
    """Копия таблицы RFM в формате .xlsx (bytes)."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        rfm.to_excel(writer, index=False, sheet_name="RFM")
    buf.seek(0)
    return buf.read()


def _register_unicode_font() -> str:
    """
    Регистрирует TTF с поддержкой кириллицы (Arial на Windows, иначе попытка DejaVu).
    Возвращает имя шрифта для ReportLab.
    """
    candidates: list[tuple[str, Path]] = []
    windir = os.environ.get("WINDIR")
    if windir:
        candidates.append(("ArialRU", Path(windir) / "Fonts" / "arial.ttf"))
        candidates.append(("CalibriRU", Path(windir) / "Fonts" / "calibri.ttf"))
    candidates.extend(
        [
            ("DejaVuSans", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")),
            ("NotoSans", Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf")),
        ]
    )
    for name, p in candidates:
        try:
            if p.is_file():
                pdfmetrics.registerFont(TTFont(name, str(p)))
                return name
        except Exception:
            continue
    return "Helvetica"


def build_pdf_report_bytes(
    title: str,
    lines: list[str],
    monthly_revenue: pd.Series,
    rfm_head: pd.DataFrame,
) -> bytes:
    """
    PDF-отчёт (ReportLab): текст, последние месяцы выручки, образец RFM.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    font = _register_unicode_font()
    _, height = A4
    y = height - 40
    c.setFont(font, 14)

    def _draw(x: float, yy: float, text: str) -> None:
        try:
            c.drawString(x, yy, text)
        except Exception:
            c.drawString(x, yy, text.encode("ascii", "replace").decode("ascii"))

    for chunk in _wrap_lines(title, 80):
        _draw(40, y, chunk[:500])
        y -= 18
        if y < 80:
            c.showPage()
            c.setFont(font, 14)
            y = height - 40
    c.setFont(font, 11)
    y -= 8
    for line in lines:
        for chunk in _wrap_lines(line, 95):
            _draw(40, y, chunk[:500])
            y -= 14
            if y < 80:
                c.showPage()
                c.setFont(font, 11)
                y = height - 40

    y -= 10
    c.setFont(font, 12)
    _draw(40, y, "Выручка по месяцам (соңғы жұрты / последние строки):")
    y -= 20
    c.setFont(font, 10)
    for idx, val in monthly_revenue.tail(8).items():
        _draw(40, y, f"{idx}: {float(val):,.2f}")
        y -= 12
        if y < 80:
            c.showPage()
            c.setFont(font, 10)
            y = height - 40

    y -= 10
    c.setFont(font, 12)
    _draw(40, y, "RFM (үлгісі / выборка, 15 клиентов):")
    y -= 18
    c.setFont(font, 9)
    for _, row in rfm_head.head(15).iterrows():
        s = (
            f"{row.get('customer_id','')}: R={row.get('recency_days','')} "
            f"F={row.get('frequency','')} M={float(row.get('monetary', 0)):.2f} {row.get('segment','')}"
        )
        for chunk in _wrap_lines(s, 100):
            _draw(40, y, chunk[:520])
            y -= 11
            if y < 60:
                c.showPage()
                c.setFont(font, 9)
                y = height - 40

    c.save()
    return buf.getvalue()


def _wrap_lines(text: str, max_len: int) -> list[str]:
    """Грубый перенос длинных строк для PDF."""
    text = text.replace("\n", " ")
    if len(text) <= max_len:
        return [text]
    return [text[i : i + max_len] for i in range(0, len(text), max_len)]


def insights_text(monthly_revenue: pd.Series, rfm: pd.DataFrame, forecast: dict[str, Any]) -> list[str]:
    """Краткие формулировки для PDF/экрана."""
    lines: list[str] = []
    if not monthly_revenue.empty:
        idx = monthly_revenue.idxmax()
        lines.append(
            f"Самый прибыльный месяц: {idx} (выручка {float(monthly_revenue.loc[idx]):,.2f})."
        )
    premium = rfm[rfm["segment"].isin(["Чемпионы", "Лояльные"])]
    pool = premium if not premium.empty else rfm
    if not pool.empty:
        seg_stats = pool.groupby("segment")["frequency"].mean().sort_values(ascending=False)
        loyal = str(seg_stats.index[0])
        lines.append(
            f'Наиболее "лояльный" сегмент (по средней частоте среди приоритетных): {loyal} '
            f"({seg_stats.iloc[0]:.2f} заказов в среднем)."
        )
    fv = forecast.get("predicted_value")
    fp = forecast.get("next_period")
    if fp and fv == fv and not np.isnan(fv):
        lines.append(f"Прогноз выручки на {fp}: {fv:,.2f} (linear trend).")
    return lines


def load_csv_from_upload(uploaded_file: Any) -> pd.DataFrame:
    """Читает загруженный в Streamlit файл в DataFrame."""
    return pd.read_csv(uploaded_file)
