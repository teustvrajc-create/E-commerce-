# E-commerce analytics

Веб-панель (Streamlit), CLI-скрипты және деректерді өңдеу (`analytics.py`): тазалау, айлық кіріс, **RFM**, **linear regression** бойынша болжам, **SQLite** журналы, Excel/PDF экспорт.

## Құрылым / Структура жобаның

| Файл / каталог | Мақсаты |
|----------------|---------|
| `app.py` | Streamlit интерфейсі: CSV жүктеу, күн және санат фильтрлері, Plotly графиктері, экспорт |
| `analytics.py` | Деректерді өңдеу, Plotly фигуралары, болжам, Excel/PDF |
| `database.py` | SQLite (`data/app.sqlite3`) — жүктемелер журналы |
| `.streamlit/config.toml` | Қараңғы тема (dark) үнді по умолчанию |
| `run.py`, `src/ecommerce_analytics/` | Бұрынғы модульдік CLI нұсқасы |
| `ecommerce_analytics_all_in_one.py` | Барлық логика бір файлда (консоль) |
| `data/` | CSV деректері, SQLite файлы |

## Орнату

```bash
cd ecommerce-analytics
pip install -r requirements.txt
```

## Іске қосу (веб)

```bash
streamlit run app.py
```

Браузерде ашылады: файл жүктеңіз немесе «Демо деректер» қалқысымен `data/sales_yearly.csv` қолданыңыз.

**Міндетті бағандар CSV:** `order_id`, `order_date`, `customer_id`, `product_id`, `product_name`, `quantity`, `unit_price`. Қосымша: `category` (санат фильтрі үшін).

## Сынған файлдарды тексеру

- Бос CSV → экранда қате хабары.
- Қажетті бағандар жоқ → қай бағандар керек екені көрсетіледі.
- Тазалаудан кейін бос кесте → күндер форматы / сандық өрістерді тексеріңіз.

## PostgreSQL (қосымша)

Негізгі нұсқа **SQLite** қолданады. Өндірісте PostgreSQL үшін деректерді `pandas.read_sql()` арқылы оқуға болады; ортақ қосылым жолын `DATABASE_URL` түрінде сақтап, `analytics.clean_sales()` қолданыңыз.

## Streamlit Cloud деплой

1. Жобаны GitHub репозиторийіне жіберіңіз.
2. [share.streamlit.io](https://share.streamlit.io) → **New app** → репоны таңдаңыз.
3. **Main file path:** `app.py`.
4. **Python version** 3.11+ ұсынылады.
5. `requirements.txt` автоматты орнатылады.
6. **Secrets** қажет болса: PostgreSQL URI, т.б. — **Settings → Secrets** `toml` арқылы.

Қолданба public сілтеме алады (сіз жариялау режимін қосқаныңызда).

## Тәуелділіктер

`requirements.txt`: pandas, numpy, matplotlib, seaborn (CLI), streamlit, plotly, scikit-learn, openpyxl, reportlab.
