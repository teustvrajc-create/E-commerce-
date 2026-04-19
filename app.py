"""
Интерфейс Streamlit: жүктеу, фильтрлер, интерактивті графиктер, экспорт, журнал SQLite.
Іске қосу: streamlit run app.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import analytics as an
from database import init_db, log_upload, recent_uploads

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CSV = PROJECT_ROOT / "data" / "sales_yearly.csv"

st.set_page_config(
    page_title="E-commerce талдау панелі",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _load_raw_dataframe(uploaded_file, use_demo: bool) -> tuple[pd.DataFrame, str]:
    """Возвращает DataFrame и имя источника (файл или демо)."""
    if use_demo or uploaded_file is None:
        if not DEFAULT_CSV.is_file():
            st.error(f"Демо файл табылмады: {DEFAULT_CSV}. Жүктеп салған CSV қолданыңыз.")
            st.stop()
        df = pd.read_csv(DEFAULT_CSV)
        return df, str(DEFAULT_CSV.name)
    df = an.load_csv_from_upload(uploaded_file)
    return df, uploaded_file.name


def main() -> None:
    init_db()

    st.title("📊 E-commerce талдау / Аналитика продаж")
    st.caption(
        "Интерактивті дашборд: Plotly, RFM, болжам (Linear Regression), SQLite журналы."
    )

    with st.sidebar:
        st.subheader("📁 Деректер / Данные")
        uploaded = st.file_uploader(
            "CSV жүктеу (order_id, order_date, …)",
            type=["csv"],
            help="Міндетті бағандар: order_id, order_date, customer_id, product_id, product_name, quantity, unit_price. "
            "Қосымша: category.",
        )
        use_demo = st.toggle(
            "Демо деректер (data/sales_yearly.csv)",
            value=uploaded is None,
            help="Егер файл жүктемесеңіз, жергілікті демо қолданылады.",
        )

        st.subheader("🗓 Кезең / Период дат")
        st.caption("Фильтр применяется после очистки данных.")

        st.subheader("🗄 Журнал (SQLite)")

    # --- загрузка и проверка ---
    try:
        raw, source_name = _load_raw_dataframe(uploaded, use_demo)
        an.validate_raw_sales(raw)
    except an.DataValidationError as e:
        st.error(str(e))
        st.info(
            "**Қате файл:** бос файл немесе бағандар сәйкес келмейді. "
            "Тексеріңіз: order_id, order_date, customer_id, product_id, product_name, quantity, unit_price."
        )
        st.stop()

    try:
        clean_full = an.clean_sales(raw)
    except Exception as e:
        st.exception(e)
        st.stop()

    if clean_full.empty:
        st.warning("Тазалаудан кейін дерек қалмады — бағандарды немесе формат күндерді тексеріңіз.")
        st.stop()

    # Журналда тек настоящая загрузка пользователя (не демо переключатель без файла можно логировать как demo - логируем один раз за сессию)
    if uploaded is not None and not use_demo:
        log_upload(source_name, len(raw), list(raw.columns))

    dmin = clean_full["order_date"].min().date()
    dmax = clean_full["order_date"].max().date()

    with st.sidebar:
        date_range = st.date_input(
            "Күн аралығы",
            value=(dmin, dmax),
            min_value=dmin,
            max_value=dmax,
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_d, end_d = date_range[0], date_range[1]
        else:
            td = pd.Timestamp(date_range).date()
            start_d = end_d = td

        cats_all = sorted(clean_full["category"].dropna().unique().tolist())
        sel_cats = st.multiselect(
            "Санат / Категория",
            options=cats_all,
            default=cats_all,
            help="Егер баған болмаса, барлық жолдар «Без категории».",
        )

    if not sel_cats:
        st.error("Кемінде бір санат таңдаңыз / Выберите хотя бы одну категорию.")
        st.stop()

    df = an.filter_by_date_range(clean_full, start_d, end_d)
    df = an.filter_by_categories(df, sel_cats)

    if df.empty:
        st.warning("Фильтрлерден кейін дерек жоқ — кезеңді немесе санаттарды кеңейтіңіз.")
        st.stop()

    # --- метрики ---
    mrev = df["line_revenue"].sum()
    n_orders = df["order_id"].nunique()
    n_customers = df["customer_id"].nunique()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Кіріс (фильтр)", f"{mrev:,.0f}")
    c2.metric("Тапсырыс / Заказов", f"{n_orders:,}")
    c3.metric("Клиенттер", f"{n_customers:,}")
    monthly = an.monthly_revenue_series(df)
    fc = an.forecast_next_month_revenue(monthly)
    rfm = an.compute_rfm(df)
    c4.metric(
        "Болжам (келесі ай)",
        f"{fc['predicted_value']:,.0f}" if fc["predicted_value"] == fc["predicted_value"] else "—",
        help=fc.get("note", ""),
    )

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Айлық кіріс", "Топ тауарлар", "RFM сегменттері", "Экспорт және журнал"]
    )

    with tab1:
        st.plotly_chart(an.plotly_monthly_revenue(monthly), use_container_width=True)
        st.plotly_chart(an.plotly_forecast_chart(monthly, fc), use_container_width=True)
        st.caption(fc.get("note", ""))

    with tab2:
        topn = st.slider("Топ (N)", 5, 25, 10)
        top = an.top_products_by_quantity(df, top_n=topn)
        st.dataframe(top, use_container_width=True, hide_index=True)

    with tab3:
        st.plotly_chart(an.plotly_rfm_scatter(rfm), use_container_width=True)
        st.plotly_chart(an.plotly_rfm_treemap(rfm), use_container_width=True)
        with st.expander("RFM кестесі (толық)"):
            st.dataframe(rfm, use_container_width=True, hide_index=True)

    with tab4:
        lines = an.insights_text(monthly, rfm, fc)
        st.subheader("Қысқаша нәтижелер / Краткие итоги")
        for line in lines:
            st.write(line)

        xlsx_bytes = an.rfm_to_excel_bytes(rfm)
        st.download_button(
            label="📥 RFM — Excel (.xlsx)",
            data=xlsx_bytes,
            file_name="rfm_segments.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        pdf_bytes = an.build_pdf_report_bytes(
            title="E-commerce есебі / Отчёт",
            lines=[f"Көз: {source_name}", *lines],
            monthly_revenue=monthly,
            rfm_head=rfm,
        )
        st.download_button(
            label="📄 PDF есеп жүктеу",
            data=pdf_bytes,
            file_name="ecommerce_report.pdf",
            mime="application/pdf",
        )

        st.divider()
        st.subheader("Соңғы жүктемелер / История загрузок (SQLite)")
        logs = recent_uploads(15)
        if not logs:
            st.caption("Әлі жүктеме жоқ (демо режим немесе файл жүктемедіңіз).")
        else:
            st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
