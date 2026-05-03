# AFFILISTAY Admin Dashboard UI - Redeploy 1
import streamlit as st
import re
import pandas as pd
import uuid
import qrcode
import base64
import hashlib
import hmac
import json
from datetime import timedelta
from io import BytesIO
import database
import os
import time
import httpx
import fcm_service

try:
    import altair as alt
except Exception:
    alt = None

st.set_page_config(
    page_title="AffiliStay 파트너 센터",
    page_icon="🛋️",
    layout="wide",
    initial_sidebar_state="expanded"
)
# DB 초기화 (캐시 적용하여 서버 시작 시 1회만 실행)
@st.cache_resource
def initialize_platform():
    database.init_db()
    return True

initialize_platform()

CHECKOUT_BASE_URL = "https://affilistay-showroom.onrender.com"
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_VERIFY_SERVICE_SID = os.getenv("TWILIO_VERIFY_SERVICE_SID", "")
JUSO_API_KEY = os.getenv("JUSO_API_KEY", "")
PHONE_REGEX = re.compile(r"^01[016789]\d{7,8}$")
EMAIL_REGEX = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)
ROOM_MAP = {
    '거실': 'living_room',
    '침실': 'bedroom',
    '주방': 'kitchen',
    '화장실': 'bathroom',
}
ROOM_LABEL_MAP = {value: key for key, value in ROOM_MAP.items()}
ROOM_ICON_MAP = {
    'living_room': '🛋️',
    'bedroom': '🛏️',
    'kitchen': '🍳',
    'bathroom': '🛁',
}
PROD_CAT_OPTIONS = [
    ('🛋️ 가구', 'furniture'),
    ('🧶 패브릭', 'fabric'),
    ('📺 가전·디지털', 'appliance'),
    ('🍳 주방용품', 'kitchenware'),
    ('🥯 식품', 'food'),
    ('🪴 데코·식물', 'deco'),
    ('💡 조명', 'lighting'),
    ('📦 수납·정리', 'storage'),
    ('🛁 생활품', 'lifestyle'),
    ('🔌 헤어드라이어', 'hairdryer'),
]
PROD_CAT_MAP = dict(PROD_CAT_OPTIONS)
PROD_CAT_LABEL_MAP = {value: label for label, value in PROD_CAT_OPTIONS}
VENUE_IMAGE_KEYS = [f"image{i}" for i in range(1, 6)]

st.markdown(
    """
    <style>
    :root {
        --affili-ink: #221f1a;
        --affili-muted: #7d7368;
        --affili-paper: #f7f3ec;
        --affili-card: #fffdfa;
        --affili-line: #e4ddd2;
        --affili-accent: #b9a58f;
    }
    .stApp {
        background: radial-gradient(circle at top, rgba(255,255,255,0.92), rgba(247,243,236,0.96) 38%, #f4efe7 100%) !important;
        color: var(--affili-ink) !important;
    }
    [data-testid="stHeader"] {
        background: rgba(247,243,236,0.82) !important;
        backdrop-filter: blur(18px);
    }
    [data-testid="stSidebar"] {
        background: #fffdfa !important;
        border-right: 1px solid var(--affili-line);
    }
    [data-testid="stSidebar"] * {
        color: var(--affili-ink) !important;
    }
    h1, h2, h3, h4, h5, h6, p, label, span {
        letter-spacing: 0 !important;
    }
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] *,
    [data-testid="stDateInput"] label,
    [data-testid="stDateInput"] label *,
    [data-testid="stSelectbox"] label,
    [data-testid="stSelectbox"] label *,
    [data-testid="stMultiSelect"] label,
    [data-testid="stMultiSelect"] label *,
    [data-testid="stNumberInput"] label,
    [data-testid="stNumberInput"] label *,
    [data-testid="stTextInput"] label,
    [data-testid="stTextInput"] label *,
    [data-testid="stTextArea"] label,
    [data-testid="stTextArea"] label * {
        color: var(--affili-ink) !important;
        opacity: 1 !important;
        font-weight: 800 !important;
    }
    div[data-testid="stForm"], div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--affili-line) !important;
        background: rgba(255,253,250,0.72) !important;
        box-shadow: 0 18px 46px rgba(34,31,26,0.06);
    }
    input, textarea, [data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
        background: #fffdf9 !important;
        border-color: var(--affili-line) !important;
        color: var(--affili-ink) !important;
    }
    input::placeholder, textarea::placeholder {
        color: #b8ad9f !important;
    }
    .stButton > button, .stFormSubmitButton > button {
        border-radius: 16px !important;
        border: 1px solid var(--affili-line) !important;
        background: #fffdfa !important;
        color: var(--affili-ink) !important;
        font-weight: 800 !important;
    }
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
        background: var(--affili-ink) !important;
        border-color: var(--affili-ink) !important;
        color: #fffdf8 !important;
        box-shadow: 0 16px 36px rgba(34,31,26,0.18);
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--affili-ink) !important;
        border-bottom-color: var(--affili-ink) !important;
    }
    div[data-testid="stTabs"] button[role="tab"] * {
        color: var(--affili-muted) !important;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] * {
        color: var(--affili-ink) !important;
    }
    div[data-testid="stForm"] label,
    div[data-testid="stForm"] p,
    div[data-testid="stForm"] span,
    div[data-testid="stVerticalBlockBorderWrapper"] label,
    div[data-testid="stVerticalBlockBorderWrapper"] p,
    div[data-testid="stVerticalBlockBorderWrapper"] span,
    div[role="radiogroup"] label,
    div[role="radiogroup"] span {
        color: var(--affili-ink) !important;
    }
    .affili-login-note {
        color: var(--affili-muted);
        font-size: 0.96rem;
        line-height: 1.65;
        margin: 0.4rem 0 1.4rem;
        text-align: center;
    }
    div[data-testid="stTabs"] button[role="tab"] {
        border-radius: 999px;
        padding: 0.6rem 0.95rem;
        font-weight: 700;
    }
    .host-hero {
        background: linear-gradient(135deg, rgba(255,253,250,0.96), rgba(235,226,214,0.94));
        border-radius: 28px;
        color: var(--affili-ink);
        padding: 1.4rem 1.5rem;
        box-shadow: 0 20px 40px rgba(34, 31, 26, 0.16);
        margin-bottom: 1rem;
    }
    .host-hero-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.9rem;
        margin-top: 1rem;
    }
    .host-chip {
        border: 1px solid rgba(34,31,26,0.12);
        background: rgba(255,255,255,0.58);
        border-radius: 18px;
        padding: 0.95rem 1rem;
    }
    .host-chip-label {
        font-size: 0.8rem;
        opacity: 0.84;
        margin-bottom: 0.2rem;
    }
    .host-chip-value {
        font-size: 1.7rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }
    [data-testid="stMetric"] {
        background: rgba(255,253,250,0.72);
        border: 1px solid var(--affili-line);
        border-radius: 18px;
        padding: 0.9rem 1rem;
        box-shadow: 0 14px 32px rgba(34,31,26,0.045);
    }
    [data-testid="stMetric"] * {
        color: var(--affili-ink) !important;
    }
    [data-testid="stDataFrame"] * {
        color: var(--affili-ink) !important;
    }
    .insight-note {
        border: 1px solid var(--affili-line);
        border-radius: 18px;
        background: rgba(255,253,250,0.78);
        color: var(--affili-ink);
        padding: 0.9rem 1rem;
        line-height: 1.55;
        margin: 0.4rem 0 0.8rem;
    }
    .insight-note strong {
        color: var(--affili-ink);
    }
    .section-card {
        border: 1px solid rgba(34,31,26,0.08);
        border-radius: 24px;
        padding: 1rem;
        background: rgba(255,253,250,0.82);
        color: var(--affili-ink);
    }
    .section-title {
        font-size: 1rem;
        font-weight: 800;
        margin-bottom: 0.25rem;
    }
    .section-copy {
        color: var(--affili-muted);
        font-size: 0.92rem;
        margin-bottom: 0.85rem;
    }
    .guide-card {
        border: 1px solid rgba(34,31,26,0.08);
        border-radius: 24px;
        padding: 1rem 1.05rem;
        background: rgba(255,253,250,0.84);
        color: var(--affili-ink);
        margin-bottom: 0.9rem;
        box-shadow: 0 14px 34px rgba(34,31,26,0.045);
    }
    .guide-kicker {
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: var(--affili-accent);
        margin-bottom: 0.45rem;
    }
    .guide-title {
        font-size: 1.08rem;
        font-weight: 800;
        margin-bottom: 0.35rem;
        color: var(--affili-ink);
    }
    .guide-copy {
        font-size: 0.92rem;
        color: var(--affili-muted);
        line-height: 1.6;
    }
    .guide-list {
        display: grid;
        gap: 0.55rem;
        margin-top: 0.8rem;
    }
    .guide-step {
        border-radius: 18px;
        padding: 0.8rem 0.9rem;
        background: rgba(255,255,255,0.72);
        border: 1px solid var(--affili-line);
    }
    .guide-step strong {
        display: block;
        font-size: 0.92rem;
        margin-bottom: 0.2rem;
    }
    .guide-step span {
        display: block;
        font-size: 0.84rem;
        line-height: 1.55;
        color: var(--affili-muted);
    }
    @media (max-width: 900px) {
        .host-hero-grid {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────
# 헬퍼 함수
# ─────────────────────────────────────────
def make_qr(url: str) -> BytesIO:
    qr = qrcode.QRCode(version=1, box_size=8, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#2C2520", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def ph(text="이미지 없음"):
    """이미지가 없을 때 표시할 플레이스홀더"""
    st.markdown(
        f"<div style='background:#F0EBE3;border-radius:12px;padding:32px;text-align:center;"
        f"color:#9C9288;font-size:12px;'>{text}</div>",
        unsafe_allow_html=True
    )

def show_img(b64_str, width=280):
    if b64_str:
        try:
            st.image(database.base64_to_bytes(b64_str), width=width)
        except Exception:
            ph()
    else:
        ph()


def build_options_text(option_rows):
    return "\n".join(f"{name}: {values}" for name, values in option_rows)


def parse_option_lines(options_raw):
    option_lines = []
    for raw_line in options_raw.splitlines():
        if ":" not in raw_line:
            continue
        name, values = [piece.strip() for piece in raw_line.split(":", 1)]
        if name and values:
            option_lines.append((name, values))
    return option_lines


def replace_product_media(cursor, product_id, uploaded_files):
    if database.DATABASE_URL:
        cursor.execute("DELETE FROM product_images WHERE product_id=%s", (product_id,))
        insert_query = "INSERT INTO product_images (product_id, image_data, sort_order) VALUES (%s,%s,%s)"
    else:
        cursor.execute("DELETE FROM product_images WHERE product_id=?", (product_id,))
        insert_query = "INSERT INTO product_images (product_id, image_data, sort_order) VALUES (?,?,?)"

    for index, img_file in enumerate(uploaded_files):
        cursor.execute(insert_query, (product_id, database.file_to_base64(img_file), index))


def replace_product_options(cursor, product_id, options_raw):
    if database.DATABASE_URL:
        cursor.execute("DELETE FROM product_options WHERE product_id=%s", (product_id,))
        insert_query = 'INSERT INTO product_options (product_id, name, "values") VALUES (%s,%s,%s)'
    else:
        cursor.execute("DELETE FROM product_options WHERE product_id=?", (product_id,))
        insert_query = 'INSERT INTO product_options (product_id, name, "values") VALUES (?,?,?)'

    for name, values in parse_option_lines(options_raw):
        cursor.execute(insert_query, (product_id, name, values))


def calc_host_share(row):
    original_price = row.get('original_price') or row.get('price') or 0
    sale_price = row.get('price') or 0
    gap = max(int(original_price) - int(sale_price), 0)
    return int(gap * 0.5)


def load_host_income_snapshot(host_id):
    conn = database.get_db_connection()
    query = (
        """
        SELECT o.id, o.total_amount, o.created_at, o.payment_status, o.settlement_status,
               p.price, p.original_price
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE p.owner_id = %s
        ORDER BY o.created_at DESC
        """
        if database.DATABASE_URL else
        """
        SELECT o.id, o.total_amount, o.created_at, o.payment_status, o.settlement_status,
               p.price, p.original_price
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE p.owner_id = ?
        ORDER BY o.created_at DESC
        """
    )
    orders = pd.read_sql_query(query, conn, params=(host_id,))

    count_query = (
        "SELECT COUNT(*) AS count FROM products WHERE owner_id=%s"
        if database.DATABASE_URL else
        "SELECT COUNT(*) AS count FROM products WHERE owner_id=?"
    )
    live_products = int(pd.read_sql_query(count_query, conn, params=(host_id,)).iloc[0]["count"])
    conn.close()

    if orders.empty:
        return {
            "week_income": 0,
            "month_income": 0,
            "week_sales": 0,
            "month_sales": 0,
            "live_products": live_products,
            "order_count": 0,
        }

    orders["created_at"] = pd.to_datetime(orders["created_at"], errors="coerce")
    orders["host_share"] = orders.apply(calc_host_share, axis=1)

    now = pd.Timestamp.now(tz=None)
    week_cutoff = now - pd.Timedelta(days=7)
    month_cutoff = now - pd.Timedelta(days=30)
    weekly = orders[orders["created_at"] >= week_cutoff]
    monthly = orders[orders["created_at"] >= month_cutoff]

    return {
        "week_income": int(weekly["host_share"].sum()),
        "month_income": int(monthly["host_share"].sum()),
        "week_sales": int(weekly["total_amount"].sum()),
        "month_sales": int(monthly["total_amount"].sum()),
        "live_products": live_products,
        "order_count": int(len(orders)),
    }


# 작업 4: analytics_events 기반 인사이트 대시보드 데이터 로드
def load_analytics_events(start_date, end_date, host_id=None, is_master=False):
    conn = database.get_db_connection()
    end_exclusive = pd.Timestamp(end_date) + pd.Timedelta(days=1)
    params = [
        pd.Timestamp(start_date).strftime("%Y-%m-%d 00:00:00"),
        end_exclusive.strftime("%Y-%m-%d 00:00:00"),
    ]
    where = ["ae.timestamp >= %s", "ae.timestamp < %s"] if database.DATABASE_URL else ["ae.timestamp >= ?", "ae.timestamp < ?"]
    if not is_master and host_id:
        where.append("p.owner_id = %s" if database.DATABASE_URL else "p.owner_id = ?")
        params.append(host_id)

    query = f"""
        SELECT
            ae.id, ae.event_type, ae.product_id, ae.stay_id, ae.location, ae.checkin_day,
            ae.duration_seconds, ae.scroll_depth, ae.is_return_visit, ae.is_purchased,
            ae.device_type, ae.browser_language, ae.timestamp,
            p.product_name, p.brand_name, p.owner_id, p.product_category, p.room_category, h.name AS host_name,
            hv.location AS venue_location
        FROM analytics_events ae
        LEFT JOIN products p ON ae.product_id = p.id
        LEFT JOIN hosts h ON p.owner_id = h.id
        LEFT JOIN host_venues hv ON h.id = hv.host_id
        WHERE {' AND '.join(where)}
        ORDER BY ae.timestamp DESC
    """
    try:
        df = pd.read_sql_query(query, conn, params=tuple(params))
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df


def load_purchase_orders(start_date, end_date, host_id=None, is_master=False):
    conn = database.get_db_connection()
    end_exclusive = pd.Timestamp(end_date) + pd.Timedelta(days=1)
    params = [
        pd.Timestamp(start_date).strftime("%Y-%m-%d 00:00:00"),
        end_exclusive.strftime("%Y-%m-%d 00:00:00"),
    ]
    where = ["o.created_at >= %s", "o.created_at < %s", "o.payment_status = 'PAID'"] if database.DATABASE_URL else ["o.created_at >= ?", "o.created_at < ?", "o.payment_status = 'PAID'"]
    if not is_master and host_id:
        where.append("p.owner_id = %s" if database.DATABASE_URL else "p.owner_id = ?")
        params.append(host_id)

    query = f"""
        SELECT
            o.id, o.product_id, o.customer_id, o.total_amount, o.created_at,
            COALESCE(o.customer_age_group, c.age_group) AS customer_age_group,
            COALESCE(o.customer_gender, c.gender) AS customer_gender,
            p.product_name, p.brand_name, p.owner_id, p.product_category, p.room_category,
            h.name AS host_name,
            hv.location AS venue_location
        FROM orders o
        LEFT JOIN products p ON o.product_id = p.id
        LEFT JOIN hosts h ON p.owner_id = h.id
        LEFT JOIN host_venues hv ON h.id = hv.host_id
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE {' AND '.join(where)}
        ORDER BY o.created_at DESC
    """
    try:
        df = pd.read_sql_query(query, conn, params=tuple(params))
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df


def load_wishlist_events(start_date, end_date, host_id=None, is_master=False):
    conn = database.get_db_connection()
    end_exclusive = pd.Timestamp(end_date) + pd.Timedelta(days=1)
    params = [
        pd.Timestamp(start_date).strftime("%Y-%m-%d 00:00:00"),
        end_exclusive.strftime("%Y-%m-%d 00:00:00"),
    ]
    where = ["w.created_at >= %s", "w.created_at < %s"] if database.DATABASE_URL else ["w.created_at >= ?", "w.created_at < ?"]
    if not is_master and host_id:
        where.append("p.owner_id = %s" if database.DATABASE_URL else "p.owner_id = ?")
        params.append(host_id)

    query = f"""
        SELECT
            w.id, w.customer_id, w.product_id, w.qr_code_id, w.host_id, w.purchased,
            w.reminder_status, w.created_at, w.updated_at,
            COALESCE(c.age_group, '') AS customer_age_group,
            COALESCE(c.gender, '') AS customer_gender,
            p.product_name, p.brand_name, p.owner_id, p.product_category, p.room_category,
            h.name AS host_name,
            hv.location AS venue_location
        FROM wishlist_events w
        LEFT JOIN products p ON w.product_id = p.id
        LEFT JOIN hosts h ON p.owner_id = h.id
        LEFT JOIN host_venues hv ON h.id = hv.host_id
        LEFT JOIN customers c ON w.customer_id = c.id
        WHERE {' AND '.join(where)}
        ORDER BY w.created_at DESC
    """
    try:
        df = pd.read_sql_query(query, conn, params=tuple(params))
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df


def analytics_truthy(value):
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def analytics_int_mean(series):
    mean_value = pd.to_numeric(series, errors="coerce").dropna().mean()
    if pd.isna(mean_value):
        return 0
    return int(mean_value)


def clean_insight_label(value, fallback="미입력"):
    text = str(value or "").strip()
    return text if text else fallback


def normalize_age_group(value):
    return {
        "10s": "10대",
        "20s": "20대",
        "30s": "30대",
        "40s": "40대",
        "50s": "50대",
        "60s_plus": "60대 이상",
        "unknown": "선택 안 함",
    }.get(str(value or "").strip(), "미입력")


def normalize_gender(value):
    return {
        "female": "여성",
        "male": "남성",
        "other": "기타",
        "unknown": "선택 안 함",
    }.get(str(value or "").strip(), "미입력")


def render_insight_bar(series, order=None, height=280, x_title="", y_title="건수"):
    data = series.copy()
    if order is not None:
        data = data.reindex(order, fill_value=0)
    data = data.reset_index()
    data.columns = ["항목", "건수"]
    data["항목"] = data["항목"].astype(str)
    data["건수"] = pd.to_numeric(data["건수"], errors="coerce").fillna(0)
    if alt:
        chart = (
            alt.Chart(data)
            .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5, color="#b9a58f")
            .encode(
                x=alt.X(
                    "항목:N",
                    sort=None,
                    title=x_title,
                    axis=alt.Axis(labelAngle=0, labelLimit=160, labelOverlap=False),
                ),
                y=alt.Y("건수:Q", title=y_title, axis=alt.Axis(tickMinStep=1)),
                tooltip=["항목:N", "건수:Q"],
            )
            .properties(height=height, background="#fffdfa")
            .configure_axis(labelColor="#221f1a", titleColor="#5f554c", gridColor="#ece4d9")
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(data.set_index("항목"), height=height)


def normalize_analytics_location(value):
    location = str(value or "").strip()
    return {
        "bedroom": "침실",
        "livingroom": "거실",
        "living_room": "거실",
        "bathroom": "욕실",
        "kitchen": "주방",
    }.get(location, location or "미분류")


def normalize_product_category(value):
    category = str(value or "").strip()
    return PROD_CAT_LABEL_MAP.get(category, category or "미분류")


def normalize_room_category(value):
    room = str(value or "").strip()
    return ROOM_LABEL_MAP.get(room, normalize_analytics_location(room))


def safe_rate(numerator, denominator):
    return round((numerator / denominator * 100), 1) if denominator else 0.0


def render_insight_rate_bar(df, category_col, value_col, height=280, x_title="", y_title="비율(%)"):
    if df.empty:
        st.info("표시할 데이터가 없습니다.")
        return
    chart_data = df[[category_col, value_col]].copy()
    chart_data[category_col] = chart_data[category_col].astype(str)
    chart_data[value_col] = pd.to_numeric(chart_data[value_col], errors="coerce").fillna(0)
    if alt:
        chart = (
            alt.Chart(chart_data)
            .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5, color="#b9a58f")
            .encode(
                x=alt.X(f"{category_col}:N", sort=None, title=x_title, axis=alt.Axis(labelAngle=0, labelLimit=160, labelOverlap=False)),
                y=alt.Y(f"{value_col}:Q", title=y_title),
                tooltip=[category_col, alt.Tooltip(f"{value_col}:Q", format=".1f")],
            )
            .properties(height=height, background="#fffdfa")
            .configure_axis(labelColor="#221f1a", titleColor="#5f554c", gridColor="#ece4d9")
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(chart_data.set_index(category_col), height=height)


def demographic_rate_table(wishlist_df, orders_df, group_col, ordered_labels=None):
    labels = pd.concat(
        [
            wishlist_df[group_col] if group_col in wishlist_df else pd.Series(dtype="object"),
            orders_df[group_col] if group_col in orders_df else pd.Series(dtype="object"),
        ],
        ignore_index=True,
    ).dropna().astype(str).unique().tolist()
    if ordered_labels:
        labels = [label for label in ordered_labels if label in labels] + sorted([label for label in labels if label not in ordered_labels])
    else:
        labels = sorted(labels)

    total_wishlist = len(wishlist_df)
    total_orders = len(orders_df)
    rows = []
    for label in labels:
        wishlist_group = wishlist_df[wishlist_df[group_col].astype(str) == label] if group_col in wishlist_df else pd.DataFrame()
        order_group = orders_df[orders_df[group_col].astype(str) == label] if group_col in orders_df else pd.DataFrame()
        wishlist_count = len(wishlist_group)
        purchase_count = len(order_group)
        purchased_wishlist_count = int(wishlist_group["purchased_bool"].sum()) if "purchased_bool" in wishlist_group else 0
        rows.append({
            "항목": label,
            "찜 수": wishlist_count,
            "구매 수": purchase_count,
            "찜 비중(%)": safe_rate(wishlist_count, total_wishlist),
            "구매 비중(%)": safe_rate(purchase_count, total_orders),
            "찜 후 구매율(%)": safe_rate(purchased_wishlist_count, wishlist_count),
        })
    return pd.DataFrame(rows)


def dataframe_to_excel_bytes(sheets):
    buffer = BytesIO()
    invalid_sheet_chars = set('[]:*?/\\')
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            safe_name = "".join("_" if char in invalid_sheet_chars else char for char in str(sheet_name))[:31] or "Sheet"
            export_df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame(df)
            export_df.to_excel(writer, sheet_name=safe_name, index=False)
    buffer.seek(0)
    return buffer


def render_insights_dashboard(host_id, is_master):
    # 작업 4: 관리자/호스트/입점업체 공통 인사이트 탭
    st.subheader("📊 쇼룸 인사이트")
    st.caption("QR 상세페이지에서 수집한 조회, 재방문, 찜, 장바구니, 구매 데이터를 입점업체 관점의 전환 신호로 정리합니다.")

    today = pd.Timestamp.now().date()
    default_start = today - pd.Timedelta(days=30)
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        selected_range = st.date_input("날짜 범위", value=(default_start, today), key=f"insight_range_{host_id}_{is_master}")
    if isinstance(selected_range, tuple):
        if len(selected_range) < 2:
            st.info("날짜 범위의 시작일과 종료일을 모두 선택해 주세요.")
            return
        start_date, end_date = selected_range
    else:
        start_date = selected_range
        end_date = selected_range

    events = load_analytics_events(start_date, end_date, host_id=host_id, is_master=is_master)
    purchase_orders = load_purchase_orders(start_date, end_date, host_id=host_id, is_master=is_master)
    wishlist_events = load_wishlist_events(start_date, end_date, host_id=host_id, is_master=is_master)
    if events.empty and purchase_orders.empty and wishlist_events.empty:
        with f2:
            st.selectbox("숙소 선택", ["전체 숙소"], disabled=True)
        with f3:
            st.selectbox("입점업체 선택", ["전체 입점업체"], disabled=True)
        with f4:
            st.selectbox("숙소 위치", ["전체 위치"], disabled=True)
        st.info("아직 수집된 인사이트 데이터가 없습니다. QR 상세페이지 방문, 찜, 구매가 쌓이면 여기에 표시됩니다.")
        return

    event_columns = [
        "event_type", "product_id", "location", "checkin_day", "duration_seconds", "scroll_depth",
        "is_return_visit", "is_purchased", "device_type", "browser_language", "timestamp",
        "product_name", "brand_name", "host_name", "venue_location", "product_category", "room_category",
    ]
    order_columns = [
        "product_id", "product_name", "brand_name", "host_name", "venue_location", "product_category",
        "room_category", "customer_age_group", "customer_gender", "created_at",
    ]
    wishlist_columns = [
        "product_id", "product_name", "brand_name", "host_name", "venue_location", "product_category",
        "room_category", "customer_age_group", "customer_gender", "purchased", "created_at",
    ]
    for column in event_columns:
        if column not in events.columns:
            events[column] = pd.Series(dtype="object")
    for column in order_columns:
        if column not in purchase_orders.columns:
            purchase_orders[column] = pd.Series(dtype="object")
    for column in wishlist_columns:
        if column not in wishlist_events.columns:
            wishlist_events[column] = pd.Series(dtype="object")

    events["timestamp"] = pd.to_datetime(events["timestamp"], errors="coerce")
    events["duration_seconds"] = pd.to_numeric(events["duration_seconds"], errors="coerce")
    events["scroll_depth"] = pd.to_numeric(events["scroll_depth"], errors="coerce")
    events["is_return_bool"] = events["is_return_visit"].apply(analytics_truthy)
    events["is_purchase_bool"] = events["is_purchased"].apply(analytics_truthy)
    events["location_label"] = events["location"].apply(normalize_analytics_location)
    events["product_name"] = events["product_name"].fillna("미등록 제품")
    events["brand_name"] = events["brand_name"].fillna("브랜드 미입력")
    events["host_name"] = events["host_name"].fillna("미분류 숙소")
    events["venue_location_label"] = events["venue_location"].apply(lambda value: clean_insight_label(value, "위치 미입력"))
    events["product_category_label"] = events["product_category"].apply(normalize_product_category)
    events["room_category_label"] = events["room_category"].apply(normalize_room_category)

    purchase_orders["created_at"] = pd.to_datetime(purchase_orders["created_at"], errors="coerce")
    purchase_orders["product_name"] = purchase_orders["product_name"].fillna("미등록 제품")
    purchase_orders["brand_name"] = purchase_orders["brand_name"].fillna("브랜드 미입력")
    purchase_orders["host_name"] = purchase_orders["host_name"].fillna("미분류 숙소")
    purchase_orders["venue_location_label"] = purchase_orders["venue_location"].apply(lambda value: clean_insight_label(value, "위치 미입력"))
    purchase_orders["product_category_label"] = purchase_orders["product_category"].apply(normalize_product_category)
    purchase_orders["room_category_label"] = purchase_orders["room_category"].apply(normalize_room_category)
    purchase_orders["age_group_label"] = purchase_orders["customer_age_group"].apply(normalize_age_group)
    purchase_orders["gender_label"] = purchase_orders["customer_gender"].apply(normalize_gender)

    wishlist_events["created_at"] = pd.to_datetime(wishlist_events["created_at"], errors="coerce")
    wishlist_events["product_name"] = wishlist_events["product_name"].fillna("미등록 제품")
    wishlist_events["brand_name"] = wishlist_events["brand_name"].fillna("브랜드 미입력")
    wishlist_events["host_name"] = wishlist_events["host_name"].fillna("미분류 숙소")
    wishlist_events["venue_location_label"] = wishlist_events["venue_location"].apply(lambda value: clean_insight_label(value, "위치 미입력"))
    wishlist_events["product_category_label"] = wishlist_events["product_category"].apply(normalize_product_category)
    wishlist_events["room_category_label"] = wishlist_events["room_category"].apply(normalize_room_category)
    wishlist_events["age_group_label"] = wishlist_events["customer_age_group"].apply(normalize_age_group)
    wishlist_events["gender_label"] = wishlist_events["customer_gender"].apply(normalize_gender)
    wishlist_events["purchased_bool"] = wishlist_events["purchased"].apply(analytics_truthy)

    host_values = pd.concat([events["host_name"], purchase_orders["host_name"], wishlist_events["host_name"]], ignore_index=True).dropna()
    with f2:
        host_options = ["전체 숙소"] + sorted(host_values.unique().tolist())
        selected_host = st.selectbox("숙소 선택", host_options, key=f"insight_host_{host_id}_{is_master}")

    filtered = events.copy()
    filtered_orders = purchase_orders.copy()
    filtered_wishlist = wishlist_events.copy()
    if selected_host != "전체 숙소":
        filtered = filtered[filtered["host_name"] == selected_host]
        filtered_orders = filtered_orders[filtered_orders["host_name"] == selected_host]
        filtered_wishlist = filtered_wishlist[filtered_wishlist["host_name"] == selected_host]

    brand_values = pd.concat([filtered["brand_name"], filtered_orders["brand_name"], filtered_wishlist["brand_name"]], ignore_index=True).dropna()
    with f3:
        brand_options = ["전체 입점업체"] + sorted(brand_values.unique().tolist())
        selected_brand = st.selectbox("입점업체 선택", brand_options, key=f"insight_brand_{host_id}_{is_master}")

    if selected_brand != "전체 입점업체":
        filtered = filtered[filtered["brand_name"] == selected_brand]
        filtered_orders = filtered_orders[filtered_orders["brand_name"] == selected_brand]
        filtered_wishlist = filtered_wishlist[filtered_wishlist["brand_name"] == selected_brand]

    venue_values = pd.concat([filtered["venue_location_label"], filtered_orders["venue_location_label"], filtered_wishlist["venue_location_label"]], ignore_index=True).dropna()
    with f4:
        venue_options = ["전체 위치"] + sorted(venue_values.unique().tolist())
        selected_venue = st.selectbox("숙소 위치", venue_options, key=f"insight_venue_{host_id}_{is_master}")

    if selected_venue != "전체 위치":
        filtered = filtered[filtered["venue_location_label"] == selected_venue]
        filtered_orders = filtered_orders[filtered_orders["venue_location_label"] == selected_venue]
        filtered_wishlist = filtered_wishlist[filtered_wishlist["venue_location_label"] == selected_venue]

    f5, f6 = st.columns(2)
    product_values = pd.concat([filtered["product_name"], filtered_orders["product_name"], filtered_wishlist["product_name"]], ignore_index=True).dropna()
    with f5:
        product_options = ["전체 제품"] + sorted(product_values.unique().tolist())
        selected_product = st.selectbox("제품 선택", product_options, key=f"insight_product_{host_id}_{is_master}")

    category_values = pd.concat([filtered["product_category_label"], filtered_orders["product_category_label"], filtered_wishlist["product_category_label"]], ignore_index=True).dropna()
    with f6:
        category_options = ["전체 카테고리"] + sorted(category_values.unique().tolist())
        selected_category = st.selectbox("제품 카테고리", category_options, key=f"insight_category_{host_id}_{is_master}")

    if selected_product != "전체 제품":
        filtered = filtered[filtered["product_name"] == selected_product]
        filtered_orders = filtered_orders[filtered_orders["product_name"] == selected_product]
        filtered_wishlist = filtered_wishlist[filtered_wishlist["product_name"] == selected_product]
    if selected_category != "전체 카테고리":
        filtered = filtered[filtered["product_category_label"] == selected_category]
        filtered_orders = filtered_orders[filtered_orders["product_category_label"] == selected_category]
        filtered_wishlist = filtered_wishlist[filtered_wishlist["product_category_label"] == selected_category]

    if filtered.empty and filtered_orders.empty and filtered_wishlist.empty:
        st.info("선택한 조건에 맞는 데이터가 없습니다.")
        return

    page_views = filtered[filtered["event_type"] == "page_view"]
    cart_events = filtered[filtered["event_type"] == "cart"]
    purchase_events = filtered[(filtered["event_type"] == "purchase") | (filtered["is_purchase_bool"])]
    purchase_count = len(purchase_events) + len(filtered_orders)
    returning_views = page_views[page_views["is_return_bool"]]
    returning_product_ids = set(returning_views["product_id"].dropna().astype(str))
    returning_purchase_events = purchase_events[purchase_events["is_return_bool"]]
    returning_orders = filtered_orders[filtered_orders["product_id"].astype(str).isin(returning_product_ids)] if returning_product_ids else filtered_orders.iloc[0:0]
    return_purchase_count = len(returning_purchase_events) + len(returning_orders)

    total_views = len(page_views)
    c1, c2, c3 = st.columns(3)
    c1.metric("제품 조회", f"{total_views:,}회")
    c2.metric("평균 체류", f"{analytics_int_mean(page_views['duration_seconds']):,}초")
    c3.metric("찜 전환율", f"{safe_rate(len(filtered_wishlist), total_views):.1f}%")
    c4, c5, c6 = st.columns(3)
    c4.metric("장바구니율", f"{safe_rate(len(cart_events), total_views):.1f}%")
    c5.metric("구매 전환율", f"{safe_rate(purchase_count, total_views):.1f}%")
    c6.metric("재방문 후 구매율", f"{safe_rate(return_purchase_count, len(returning_views)):.1f}%")

    st.markdown("#### 제품별 통계")
    product_names = sorted(pd.concat([filtered["product_name"], filtered_orders["product_name"], filtered_wishlist["product_name"]], ignore_index=True).dropna().unique().tolist())
    rows = []
    for product_name in product_names:
        group = filtered[filtered["product_name"] == product_name]
        order_group = filtered_orders[filtered_orders["product_name"] == product_name]
        wishlist_group = filtered_wishlist[filtered_wishlist["product_name"] == product_name]
        product_views = group[group["event_type"] == "page_view"]
        product_carts = group[group["event_type"] == "cart"]
        product_purchases = group[(group["event_type"] == "purchase") | (group["is_purchase_bool"])]
        views = len(product_views)
        total_product_purchases = len(product_purchases) + len(order_group)
        interest_count = len(wishlist_group) + len(product_carts)
        rows.append({
            "입점업체": (pd.concat([group["brand_name"], order_group["brand_name"], wishlist_group["brand_name"]], ignore_index=True).dropna().iloc[0]
                     if not pd.concat([group["brand_name"], order_group["brand_name"], wishlist_group["brand_name"]], ignore_index=True).dropna().empty else "브랜드 미입력"),
            "제품명": product_name,
            "조회수": views,
            "찜 수": len(wishlist_group),
            "장바구니 수": len(product_carts),
            "구매수": total_product_purchases,
            "평균 체류시간(초)": analytics_int_mean(product_views["duration_seconds"]),
            "평균 스크롤 깊이(%)": analytics_int_mean(group["scroll_depth"]),
            "찜 전환율(%)": safe_rate(len(wishlist_group), views),
            "장바구니율(%)": safe_rate(len(product_carts), views),
            "구매 전환율(%)": safe_rate(total_product_purchases, views),
            "관심 후 구매율(%)": safe_rate(total_product_purchases, interest_count),
            "재방문 조회수": int(product_views["is_return_bool"].sum()) if "is_return_bool" in product_views else 0,
        })
    product_stats_df = pd.DataFrame(rows)
    if not product_stats_df.empty:
        product_stats_df = product_stats_df.sort_values(["조회수", "구매수"], ascending=False)
        st.dataframe(product_stats_df, use_container_width=True, hide_index=True)
    else:
        st.info("제품별 통계를 만들 데이터가 아직 없습니다.")

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.markdown("#### 제품 위치별 스캔 현황")
        location_counts = page_views["location_label"].value_counts()
        render_insight_bar(location_counts, order=["침실", "거실", "욕실", "주방", "미분류"])

    with chart_col2:
        st.markdown("#### 시간대별 스캔 분포")
        hourly = page_views.dropna(subset=["timestamp"]).assign(hour=lambda df: df["timestamp"].dt.hour.astype(str))
        hour_counts = hourly["hour"].value_counts().reindex([str(hour) for hour in range(24)], fill_value=0)
        render_insight_bar(hour_counts, height=280, x_title="시간대")

    revisit_col1, revisit_col2 = st.columns(2)
    with revisit_col1:
        st.markdown("#### 재방문 시간대")
        returning_hourly = returning_views.dropna(subset=["timestamp"]).assign(hour=lambda df: df["timestamp"].dt.hour.astype(str))
        returning_hour_counts = returning_hourly["hour"].value_counts().reindex([str(hour) for hour in range(24)], fill_value=0)
        render_insight_bar(returning_hour_counts, height=260, x_title="시간대")

    with revisit_col2:
        st.markdown("#### 구매 전환율 높은 시간대")
        view_hour_counts = hourly["hour"].value_counts().reindex([str(hour) for hour in range(24)], fill_value=0) if not page_views.empty else pd.Series(0, index=[str(hour) for hour in range(24)])
        order_hours = filtered_orders.dropna(subset=["created_at"]).assign(hour=lambda df: df["created_at"].dt.hour.astype(str))
        purchase_event_hours = purchase_events.dropna(subset=["timestamp"]).assign(hour=lambda df: df["timestamp"].dt.hour.astype(str))
        purchase_hour_counts = (
            order_hours["hour"].value_counts().reindex([str(hour) for hour in range(24)], fill_value=0)
            + purchase_event_hours["hour"].value_counts().reindex([str(hour) for hour in range(24)], fill_value=0)
        )
        hourly_conversion_df = pd.DataFrame({
            "시간대": [f"{hour}시" for hour in range(24)],
            "조회수": view_hour_counts.values,
            "구매수": purchase_hour_counts.values,
        })
        hourly_conversion_df["구매 전환율(%)"] = hourly_conversion_df.apply(lambda row: safe_rate(row["구매수"], row["조회수"]), axis=1)
        render_insight_rate_bar(hourly_conversion_df, "시간대", "구매 전환율(%)", height=260, x_title="시간대")

    weekday_order = ["월", "화", "수", "목", "금", "토", "일"]
    order_weekdays = filtered_orders.dropna(subset=["created_at"]).assign(
        weekday=lambda df: df["created_at"].dt.dayofweek.map({0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"})
    )
    purchase_event_weekdays = purchase_events.dropna(subset=["timestamp"]).assign(
        weekday=lambda df: df["timestamp"].dt.dayofweek.map({0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"})
    )
    weekday_purchase_counts = (
        order_weekdays["weekday"].value_counts().reindex(weekday_order, fill_value=0)
        + purchase_event_weekdays["weekday"].value_counts().reindex(weekday_order, fill_value=0)
    )
    weekday_purchase_df = weekday_purchase_counts.reset_index()
    weekday_purchase_df.columns = ["요일", "구매수"]

    weekday_purchase_col1, weekday_purchase_col2 = st.columns(2)
    with weekday_purchase_col1:
        st.markdown("#### 요일별 구매 현황")
        render_insight_bar(weekday_purchase_counts, order=weekday_order, height=240, x_title="요일")
    with weekday_purchase_col2:
        st.markdown("#### 주중/주말 구매 현황")
        weekday_purchase_type = pd.Series({
            "주중": int(weekday_purchase_counts.reindex(["월", "화", "수", "목", "금"], fill_value=0).sum()),
            "주말": int(weekday_purchase_counts.reindex(["토", "일"], fill_value=0).sum()),
        })
        render_insight_bar(weekday_purchase_type, order=["주중", "주말"], height=240)

    venue_col1, venue_col2 = st.columns(2)
    with venue_col1:
        st.markdown("#### 숙소 위치별 스캔")
        venue_scan_counts = page_views["venue_location_label"].value_counts()
        render_insight_bar(venue_scan_counts)
    with venue_col2:
        st.markdown("#### 숙소 위치별 구매")
        venue_purchase_counts = filtered_orders["venue_location_label"].value_counts()
        if venue_purchase_counts.empty:
            st.info("아직 구매 데이터가 없습니다.")
        else:
            render_insight_bar(venue_purchase_counts)

    pattern_col1, pattern_col2, pattern_col3, pattern_col4 = st.columns(4)
    with pattern_col1:
        weekday_counts = page_views.dropna(subset=["timestamp"]).assign(
            visit_type=lambda df: df["timestamp"].dt.dayofweek.apply(lambda day: "주말" if day >= 5 else "주중")
        )["visit_type"].value_counts()
        st.markdown("#### 주중 vs 주말")
        render_insight_bar(weekday_counts, order=["주중", "주말"], height=220)

    with pattern_col2:
        language_counts = page_views["browser_language"].fillna("").apply(
            lambda lang: "국내" if str(lang).lower().startswith("ko") else "해외"
        ).value_counts()
        st.markdown("#### 국내/해외")
        render_insight_bar(language_counts, order=["국내", "해외"], height=220)

    with pattern_col3:
        device_counts = page_views["device_type"].fillna("unknown").value_counts()
        st.markdown("#### 디바이스")
        render_insight_bar(device_counts, height=220)

    with pattern_col4:
        return_rate = page_views["is_return_bool"].mean() * 100 if not page_views.empty else 0
        st.markdown("#### 재방문율")
        st.metric("재방문 비율", f"{return_rate:.1f}%")
        checkin = page_views["checkin_day"].dropna()
        if not checkin.empty:
            st.metric("평균 체크인 일차", f"{checkin.mean():.1f}일차")

    st.markdown("#### 연령대/성별별 찜·구매 비율")
    age_order = ["10대", "20대", "30대", "40대", "50대", "60대 이상", "선택 안 함", "미입력"]
    gender_order = ["여성", "남성", "기타", "선택 안 함", "미입력"]
    age_rate_df = demographic_rate_table(filtered_wishlist, filtered_orders, "age_group_label", age_order)
    gender_rate_df = demographic_rate_table(filtered_wishlist, filtered_orders, "gender_label", gender_order)
    demographic_col1, demographic_col2 = st.columns(2)
    with demographic_col1:
        st.markdown("##### 연령대")
        if age_rate_df.empty:
            st.info("연령대 데이터가 아직 없습니다.")
        else:
            st.dataframe(age_rate_df, use_container_width=True, hide_index=True)
            render_insight_rate_bar(age_rate_df, "항목", "찜 후 구매율(%)", height=220)
    with demographic_col2:
        st.markdown("##### 성별")
        if gender_rate_df.empty:
            st.info("성별 데이터가 아직 없습니다.")
        else:
            st.dataframe(gender_rate_df, use_container_width=True, hide_index=True)
            render_insight_rate_bar(gender_rate_df, "항목", "찜 후 구매율(%)", height=220)

    st.markdown("#### 입점업체 액션 신호")
    category_stats_df = pd.DataFrame()
    if not product_stats_df.empty:
        no_purchase_interest = product_stats_df[(product_stats_df["찜 수"] + product_stats_df["장바구니 수"] > 0) & (product_stats_df["구매수"] == 0)]
        best_hour_row = hourly_conversion_df.sort_values(["구매 전환율(%)", "구매수"], ascending=False).head(1)
        category_rows = []
        category_names = sorted(pd.concat([filtered["product_category_label"], filtered_orders["product_category_label"], filtered_wishlist["product_category_label"]], ignore_index=True).dropna().unique().tolist())
        for category in category_names:
            category_views = len(page_views[page_views["product_category_label"] == category])
            category_wishlist = len(filtered_wishlist[filtered_wishlist["product_category_label"] == category])
            category_orders = len(filtered_orders[filtered_orders["product_category_label"] == category])
            category_rows.append({
                "카테고리": category,
                "조회수": category_views,
                "찜 수": category_wishlist,
                "구매수": category_orders,
                "구매 전환율(%)": safe_rate(category_orders, category_views),
            })
        category_stats_df = pd.DataFrame(category_rows).sort_values(["구매 전환율(%)", "조회수"], ascending=False) if category_rows else pd.DataFrame()

        signal_rows = []
        if not no_purchase_interest.empty:
            row = no_purchase_interest.sort_values(["찜 수", "장바구니 수", "조회수"], ascending=False).iloc[0]
            signal_rows.append({
                "신호": "관심은 높은데 구매가 없는 제품",
                "대상": row["제품명"],
                "해석": f"찜 {int(row['찜 수'])}회, 장바구니 {int(row['장바구니 수'])}회지만 구매가 아직 없습니다.",
                "제안": "상세 설명, 배송/가격 안내, 첫 화면 이미지 순서를 먼저 손보세요.",
            })
        if not best_hour_row.empty and best_hour_row.iloc[0]["구매 전환율(%)"] > 0:
            row = best_hour_row.iloc[0]
            signal_rows.append({
                "신호": "구매 전환율이 높은 시간대",
                "대상": row["시간대"],
                "해석": f"해당 시간대 전환율 {row['구매 전환율(%)']:.1f}%입니다.",
                "제안": "이 시간대에 쿠폰, 리마인드, 카카오 알림 테스트를 우선 배치해 보세요.",
            })
        if not category_stats_df.empty:
            row = category_stats_df.iloc[0]
            signal_rows.append({
                "신호": "가장 반응 좋은 카테고리",
                "대상": row["카테고리"],
                "해석": f"조회 {int(row['조회수'])}회 대비 구매 전환율 {row['구매 전환율(%)']:.1f}%입니다.",
                "제안": "유사 제품 확장이나 같은 공간 내 추가 큐레이션 후보로 보세요.",
            })
        recommendation_df = pd.DataFrame(signal_rows)
        if recommendation_df.empty:
            st.markdown("<div class='insight-note'>아직 액션 신호를 만들 만큼 데이터가 충분하지 않습니다.</div>", unsafe_allow_html=True)
        else:
            st.dataframe(recommendation_df, use_container_width=True, hide_index=True)
    else:
        recommendation_df = pd.DataFrame()
        st.markdown("<div class='insight-note'>제품별 조회 데이터가 쌓이면 입점업체 액션 신호를 자동으로 정리합니다.</div>", unsafe_allow_html=True)

    st.markdown("#### 카테고리별 기회")
    if category_stats_df.empty:
        st.info("카테고리별로 비교할 데이터가 아직 없습니다.")
    else:
        st.dataframe(category_stats_df, use_container_width=True, hide_index=True)

    venue_summary_df = pd.DataFrame({
        "숙소 위치": sorted(pd.concat([page_views["venue_location_label"], filtered_orders["venue_location_label"], filtered_wishlist["venue_location_label"]], ignore_index=True).dropna().unique().tolist())
    })
    if not venue_summary_df.empty:
        venue_summary_df["조회수"] = venue_summary_df["숙소 위치"].apply(lambda value: len(page_views[page_views["venue_location_label"] == value]))
        venue_summary_df["찜 수"] = venue_summary_df["숙소 위치"].apply(lambda value: len(filtered_wishlist[filtered_wishlist["venue_location_label"] == value]))
        venue_summary_df["구매수"] = venue_summary_df["숙소 위치"].apply(lambda value: len(filtered_orders[filtered_orders["venue_location_label"] == value]))
        venue_summary_df["구매 전환율(%)"] = venue_summary_df.apply(lambda row: safe_rate(row["구매수"], row["조회수"]), axis=1)
    else:
        venue_summary_df = pd.DataFrame(columns=["숙소 위치", "조회수", "찜 수", "구매수", "구매 전환율(%)"])

    summary_df = pd.DataFrame([
        {"항목": "제품 조회", "값": total_views},
        {"항목": "찜 수", "값": len(filtered_wishlist)},
        {"항목": "장바구니 수", "값": len(cart_events)},
        {"항목": "구매 수", "값": purchase_count},
        {"항목": "찜 전환율(%)", "값": safe_rate(len(filtered_wishlist), total_views)},
        {"항목": "장바구니율(%)", "값": safe_rate(len(cart_events), total_views)},
        {"항목": "구매 전환율(%)", "값": safe_rate(purchase_count, total_views)},
        {"항목": "재방문 후 구매율(%)", "값": safe_rate(return_purchase_count, len(returning_views))},
    ])
    export_events = filtered.copy()
    export_orders = filtered_orders.copy()
    export_wishlist = filtered_wishlist.copy()
    for export_df in (export_events, export_orders, export_wishlist):
        for column in export_df.columns:
            if pd.api.types.is_datetime64_any_dtype(export_df[column]):
                export_df[column] = export_df[column].dt.strftime("%Y-%m-%d %H:%M:%S")
    sheets = {
        "Summary": summary_df,
        "Product Stats": product_stats_df,
        "Hourly Conversion": hourly_conversion_df,
        "Weekday Purchase": weekday_purchase_df,
        "Age Wishlist Purchase": age_rate_df,
        "Gender Wishlist Purchase": gender_rate_df,
        "Venue Stats": venue_summary_df,
        "Category Stats": category_stats_df,
        "Action Signals": recommendation_df,
        "Raw Events": export_events,
        "Raw Orders": export_orders,
        "Raw Wishlist": export_wishlist,
    }
    file_brand = selected_brand if selected_brand != "전체 입점업체" else "all-brands"
    file_date = pd.Timestamp.now().strftime("%Y%m%d")
    st.download_button(
        "📥 입점업체별 인사이트 엑셀 다운로드",
        data=dataframe_to_excel_bytes(sheets),
        file_name=f"affilistay_insights_{file_brand}_{file_date}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


def render_host_income_billboard(snapshot):
    st.markdown(
        f"""
        <div class="host-hero">
            <div style="font-size:0.82rem;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;opacity:0.88;">Host Momentum Board</div>
            <div style="font-size:1.95rem;font-weight:800;line-height:1.15;margin-top:0.45rem;">이번 주와 이번 달 수입 흐름을 한눈에 보세요.</div>
            <div style="opacity:0.9;margin-top:0.55rem;font-size:0.96rem;">숙소 운영 성과를 바로 확인하고, 인기 제품과 쇼룸 업데이트에 더 빠르게 반응할 수 있어요.</div>
            <div class="host-hero-grid">
                <div class="host-chip">
                    <div class="host-chip-label">주간 예상 수입</div>
                    <div class="host-chip-value">{snapshot['week_income']:,}원</div>
                    <div style="font-size:0.84rem;opacity:0.82;margin-top:0.3rem;">주간 판매 {snapshot['week_sales']:,}원</div>
                </div>
                <div class="host-chip">
                    <div class="host-chip-label">월간 예상 수입</div>
                    <div class="host-chip-value">{snapshot['month_income']:,}원</div>
                    <div style="font-size:0.84rem;opacity:0.82;margin-top:0.3rem;">월간 판매 {snapshot['month_sales']:,}원</div>
                </div>
                <div class="host-chip">
                    <div class="host-chip-label">운영 중인 상품 / 누적 주문</div>
                    <div class="host-chip-value">{snapshot['live_products']} / {snapshot['order_count']}</div>
                    <div style="font-size:0.84rem;opacity:0.82;margin-top:0.3rem;">상품을 손보면 쇼룸 전환도 더 좋아집니다.</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_b64_gallery(images, columns_count=5):
    images = [img for img in images if img]
    if not images:
        st.caption("아직 등록된 이미지가 없습니다.")
        return
    for start in range(0, len(images), columns_count):
        cols = st.columns(columns_count)
        for col, image in zip(cols, images[start:start + columns_count]):
            with col:
                show_img(image, width=120)


def render_host_upload_guide(mode):
    if mode == "create":
        st.markdown(
            """
            <div class="guide-card">
                <div class="guide-kicker">Upload flow</div>
                <div class="guide-title">오늘의집처럼 단계별로 올리면 덜 헷갈려요.</div>
                <div class="guide-copy">이미지, 기본 정보, 가격과 공간, 상세 설명 순서로 채우면 쇼룸 완성도가 가장 빠르게 올라갑니다.</div>
                <div class="guide-list">
                    <div class="guide-step">
                        <strong>1. 대표 이미지부터 고르기</strong>
                        <span>첫 이미지는 고객 화면의 대표 카드로 바로 노출됩니다. 밝고 용도가 잘 보이는 컷이 좋아요.</span>
                    </div>
                    <div class="guide-step">
                        <strong>2. 공간과 카테고리 맞추기</strong>
                        <span>거실·침실 같은 배치 공간과 품목 카테고리를 함께 맞춰 두면 카탈로그에서 바로 찾기 쉬워집니다.</span>
                    </div>
                    <div class="guide-step">
                        <strong>3. 상세 설명은 짧고 분명하게</strong>
                        <span>소재, 사용감, 추천 포인트를 고객 언어로 정리해 두면 전환이 좋아집니다.</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="guide-card">
                <div class="guide-kicker">Editing flow</div>
                <div class="guide-title">변경 즉시 쇼룸이 새 정보를 감지합니다.</div>
                <div class="guide-copy">제품명, 대표 이미지, 한줄 설명, 상세 설명을 손보면 고객 페이지가 자동으로 새 정보를 불러옵니다.</div>
                <div class="guide-list">
                    <div class="guide-step">
                        <strong>대표 이미지 교체</strong>
                        <span>새 갤러리를 올리면 기존 이미지가 한 번에 교체됩니다. 첫 이미지가 대표로 사용됩니다.</span>
                    </div>
                    <div class="guide-step">
                        <strong>가격과 옵션 정리</strong>
                        <span>정가와 판매가를 함께 맞춰 두고, 옵션은 줄바꿈으로 정리하면 고객이 선택하기 쉬워져요.</span>
                    </div>
                    <div class="guide-step">
                        <strong>쇼룸 반영 확인</strong>
                        <span>저장 후 퍼블릭 페이지에서 새로고침 버튼 없이도 몇 초 안에 변경사항이 반영됩니다.</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_product_summary_metrics(df_products, gallery_map):
    total_products = int(len(df_products))
    detailed_ready = 0
    gallery_ready = 0
    room_mix = set()
    for _, product in df_products.iterrows():
        if (product.get("detailed_description") or "").strip():
            detailed_ready += 1
        if len(gallery_map.get(int(product["id"]), [])) >= 2:
            gallery_ready += 1
        if product.get("room_category"):
            room_mix.add(product.get("room_category"))

    c1, c2, c3 = st.columns(3)
    c1.metric("등록 상품", f"{total_products}개")
    c2.metric("상세 설명 완성", f"{detailed_ready}개")
    c3.metric("다중 이미지 적용", f"{gallery_ready}개")
    st.caption(f"현재 {len(room_mix)}개 공간 카테고리에 제품이 배치되어 있어요.")


def normalize_phone(raw_phone):
    digits = re.sub(r"\D", "", raw_phone or "")
    if not PHONE_REGEX.fullmatch(digits):
        return None
    return digits


def format_phone_display(raw_phone):
    digits = normalize_phone(raw_phone)
    if not digits:
        return raw_phone
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"


def to_e164_kr(raw_phone):
    digits = normalize_phone(raw_phone)
    if not digits:
        return None
    return f"+82{digits[1:]}"


def is_valid_email(email):
    return bool(EMAIL_REGEX.fullmatch((email or "").strip()))


def signup_address_label(role):
    if role == "HOST":
        return "숙소 주소"
    if role == "BRAND":
        return "판매시설 주소"
    return "주소"


def send_phone_verification(phone_e164):
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_VERIFY_SERVICE_SID):
        return False, "휴대폰 인증을 사용하려면 Twilio Verify 환경변수를 먼저 설정해 주세요."

    try:
        response = httpx.post(
            f"https://verify.twilio.com/v2/Services/{TWILIO_VERIFY_SERVICE_SID}/Verifications",
            data={"To": phone_e164, "Channel": "sms"},
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=12.0,
        )
        data = response.json()
        if response.is_success:
            return True, "인증번호를 전송했습니다. 문자로 받은 코드를 입력해 주세요."
        return False, data.get("message", "인증번호 전송에 실패했습니다.")
    except Exception as exc:
        return False, f"인증번호 전송 중 오류가 발생했습니다: {exc}"


def verify_phone_code(phone_e164, code):
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_VERIFY_SERVICE_SID):
        return False, "휴대폰 인증 환경변수가 설정되지 않았습니다."

    try:
        response = httpx.post(
            f"https://verify.twilio.com/v2/Services/{TWILIO_VERIFY_SERVICE_SID}/VerificationCheck",
            data={"To": phone_e164, "Code": (code or "").strip()},
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=12.0,
        )
        data = response.json()
        if response.is_success and data.get("status") == "approved":
            return True, "휴대폰 인증이 완료되었습니다."
        return False, data.get("message", "인증번호가 올바르지 않습니다.")
    except Exception as exc:
        return False, f"인증 확인 중 오류가 발생했습니다: {exc}"


def search_road_addresses(keyword):
    if not JUSO_API_KEY:
        return [], "도로명 주소 검색을 사용하려면 JUSO_API_KEY 환경변수를 설정해 주세요."

    try:
        response = httpx.get(
            "https://business.juso.go.kr/addrlink/addrLinkApi.do",
            params={
                "confmKey": JUSO_API_KEY,
                "currentPage": 1,
                "countPerPage": 7,
                "keyword": keyword,
                "resultType": "json",
            },
            timeout=12.0,
        )
        data = response.json()
        common = data.get("results", {}).get("common", {})
        if common.get("errorCode") not in (None, "0"):
            return [], common.get("errorMessage", "주소 검색 결과를 불러오지 못했습니다.")
        results = data.get("results", {}).get("juso", [])
        return results, ""
    except Exception as exc:
        return [], f"주소 검색 중 오류가 발생했습니다: {exc}"


def format_address_option(address_row):
    road = address_row.get("roadAddrPart1") or address_row.get("roadAddr") or ""
    detail_hint = address_row.get("bdNm") or address_row.get("detBdNmList") or ""
    zip_code = address_row.get("zipNo") or ""
    suffix = f" · {detail_hint}" if detail_hint else ""
    return f"[{zip_code}] {road}{suffix}"


def sync_signup_address_selection(results, selected_index):
    if results and 0 <= selected_index < len(results):
        selected = results[selected_index]
        st.session_state["signup_address_road"] = selected.get("roadAddrPart1") or selected.get("roadAddr") or ""
        st.session_state["signup_postal_code"] = selected.get("zipNo") or ""


def reset_signup_phone_verification():
    st.session_state["signup_phone_verified"] = False
    st.session_state["signup_verified_phone"] = ""
    st.session_state["signup_verification_sent"] = False
    st.session_state["signup_verification_target"] = ""
    st.session_state["signup_verification_code"] = ""


def _login_bridge_secret():
    return os.getenv("AFFILISTAY_LOGIN_SECRET") or os.getenv("SECRET_KEY") or "affilistay-local-login-bridge"


def _b64url_decode(value):
    return base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode("ascii"))


def _query_param(name):
    try:
        value = st.query_params.get(name)
    except Exception:
        try:
            value = st.experimental_get_query_params().get(name)
        except Exception:
            value = None
    if isinstance(value, list):
        return value[0] if value else ""
    return value or ""


def _clear_login_token_param():
    try:
        if "login_token" in st.query_params:
            del st.query_params["login_token"]
    except Exception:
        try:
            st.experimental_set_query_params()
        except Exception:
            pass


def verify_partner_login_token(token):
    if not token or "." not in token:
        return None
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(_login_bridge_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
        received = _b64url_decode(signature)
        if not hmac.compare_digest(expected, received):
            return None
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def consume_partner_login_token():
    payload = verify_partner_login_token(_query_param("login_token"))
    if not payload:
        return False

    conn = database.get_db_connection()
    try:
        cursor = conn.cursor()
        q = ('SELECT id,username,name,is_master,role FROM hosts WHERE id=%s AND username=%s'
             if database.DATABASE_URL else
             'SELECT id,username,name,is_master,role FROM hosts WHERE id=? AND username=?')
        cursor.execute(q, (int(payload.get("host_id")), payload.get("username")))
        user = cursor.fetchone()
    except Exception:
        user = None
    finally:
        conn.close()

    if not user:
        _clear_login_token_param()
        return False

    st.session_state.update({
        "authenticated": True,
        "host_id": user[0],
        "username": user[1],
        "name": user[2],
        "is_master": bool(user[3]),
        "role": user[4],
        "auth_mode": "login",
    })
    _clear_login_token_param()
    return True

# ─────────────────────────────────────────
# 인증 시스템
# ─────────────────────────────────────────
def check_auth():
    for key, default in [('authenticated', False), ('auth_mode', 'login')]:
        if key not in st.session_state:
            st.session_state[key] = default

    if consume_partner_login_token():
        st.rerun()

    if st.session_state['authenticated']:
        return True

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image("static/affilistay-logo.png", width=220)
        st.markdown(
            '<div class="affili-login-note">메인 쇼룸에서 로그인한 파트너 계정은 같은 인증으로 바로 이어집니다.</div>',
            unsafe_allow_html=True,
        )

        if st.session_state['auth_mode'] == 'login':
            st.markdown("#### 로그인")
            with st.form("login_form", clear_on_submit=False):
                u = st.text_input("아이디")
                p = st.text_input("비밀번호", type="password")
                if st.form_submit_button("로그인", use_container_width=True, type="primary"):
                    conn = database.get_db_connection()
                    cursor = conn.cursor()
                    q = ('SELECT id,username,name,is_master,role FROM hosts WHERE username=%s AND password=%s'
                         if database.DATABASE_URL else
                         'SELECT id,username,name,is_master,role FROM hosts WHERE username=? AND password=?')
                    cursor.execute(q, (u, p))
                    user = cursor.fetchone()
                    conn.close()
                    if user:
                        st.session_state.update({
                            "authenticated": True, "host_id": user[0],
                            "username": user[1], "name": user[2],
                            "is_master": bool(user[3]), "role": user[4]
                        })
                        st.rerun()
                    else:
                        st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
            
            if st.button("계정이 없으신가요? 회원가입", use_container_width=True):
                st.session_state['auth_mode'] = 'signup'
                st.rerun()

        else:
            st.markdown("#### 회원가입")
            signup_defaults = {
                "signup_phone_verified": False,
                "signup_verified_phone": "",
                "signup_verification_sent": False,
                "signup_verification_target": "",
                "signup_verification_code": "",
                "signup_address_results": [],
                "signup_address_choice": 0,
                "signup_address_road": "",
                "signup_address_detail": "",
                "signup_postal_code": "",
            }
            for key, default in signup_defaults.items():
                if key not in st.session_state:
                    st.session_state[key] = default

            # 역할 선택 (3가지)
            role_map = {
                "🏠 호스트 (숙소 운영자)": "HOST",
                "🎁 입점업체 (제품 공급사)": "BRAND",
                "🛋️ 게스트 (쇼룸 방문자)": "GUEST"
            }
            role_label = st.radio("가입 유형을 선택하세요", list(role_map.keys()), horizontal=False)
            actual_role = role_map[role_label]

            st.markdown("---")
            full_name = st.text_input("이름 / 업체명")
            phone = st.text_input("휴대폰 번호", placeholder="010-1234-5678")
            st.caption("회원가입은 휴대폰 인증 완료 후 진행됩니다.")
            if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_VERIFY_SERVICE_SID):
                st.info("운영 환경에서 Twilio Verify 키를 설정하면 문자 인증이 바로 활성화됩니다.")
            normalized_phone = normalize_phone(phone)
            verified_phone = st.session_state.get("signup_verified_phone")
            verification_target = st.session_state.get("signup_verification_target")
            if verified_phone and normalized_phone != verified_phone:
                reset_signup_phone_verification()
            elif st.session_state.get("signup_verification_sent") and verification_target and normalized_phone != verification_target:
                reset_signup_phone_verification()

            send_col, verify_col = st.columns([1, 1])
            with send_col:
                if st.button("인증번호 보내기", use_container_width=True):
                    if not normalized_phone:
                        st.error("휴대폰 번호는 010-1234-5678 형식으로 입력해 주세요.")
                    else:
                        sent, message = send_phone_verification(to_e164_kr(phone))
                        if sent:
                            st.session_state["signup_verification_sent"] = True
                            st.session_state["signup_verification_target"] = normalized_phone
                            st.success(message)
                        else:
                            st.error(message)

            if st.session_state.get("signup_verification_sent") and st.session_state.get("signup_verification_target") == normalized_phone:
                verification_code = st.text_input("인증번호", key="signup_verification_code", placeholder="문자로 받은 6자리 인증번호")
                with verify_col:
                    if st.button("인증 확인", use_container_width=True):
                        if not verification_code.strip():
                            st.error("인증번호를 입력해 주세요.")
                        else:
                            verified, message = verify_phone_code(to_e164_kr(phone), verification_code)
                            if verified:
                                st.session_state["signup_phone_verified"] = True
                                st.session_state["signup_verified_phone"] = normalized_phone
                                st.success(message)
                            else:
                                st.error(message)

            if st.session_state.get("signup_phone_verified") and st.session_state.get("signup_verified_phone") == normalized_phone:
                st.success(f"휴대폰 인증 완료: {format_phone_display(phone)}")

            email = st.text_input("이메일", placeholder="name@example.com")
            if email and not is_valid_email(email):
                st.caption("이메일은 name@example.com 형식으로 입력해 주세요.")

            if actual_role in {"HOST", "BRAND"}:
                st.markdown("##### 주소 입력")
                if not JUSO_API_KEY:
                    st.info("JUSO_API_KEY를 설정하면 도로명 주소 검색 결과를 바로 선택할 수 있습니다. 지금도 직접 입력은 가능합니다.")
                address_keyword = st.text_input("도로명 주소 검색", placeholder="예: 마포구 양화로 45")
                if st.button("주소 검색", use_container_width=True):
                    if not address_keyword.strip():
                        st.error("검색할 도로명 주소를 입력해 주세요.")
                    else:
                        results, message = search_road_addresses(address_keyword.strip())
                        st.session_state["signup_address_results"] = results
                        st.session_state["signup_address_choice"] = 0
                        if results:
                            sync_signup_address_selection(results, 0)
                            st.success("검색 결과를 불러왔습니다. 아래에서 정확한 주소를 선택해 주세요.")
                        else:
                            st.warning(message or "검색 결과가 없습니다. 도로명, 건물명으로 다시 검색해 주세요.")

                address_results = st.session_state.get("signup_address_results", [])
                if address_results:
                    selected_index = st.selectbox(
                        "검색 결과",
                        options=list(range(len(address_results))),
                        format_func=lambda idx: format_address_option(address_results[idx]),
                        key="signup_address_choice",
                    )
                    sync_signup_address_selection(address_results, selected_index)

                st.text_input(
                    signup_address_label(actual_role),
                    key="signup_address_road",
                    placeholder="검색 결과를 선택하거나 도로명 주소를 직접 입력해 주세요.",
                )
                st.text_input("상세 주소", key="signup_address_detail", placeholder="동/호수, 층수 등을 입력해 주세요.")
                st.text_input("우편번호", key="signup_postal_code", placeholder="주소 검색 시 자동 입력됩니다.")

            signup_path = st.selectbox("가입 경로", ["SNS", "지인소개", "검색", "광고", "기타"])
            new_username = st.text_input("사용할 아이디")
            new_password = st.text_input("비밀번호", type="password")

            if st.button("가입 신청", use_container_width=True, type="primary"):
                if not full_name.strip():
                    st.error("이름 또는 업체명을 입력해 주세요.")
                elif not normalized_phone:
                    st.error("휴대폰 번호 형식을 다시 확인해 주세요.")
                elif not (st.session_state.get("signup_phone_verified") and st.session_state.get("signup_verified_phone") == normalized_phone):
                    st.error("회원가입 전에 휴대폰 인증을 완료해 주세요.")
                elif not is_valid_email(email):
                    st.error("이메일 형식을 올바르게 입력해 주세요.")
                elif actual_role in {"HOST", "BRAND"} and not st.session_state.get("signup_address_road", "").strip():
                    st.error(f"{signup_address_label(actual_role)}를 입력해 주세요.")
                elif not new_username.strip() or not new_password.strip():
                    st.error("아이디와 비밀번호를 모두 입력해 주세요.")
                else:
                    conn = database.get_db_connection()
                    cursor = conn.cursor()
                    verified_at = pd.Timestamp.now(tz=None).strftime("%Y-%m-%d %H:%M:%S")
                    formatted_phone = format_phone_display(phone)
                    address_road = st.session_state.get("signup_address_road", "").strip()
                    address_detail = st.session_state.get("signup_address_detail", "").strip()
                    postal_code = st.session_state.get("signup_postal_code", "").strip()
                    try:
                        q = (
                            'INSERT INTO hosts (username,password,name,phone,email,address_road,address_detail,postal_code,phone_verified,phone_verified_at,signup_path,role,is_master) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id'
                            if database.DATABASE_URL else
                            'INSERT INTO hosts (username,password,name,phone,email,address_road,address_detail,postal_code,phone_verified,phone_verified_at,signup_path,role,is_master) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)'
                        )
                        cursor.execute(
                            q,
                            (
                                new_username.strip(),
                                new_password,
                                full_name.strip(),
                                formatted_phone,
                                email.strip().lower(),
                                address_road or None,
                                address_detail or None,
                                postal_code or None,
                                True,
                                verified_at,
                                signup_path,
                                actual_role,
                                False,
                            ),
                        )
                        new_host_id = cursor.fetchone()[0] if database.DATABASE_URL else cursor.lastrowid

                        if actual_role == "HOST" and address_road:
                            venue_location = " ".join(piece for piece in [address_road, address_detail] if piece).strip()
                            venue_query = (
                                "INSERT INTO host_venues (host_id, location, description) VALUES (%s,%s,%s) ON CONFLICT (host_id) DO NOTHING"
                                if database.DATABASE_URL else
                                "INSERT OR IGNORE INTO host_venues (host_id, location, description) VALUES (?,?,?)"
                            )
                            cursor.execute(venue_query, (new_host_id, venue_location, None))

                        conn.commit()
                        reset_signup_phone_verification()
                        st.session_state["signup_address_results"] = []
                        st.session_state["signup_address_road"] = ""
                        st.session_state["signup_address_detail"] = ""
                        st.session_state["signup_postal_code"] = ""
                        st.success(f"✅ 가입 완료! [{role_label}] 계정으로 로그인해 주세요.")
                        st.session_state['auth_mode'] = 'login'
                        st.rerun()
                    except Exception as e:
                        st.error(f"가입 오류 (아이디 중복 등): {e}")
                    finally:
                        conn.close()

            if st.button("로그인으로 돌아가기", use_container_width=True):
                st.session_state['auth_mode'] = 'login'
                st.rerun()
    return False

if not check_auth():
    st.stop()

# ─────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────
role      = st.session_state['role']
is_master = st.session_state['is_master']
host_id   = st.session_state['host_id']
uname     = st.session_state['name']

ROLE_LABELS = {"HOST": "숙소 호스트", "BRAND": "입점사(브랜드)", "GUEST": "게스트"}
role_display = "MASTER" if is_master else ROLE_LABELS.get(role, "파트너")

with st.sidebar:
    st.image("static/affilistay-logo.png", width=170)
    st.caption(f"**{uname}** ({role_display})")
    st.markdown("---")
    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state['authenticated'] = False
        st.rerun()

# ─────────────────────────────────────────
# 공통 UI 컴포넌트: 상품 & QR / 주문 현황
# ─────────────────────────────────────────
def render_tab_qr(host_id, is_master):
    current_role = st.session_state.get('role')
    if current_role == 'HOST' and not is_master:
        render_host_income_billboard(load_host_income_snapshot(host_id))
    conn = database.get_db_connection()
    if is_master:
        product_query = """
            SELECT p.*, h.name as owner
            FROM products p
            LEFT JOIN hosts h ON p.owner_id = h.id
            ORDER BY p.id DESC
        """
        df_p = pd.read_sql_query(product_query, conn)
    else:
        product_query = (
            """
            SELECT p.*
            FROM products p
            WHERE p.owner_id=%s
            ORDER BY p.id DESC
            """
            if database.DATABASE_URL else
            """
            SELECT p.*
            FROM products p
            WHERE p.owner_id=?
            ORDER BY p.id DESC
            """
        )
        df_p = pd.read_sql_query(product_query, conn, params=(host_id,))

    gallery_map = {}
    option_map = {}
    for product_id in df_p['id'].tolist() if not df_p.empty else []:
        gallery_images = []
        for image in [df_p[df_p['id'] == product_id].iloc[0].get('image_url')] + database.fetch_product_images(conn, product_id):
            if image and image not in gallery_images:
                gallery_images.append(image)
        gallery_map[product_id] = gallery_images
        option_map[product_id] = build_options_text(database.fetch_product_options(conn, product_id))
    conn.close()
    workspace_mode = st.radio(
        "상품 작업 모드",
        ["신규 상품 등록", "기존 상품 수정"],
        horizontal=True,
        key=f"product_workspace_{host_id}_{'master' if is_master else 'host'}",
        label_visibility="collapsed",
    )

    if workspace_mode == "신규 상품 등록":
        left, right = st.columns([1.45, 0.85], gap="large")
        with left:
            with st.container(border=True):
                st.markdown("#### 🛍️ 새 쇼룸 상품 등록")
                st.caption("이미지부터 상세 소개까지 한 화면에서 정리하고 저장 즉시 쇼룸에 반영하세요.")
                with st.form(f"product_register_form_{host_id}", clear_on_submit=True):
                    st.markdown("##### 1. 대표 이미지와 갤러리")
                    prod_images = st.file_uploader(
                        "제품 이미지 업로드",
                        type=["jpg", "jpeg", "png", "webp"],
                        accept_multiple_files=True,
                        help="첫 이미지가 대표 이미지로 노출됩니다.",
                    )
                    st.caption("대표 이미지는 밝고 제품 전체가 잘 보이는 컷이 가장 좋아요.")

                    st.markdown("##### 2. 기본 정보")
                    info_left, info_right = st.columns(2)
                    with info_left:
                        brand_name = st.text_input("브랜드명 *")
                        product_name = st.text_input("제품명 *")
                        prod_description = st.text_input("리스트 한줄 설명", placeholder="예: 체크인 직후 눈길을 끄는 무드등")
                    with info_right:
                        room_label = st.selectbox("배치 공간 *", list(ROOM_MAP.keys()))
                        prod_cat_label = st.selectbox("품목 카테고리 *", list(PROD_CAT_MAP.keys()))
                        original_price = st.number_input("정가 *", min_value=0, step=1000, format="%d")

                    st.markdown("##### 3. 가격과 쇼룸 배치")
                    price_cols = st.columns([1, 1])
                    with price_cols[0]:
                        price = st.number_input("판매가 *", min_value=0, step=1000, format="%d")
                    with price_cols[1]:
                        st.markdown("**현재 배치 기준**")
                        st.caption("위에서 선택한 공간과 카테고리가 바로 카탈로그 필터에 반영됩니다.")

                    st.markdown("##### 4. 상세 소개와 옵션")
                    detailed_description = st.text_area(
                        "상세 설명",
                        placeholder="소재, 사용감, 추천 포인트를 고객이 읽기 쉽게 적어주세요.",
                        height=160,
                    )
                    options_raw = st.text_area(
                        "옵션",
                        placeholder="예: 색상: 화이트, 블랙\n사이즈: S, M, L",
                        height=100,
                    )
                    submitted = st.form_submit_button("🎯 상품 저장하고 QR 만들기", use_container_width=True, type="primary")

            if submitted:
                if not brand_name or not product_name or price <= 0 or not prod_images:
                    st.error("브랜드명, 제품명, 판매가, 대표 이미지는 꼭 입력해 주세요.")
                else:
                    qr_id = str(uuid.uuid4())[:12]
                    url = f"{CHECKOUT_BASE_URL}/shop/{qr_id}"
                    main_img_b64 = database.file_to_base64(prod_images[0])
                    conn_save = database.get_db_connection()
                    try:
                        cursor = conn_save.cursor()
                        insert_query = (
                            'INSERT INTO products (brand_name,product_name,price,original_price,qr_code_id,owner_id,room_category,product_category,description,detailed_description,image_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id'
                            if database.DATABASE_URL else
                            'INSERT INTO products (brand_name,product_name,price,original_price,qr_code_id,owner_id,room_category,product_category,description,detailed_description,image_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)'
                        )
                        cursor.execute(
                            insert_query,
                            (
                                brand_name,
                                product_name,
                                price,
                                original_price or price,
                                qr_id,
                                host_id,
                                ROOM_MAP[room_label],
                                PROD_CAT_MAP[prod_cat_label],
                                prod_description or None,
                                detailed_description or None,
                                main_img_b64,
                            ),
                        )
                        new_product_id = cursor.fetchone()[0] if database.DATABASE_URL else cursor.lastrowid
                        replace_product_media(cursor, new_product_id, prod_images)
                        replace_product_options(cursor, new_product_id, options_raw)
                        database.bump_public_content_version(conn_save)
                        conn_save.commit()
                        st.success(f"✅ '{product_name}' 등록이 완료됐어요. 쇼룸도 자동 반영을 시작합니다.")
                        qr_buffer = make_qr(url)
                        q1, q2 = st.columns([1, 2])
                        with q1:
                            st.image(qr_buffer, width=180)
                            qr_buffer.seek(0)
                            st.download_button("📥 QR 다운로드", qr_buffer, f"QR_{product_name}.png", "image/png", use_container_width=True)
                        with q2:
                            st.code(url, language=None)
                    except Exception as e:
                        st.error(f"오류: {e}")
                    finally:
                        conn_save.close()

        with right:
            render_host_upload_guide("create")
            with st.container(border=True):
                st.markdown("#### 바로 반영되는 항목")
                st.caption("저장 직후 고객 페이지가 새 정보를 감지하는 핵심 항목입니다.")
                st.markdown("- 대표 이미지\n- 제품명과 한줄 설명\n- 공간 배치와 카테고리\n- 상세 설명과 옵션")
    else:
        st.subheader("🛠️ 등록된 상품 관리")
        if df_p.empty:
            st.info("등록된 제품이 없습니다. 먼저 신규 상품을 올려 주세요.")
            return

        render_product_summary_metrics(df_p, gallery_map)
        search_col, room_col = st.columns([1.9, 1])
        search_query = search_col.text_input(
            "상품 검색",
            placeholder="제품명 또는 브랜드명을 입력해 빠르게 찾으세요.",
            key=f"product_search_{host_id}_{'master' if is_master else 'host'}",
        )
        room_filter = room_col.selectbox(
            "공간 필터",
            ["전체"] + list(ROOM_MAP.keys()),
            key=f"product_room_filter_{host_id}_{'master' if is_master else 'host'}",
        )
        filtered_df = df_p.copy()
        if search_query:
            mask = (
                filtered_df["product_name"].fillna("").str.contains(search_query, case=False) |
                filtered_df["brand_name"].fillna("").str.contains(search_query, case=False)
            )
            filtered_df = filtered_df[mask]
        if room_filter != "전체":
            filtered_df = filtered_df[filtered_df["room_category"] == ROOM_MAP[room_filter]]

        guide_left, guide_right = st.columns([1.4, 0.9], gap="large")
        with guide_right:
            render_host_upload_guide("edit")
        with guide_left:
            if filtered_df.empty:
                st.info("조건에 맞는 상품이 아직 없습니다. 검색어나 공간 필터를 바꿔 보세요.")
            else:
                for index, (_, product) in enumerate(filtered_df.iterrows()):
                    product_id = int(product['id'])
                    room_value = product.get('room_category') or 'living_room'
                    category_value = product.get('product_category') or 'lifestyle'
                    gallery_images = gallery_map.get(product_id, [])
                    option_text = option_map.get(product_id, "")
                    badge_text = f"{ROOM_ICON_MAP.get(room_value, '🏠')} {ROOM_LABEL_MAP.get(room_value, room_value)} · {PROD_CAT_LABEL_MAP.get(category_value, category_value)}"

                    with st.expander(f"{product['product_name']}  ·  {badge_text}", expanded=index == 0):
                        top_left, top_right = st.columns([0.95, 1.55], gap="large")
                        with top_left:
                            show_img(gallery_images[0] if gallery_images else product.get('image_url'), width=240)
                            st.caption("현재 등록된 갤러리")
                            render_b64_gallery(gallery_images[:5], columns_count=min(5, max(len(gallery_images[:5]), 1)))
                            qr_url = f"{CHECKOUT_BASE_URL}/shop/{product['qr_code_id']}"
                            qr_buffer = make_qr(qr_url)
                            st.code(qr_url, language=None)
                            qr_buffer.seek(0)
                            st.download_button(
                                "📥 이 상품 QR 다운로드",
                                qr_buffer,
                                f"QR_{product['product_name']}.png",
                                "image/png",
                                key=f"product_qr_{product_id}",
                                use_container_width=True,
                            )

                        with top_right:
                            st.markdown(f"**상품 ID #{product_id}**")
                            meta1, meta2, meta3 = st.columns(3)
                            meta1.metric("판매가", f"{int(product['price']):,}원")
                            meta2.metric("정가", f"{int((product['original_price'] or product['price'])):,}원")
                            meta3.metric("할인율", f"{int(max((product['original_price'] or product['price']) - product['price'], 0) / max((product['original_price'] or product['price']), 1) * 100)}%")

                            with st.form(f"product_edit_form_{product_id}"):
                                st.markdown("##### 쇼룸에 보이는 기본 정보")
                                e1, e2 = st.columns(2)
                                with e1:
                                    edit_brand = st.text_input("브랜드명", value=product['brand_name'], key=f"brand_{product_id}")
                                    edit_name = st.text_input("제품명", value=product['product_name'], key=f"name_{product_id}")
                                    edit_description = st.text_input("리스트 한줄 설명", value=product.get('description') or "", key=f"desc_{product_id}")
                                with e2:
                                    edit_room = st.selectbox(
                                        "배치 공간",
                                        list(ROOM_MAP.keys()),
                                        index=list(ROOM_MAP.values()).index(room_value) if room_value in ROOM_MAP.values() else 0,
                                        key=f"room_{product_id}",
                                    )
                                    edit_category = st.selectbox(
                                        "품목 카테고리",
                                        list(PROD_CAT_MAP.keys()),
                                        index=list(PROD_CAT_MAP.values()).index(category_value) if category_value in PROD_CAT_MAP.values() else 0,
                                        key=f"category_{product_id}",
                                    )
                                    replacement_images = st.file_uploader(
                                        "새 갤러리 이미지 (업로드 시 기존 이미지 전체 교체)",
                                        type=["jpg", "jpeg", "png", "webp"],
                                        accept_multiple_files=True,
                                        key=f"gallery_{product_id}",
                                    )

                                st.markdown("##### 가격과 상세 소개")
                                price_left, price_right = st.columns(2)
                                with price_left:
                                    edit_original_price = st.number_input(
                                        "정가",
                                        min_value=0,
                                        step=1000,
                                        format="%d",
                                        value=int(product['original_price'] or product['price']),
                                        key=f"origin_{product_id}",
                                    )
                                with price_right:
                                    edit_price = st.number_input(
                                        "판매가",
                                        min_value=0,
                                        step=1000,
                                        format="%d",
                                        value=int(product['price']),
                                        key=f"price_{product_id}",
                                    )

                                edit_detailed_description = st.text_area(
                                    "상세 설명",
                                    value=product.get('detailed_description') or "",
                                    height=160,
                                    key=f"detail_{product_id}",
                                )
                                edit_options_raw = st.text_area(
                                    "옵션",
                                    value=option_text,
                                    height=100,
                                    key=f"options_{product_id}",
                                )
                                save_product = st.form_submit_button("💾 변경 저장하고 쇼룸 반영", use_container_width=True, type="primary")

                            if save_product:
                                if not edit_brand or not edit_name or edit_price <= 0:
                                    st.error("브랜드명, 제품명, 판매가는 비워둘 수 없습니다.")
                                else:
                                    conn_edit = database.get_db_connection()
                                    cursor = conn_edit.cursor()
                                    try:
                                        next_main_image = product.get('image_url')
                                        if replacement_images:
                                            next_main_image = database.file_to_base64(replacement_images[0])

                                        update_query = (
                                            """
                                            UPDATE products
                                            SET brand_name=%s, product_name=%s, price=%s, original_price=%s,
                                                room_category=%s, product_category=%s, description=%s,
                                                detailed_description=%s, image_url=%s
                                            WHERE id=%s
                                            """
                                            if database.DATABASE_URL else
                                            """
                                            UPDATE products
                                            SET brand_name=?, product_name=?, price=?, original_price=?,
                                                room_category=?, product_category=?, description=?,
                                                detailed_description=?, image_url=?
                                            WHERE id=?
                                            """
                                        )
                                        cursor.execute(
                                            update_query,
                                            (
                                                edit_brand,
                                                edit_name,
                                                edit_price,
                                                edit_original_price or edit_price,
                                                ROOM_MAP[edit_room],
                                                PROD_CAT_MAP[edit_category],
                                                edit_description or None,
                                                edit_detailed_description or None,
                                                next_main_image,
                                                product_id,
                                            ),
                                        )
                                        if replacement_images:
                                            replace_product_media(cursor, product_id, replacement_images)
                                        replace_product_options(cursor, product_id, edit_options_raw)
                                        database.bump_public_content_version(conn_edit)
                                        conn_edit.commit()
                                        st.success(f"✅ '{edit_name}' 정보가 저장되었습니다. 고객 페이지도 자동 업데이트를 감지합니다.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"오류: {e}")
                                    finally:
                                        conn_edit.close()

def render_tab_orders(host_id, is_master):
    st.subheader("📦 주문 현황")
    conn = database.get_db_connection()
    if is_master:
        df_o = pd.read_sql_query("""
            SELECT o.id, o.customer_name, o.phone_number, o.shipping_address, o.delivery_note, 
                   p.product_name, p.brand_name, o.total_amount, o.currency, o.exchange_rate,
                   o.paypal_order_id, o.payment_status, o.settlement_status, o.shipping_status, o.fcm_token, o.created_at 
            FROM orders o JOIN products p ON o.product_id = p.id 
            ORDER BY o.id DESC
        """, conn)
    else:
        q = ('''
            SELECT o.id, o.customer_name, o.phone_number, o.shipping_address, o.delivery_note, 
                   p.product_name, o.total_amount, o.currency, o.exchange_rate,
                   o.paypal_order_id, o.payment_status, o.settlement_status, o.shipping_status, o.fcm_token, o.created_at 
            FROM orders o JOIN products p ON o.product_id = p.id 
            WHERE p.owner_id = %s ORDER BY o.id DESC
        ''' if database.DATABASE_URL else '''
            SELECT o.id, o.customer_name, o.phone_number, o.shipping_address, o.delivery_note, 
                   p.product_name, o.total_amount, o.currency, o.exchange_rate,
                   o.paypal_order_id, o.payment_status, o.settlement_status, o.shipping_status, o.fcm_token, o.created_at 
            FROM orders o JOIN products p ON o.product_id = p.id 
            WHERE p.owner_id = ? ORDER BY o.id DESC
        ''')
        df_o = pd.read_sql_query(q, conn, params=(host_id,))
    conn.close()
    if df_o.empty:
        st.info("아직 고객 주문이 없습니다.")
    else:
        # 가독성 개선
        df_o['total_amount'] = df_o.apply(lambda x: f"{x['total_amount']:,}원 ({x['currency']})", axis=1)
        st.dataframe(df_o.drop(columns=['fcm_token']), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("#### 🚚 배송 상태 업데이트 및 알림톡(푸시) 발송")
        
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            selected_order_id = st.selectbox("주문 선택", df_o['id'].tolist(), 
                                             format_func=lambda x: f"주문 #{x} - {df_o[df_o['id']==x]['customer_name'].values[0]}")
        with c2:
            current_status = df_o[df_o['id']==selected_order_id]['shipping_status'].values[0]
            new_status = st.selectbox("상태 변경", ["PREPARING", "SHIPPED", "DELIVERED"], 
                                      index=["PREPARING", "SHIPPED", "DELIVERED"].index(current_status) if current_status in ["PREPARING", "SHIPPED", "DELIVERED"] else 0)
        with c3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("상태 업데이트 및 알림 전송", use_container_width=True, type="primary"):
                conn2 = database.get_db_connection()
                curs = conn2.cursor()
                q_up = ('UPDATE orders SET shipping_status=%s WHERE id=%s'
                        if database.DATABASE_URL else
                        'UPDATE orders SET shipping_status=? WHERE id=?')
                curs.execute(q_up, (new_status, selected_order_id))
                conn2.commit()
                conn2.close()
                
                # 푸시 알림 전송 (SHIPPED 로 변경 시)
                if new_status == "SHIPPED" and current_status != "SHIPPED":
                    fcm_token = df_o[df_o['id']==selected_order_id]['fcm_token'].values[0]
                    if fcm_token:
                        success = fcm_service.send_push_notification(
                            token=fcm_token,
                            title="배송 시작 안내",
                            body=f"고객님의 주문(#{selected_order_id}) 상품이 배송을 시작했습니다. 곧 도착할 예정입니다!",
                            data={"order_id": str(selected_order_id), "type": "shipping_started"}
                        )
                        if success:
                            st.success(f"주문 #{selected_order_id} 배송 상태 업데이트 및 푸시 알림 전송 완료!")
                        else:
                            st.warning(f"주문 #{selected_order_id} 배송 상태는 업데이트되었으나 푸시 알림 전송에 실패했습니다.")
                    else:
                        st.success(f"주문 #{selected_order_id} 배송 상태 업데이트 완료 (푸시 알림 토큰이 없어 발송되지 않음).")
                else:
                    st.success(f"주문 #{selected_order_id} 배송 상태가 {new_status}로 업데이트되었습니다.")
                
                time.sleep(1.5)
                st.rerun()


# ─────────────────────────────────────────
# GUEST 페이지
# ─────────────────────────────────────────
if role == 'GUEST' and not is_master:
    st.title(f"🛋️ 안녕하세요, {uname}님!")
    st.info("쇼룸 게스트님을 위한 큐레이션 페이지를 준비 중입니다.")
    st.stop()

# ─────────────────────────────────────────
# BRAND (입점업체) 페이지
# ─────────────────────────────────────────
if role == 'BRAND' and not is_master:
    # 작업 4: 입점업체도 QR 쇼룸 인사이트를 바로 확인할 수 있도록 탭 추가
    tab_qr, tab_ord, tab1, tab2, tab3, tab4, tab_insight = st.tabs([
        "🛍️ 상품 & QR (다이렉트 판매)",
        "📦 고객 주문 현황",
        "📦 브랜드 제품 풀(Pool) 관리",
        "🏠 호스트 숙소 탐색",
        "📤 호스트 입점 제안",
        "📊 전체 입점 현황",
        "📊 인사이트"
    ])
    
    with tab_qr: render_tab_qr(host_id, is_master)
    with tab_ord: render_tab_orders(host_id, is_master)

    # ── TAB1: 내 입점 제품 관리 ──────────────────
    with tab1:
        st.subheader("📦 입점 제품 등록 · 관리")
        st.caption("숙소에 비치할 입점 가능 제품을 등록하세요.")

        with st.form("brand_item_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                item_name = st.text_input("제품명 *")
                description = st.text_area("제품 소개", height=80)
            with c2:
                stock_qty = st.number_input("입점 가능 재고 수량 *", min_value=0, step=1)
                item_img = st.file_uploader("제품 이미지", type=["jpg","jpeg","png","webp"])
            submitted = st.form_submit_button("✅ 제품 등록", use_container_width=True, type="primary")

        if submitted:
            if not item_name or stock_qty < 0 or not item_img:
                st.error("제품명, 재고 수량, 그리고 제품 이미지를 모두 입력해 주세요.")
            else:
                img_b64 = database.file_to_base64(item_img) if item_img else None
                conn = database.get_db_connection()
                cursor = conn.cursor()
                try:
                    q = ('INSERT INTO brand_items (brand_id,item_name,description,stock_qty,image) VALUES (%s,%s,%s,%s,%s)'
                         if database.DATABASE_URL else
                         'INSERT INTO brand_items (brand_id,item_name,description,stock_qty,image) VALUES (?,?,?,?,?)')
                    cursor.execute(q, (host_id, item_name, description, stock_qty, img_b64))
                    conn.commit()
                    st.success(f"'{item_name}' 등록 완료!")
                    st.rerun()
                except Exception as e:
                    st.error(f"오류: {e}")
                finally:
                    conn.close()

        st.markdown("---")
        st.markdown("#### 🗂️ 등록된 제품 목록")
        conn = database.get_db_connection()
        q = ('SELECT id,item_name,description,stock_qty,image FROM brand_items WHERE brand_id=%s ORDER BY id DESC'
             if database.DATABASE_URL else
             'SELECT id,item_name,description,stock_qty,image FROM brand_items WHERE brand_id=? ORDER BY id DESC')
        df_items = pd.read_sql_query(q, conn, params=(host_id,))
        conn.close()

        if df_items.empty:
            st.info("아직 등록된 입점 제품이 없습니다.")
        else:
            for _, row in df_items.iterrows():
                with st.container():
                    c1, c2 = st.columns([1, 3])
                    with c1:
                        show_img(row['image'], width=120)
                    with c2:
                        st.markdown(f"**[#{row['id']}] {row['item_name']}**")
                        st.caption(row['description'] or "설명 없음")
                        st.markdown(f"📦 입점 가능 재고: **{row['stock_qty']}개**")
                    st.divider()

    # ── TAB2: 호스트 숙소 탐색 ──────────────────
    with tab2:
        st.subheader("🏠 호스트 숙소 탐색")
        st.caption("입점 제품을 비치할 숙소를 확인하세요.")
        conn = database.get_db_connection()
        df_venues = pd.read_sql_query("""
            SELECT v.id, h.name as host_name, h.id as host_id,
                   v.location, v.description, v.image1, v.image2
            FROM host_venues v JOIN hosts h ON v.host_id = h.id
            ORDER BY v.id DESC
        """ if database.DATABASE_URL else """
            SELECT v.id, h.name as host_name, h.id as host_id,
                   v.location, v.description, v.image1, v.image2
            FROM host_venues v JOIN hosts h ON v.host_id = h.id
            ORDER BY v.id DESC
        """, conn)
        conn.close()

        if df_venues.empty:
            st.info("아직 등록된 호스트 숙소가 없습니다.")
        else:
            for _, v in df_venues.iterrows():
                with st.expander(f"🏠 {v['host_name']} 님의 숙소 — 📍 {v['location'] or '위치 미입력'}", expanded=False):
                    c1, c2 = st.columns(2)
                    with c1:
                        show_img(v['image1'])
                    with c2:
                        show_img(v['image2'])
                    if v['description']:
                        st.caption(v['description'])

    # ── TAB3: 입점 보내기 ──────────────────────
    with tab3:
        st.subheader("📤 호스트에게 입점 보내기")
        st.caption("비치할 제품과 수량을 선택해 원하는 숙소 호스트에게 입점을 제안하세요.")

        conn = database.get_db_connection()
        # 내 제품 목록
        q_items = ('SELECT id,item_name,stock_qty FROM brand_items WHERE brand_id=%s AND stock_qty>0'
                   if database.DATABASE_URL else
                   'SELECT id,item_name,stock_qty FROM brand_items WHERE brand_id=? AND stock_qty>0')
        my_items = pd.read_sql_query(q_items, conn, params=(host_id,))
        # 숙소 있는 호스트 목록
        host_venues = pd.read_sql_query("""
            SELECT h.id, h.name, v.location FROM hosts h
            JOIN host_venues v ON h.id = v.host_id WHERE h.role='HOST'
        """ if database.DATABASE_URL else """
            SELECT h.id, h.name, v.location FROM hosts h
            JOIN host_venues v ON h.id = v.host_id WHERE h.role='HOST'
        """, conn)
        conn.close()

        if my_items.empty:
            st.warning("입점 가능한 제품이 없습니다. 먼저 제품을 등록해 주세요.")
        elif host_venues.empty:
            st.warning("아직 숙소 정보를 등록한 호스트가 없습니다.")
        else:
            with st.form("sponsorship_form"):
                item_options = {f"[#{r['id']}] {r['item_name']} (재고 {r['stock_qty']}개)": r['id'] for _, r in my_items.iterrows()}
                host_options = {f"{r['name']} — 📍{r['location'] or '위치 미입력'}": r['id'] for _, r in host_venues.iterrows()}

                sel_item_label = st.selectbox("입점할 제품 선택", list(item_options.keys()))
                sel_host_label = st.selectbox("입점받을 호스트 선택", list(host_options.keys()))
                qty = st.number_input("입점 수량", min_value=1, step=1)
                message = st.text_area("호스트에게 전할 메시지 (선택)", height=80)
                send = st.form_submit_button("📤 입점 제안 보내기", use_container_width=True, type="primary")

            if send:
                item_id  = item_options[sel_item_label]
                h_id     = host_options[sel_host_label]
                conn = database.get_db_connection()
                cursor = conn.cursor()
                try:
                    # 재고 차감
                    q_dec = ('UPDATE brand_items SET stock_qty=stock_qty-%s WHERE id=%s'
                             if database.DATABASE_URL else
                             'UPDATE brand_items SET stock_qty=stock_qty-? WHERE id=?')
                    cursor.execute(q_dec, (qty, item_id))
                    # 입점 내역 추가
                    q_ins = ('INSERT INTO sponsorships (brand_id,host_id,brand_item_id,qty,message,status) VALUES (%s,%s,%s,%s,%s,%s)'
                             if database.DATABASE_URL else
                             'INSERT INTO sponsorships (brand_id,host_id,brand_item_id,qty,message,status) VALUES (?,?,?,?,?,?)')
                    cursor.execute(q_ins, (host_id, h_id, item_id, qty, message, 'PENDING'))
                    conn.commit()
                    st.success("✅ 입점 제안이 전송되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"오류: {e}")
                finally:
                    conn.close()

    # ── TAB4: 입점 현황 ────────────────────────
    with tab4:
        st.subheader("📊 입점 현황")
        conn = database.get_db_connection()
        q = ("""
            SELECT s.id, h.name as 호스트, bi.item_name as 제품, s.qty as 수량,
                   s.status as 상태, s.message as 메시지, s.created_at as 일시
            FROM sponsorships s
            JOIN hosts h ON s.host_id = h.id
            JOIN brand_items bi ON s.brand_item_id = bi.id
            WHERE s.brand_id = %s ORDER BY s.id DESC
        """ if database.DATABASE_URL else """
            SELECT s.id, h.name as 호스트, bi.item_name as 제품, s.qty as 수량,
                   s.status as 상태, s.message as 메시지, s.created_at as 일시
            FROM sponsorships s
            JOIN hosts h ON s.host_id = h.id
            JOIN brand_items bi ON s.brand_item_id = bi.id
            WHERE s.brand_id = ? ORDER BY s.id DESC
        """)
        df_sp = pd.read_sql_query(q, conn, params=(host_id,))
        conn.close()
        if df_sp.empty:
            st.info("아직 입점 내역이 없습니다.")
        else:
            st.dataframe(df_sp.drop(columns=['id']), use_container_width=True, hide_index=True)

    with tab_insight:
        render_insights_dashboard(host_id, is_master)

    st.stop()

# ─────────────────────────────────────────
# HOST 페이지 + MASTER 공통
# ─────────────────────────────────────────
tabs_list = ["🛍️ 상품 & QR", "📦 주문 현황", "⭐ 리뷰", "💬 문의사항", "🏠 숙소 프로필", "🎁 입점 신청"]
if is_master:
    tabs_list = ["🛍️ 상품 & QR", "📦 주문 현황", "⭐ 리뷰", "💬 문의사항", "🏠 숙소 탐색", "🎁 입점 현황", "👥 사용자 관리", "💰 정산"]

# 작업 4: 기존 탭 인덱스를 유지하기 위해 인사이트 탭은 항상 맨 뒤에 추가
tabs_list.append("📊 인사이트")
tab_list = st.tabs(tabs_list)

# ═══════════════════════════════════════
# TAB 0 — 상품 관리 & QR
# ═══════════════════════════════════════
with tab_list[0]:
    render_tab_qr(host_id, is_master)

# ═══════════════════════════════════════
# TAB 1 — 주문 현황
# ═══════════════════════════════════════
with tab_list[1]:
    render_tab_orders(host_id, is_master)

# ═══════════════════════════════════════
# TAB 2 — 리뷰 관리
# ═══════════════════════════════════════
with tab_list[2]:
    st.subheader("⭐ 제품 리뷰 관리")
    conn = database.get_db_connection()
    q = ("""
        SELECT r.id, p.product_name, r.customer_name, r.rating, r.comment, r.created_at
        FROM reviews r JOIN products p ON r.product_id = p.id
        """ + ("" if is_master else " WHERE p.owner_id = %s") + " ORDER BY r.created_at DESC")
    if is_master: df_r = pd.read_sql_query(q, conn)
    else: df_r = pd.read_sql_query(q, conn, params=(host_id,))
    conn.close()
    if df_r.empty: st.info("아직 리뷰가 없습니다.")
    else: st.dataframe(df_r, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════
# TAB 3 — 문의사항 관리
# ═══════════════════════════════════════
with tab_list[3]:
    st.subheader("💬 제품 문의사항 (취소/환불/기타)")
    conn = database.get_db_connection()
    q = ("""
        SELECT q.id, p.product_name, q.customer_name, q.type, q.content, q.created_at
        FROM product_inquiries q JOIN products p ON q.product_id = p.id
        """ + ("" if is_master else " WHERE p.owner_id = %s") + " ORDER BY q.created_at DESC")
    if is_master: df_inq = pd.read_sql_query(q, conn)
    else: df_inq = pd.read_sql_query(q, conn, params=(host_id,))
    conn.close()
    if df_inq.empty: st.info("아직 문의사항이 없습니다.")
    else: st.dataframe(df_inq, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════
# TAB 4 — HOST: 숙소 프로필 / MASTER: 숙소 탐색
# ═══════════════════════════════════════
with tab_list[4]:
    if is_master:
        # 마스터: 전체 숙소 탐색
        st.subheader("🏠 전체 호스트 숙소")
        conn = database.get_db_connection()
        df_all_v = pd.read_sql_query("SELECT h.name,v.location,v.description,v.image1,v.image2,v.image3,v.image4,v.image5 FROM host_venues v JOIN hosts h ON v.host_id=h.id", conn)
        conn.close()
        if df_all_v.empty:
            st.info("등록된 숙소가 없습니다.")
        else:
            for _, v in df_all_v.iterrows():
                with st.expander(f"🏠 {v['name']} — 📍{v['location'] or ''}"):
                    render_b64_gallery([v.get(key) for key in VENUE_IMAGE_KEYS], columns_count=5)
                    if v['description']: st.caption(v['description'])
    else:
        render_host_income_billboard(load_host_income_snapshot(host_id))
        st.subheader("🏠 내 숙소 프로필")
        st.caption("숙소 위치와 내부 사진을 정리해 두면 쇼룸 완성도가 올라가고, 제휴 제안도 더 매끄럽게 받을 수 있어요.")

        conn = database.get_db_connection()
        q_v = ('SELECT * FROM host_venues WHERE host_id=%s' if database.DATABASE_URL
               else 'SELECT * FROM host_venues WHERE host_id=?')
        df_v = pd.read_sql_query(q_v, conn, params=(host_id,))
        conn.close()
        existing = df_v.iloc[0] if not df_v.empty else None

        current_images = [existing.get(key) if existing is not None else None for key in VENUE_IMAGE_KEYS]

        with st.container(border=True):
            st.markdown("#### ?? ?? ??")
            st.caption("?? ??? ??? ? ?? ???? ?? ???? ?? ??? ?????.")
            with st.form("venue_form"):
                location = st.text_input("?? ?? (?? ?? ???)", value=existing['location'] if existing is not None else "")
                description = st.text_area("?? ??", value=existing['description'] if existing is not None else "", height=120)
                st.markdown("**?? ?? ???**")
                render_b64_gallery(current_images, columns_count=5)
                uploaded_gallery = st.file_uploader(
                    "? ?? ?? 1~5?",
                    type=["jpg", "jpeg", "png", "webp"],
                    accept_multiple_files=True,
                    key="venue_gallery_batch",
                    help="?? ?? ? ?? ??? ?? ???? ? ?? ???? ?????.",
                )
                clear_gallery = st.checkbox("?? ?? ?? ?? ???", value=False, key="venue_gallery_clear")
                save_venue = st.form_submit_button("?? ?? ?? ??", use_container_width=True, type="primary")

        if save_venue:
            if uploaded_gallery and len(uploaded_gallery) > 5:
                st.error("?? ??? ? ?? ?? 5??? ???? ? ???.")
            else:
                next_images = current_images[:]
                if clear_gallery:
                    next_images = [None] * len(VENUE_IMAGE_KEYS)
                if uploaded_gallery:
                    uploaded_images = [database.file_to_base64(file) for file in uploaded_gallery[:5]]
                    next_images = uploaded_images + [None] * (len(VENUE_IMAGE_KEYS) - len(uploaded_images))

                conn = database.get_db_connection()
                cursor = conn.cursor()
                try:
                    if existing is not None:
                        q = ('UPDATE host_venues SET location=%s,description=%s,image1=%s,image2=%s,image3=%s,image4=%s,image5=%s WHERE host_id=%s'
                             if database.DATABASE_URL else
                             'UPDATE host_venues SET location=?,description=?,image1=?,image2=?,image3=?,image4=?,image5=? WHERE host_id=?')
                        cursor.execute(q, (location, description, *next_images, host_id))
                    else:
                        q = ('INSERT INTO host_venues (host_id,location,description,image1,image2,image3,image4,image5) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)'
                             if database.DATABASE_URL else
                             'INSERT INTO host_venues (host_id,location,description,image1,image2,image3,image4,image5) VALUES (?,?,?,?,?,?,?,?)')
                        cursor.execute(q, (host_id, location, description, *next_images))
                    database.bump_public_content_version(conn)
                    conn.commit()
                    st.success("? ?? ??? ???????!")
                    st.rerun()
                except Exception as e:
                    st.error(f"??: {e}")
                finally:
                    conn.close()

        if existing is not None:
            st.markdown("---")
            st.markdown("**?? ??? ?? ???**")
            render_b64_gallery([existing.get(key) for key in VENUE_IMAGE_KEYS], columns_count=5)

# ═══════════════════════════════════════
# TAB 5 — HOST: 입점 신청 / MASTER: 입점 전체 현황
# ═══════════════════════════════════════
with tab_list[5]:
    if is_master:
        st.subheader("🎁 전체 입점 현황")
        conn = database.get_db_connection()
        df_all_sp = pd.read_sql_query("""
            SELECT s.id, hb.name as 업체, hh.name as 호스트,
                   bi.item_name as 제품, s.qty as 수량, s.status as 상태, s.created_at as 일시
            FROM sponsorships s
            JOIN hosts hb ON s.brand_id=hb.id
            JOIN hosts hh ON s.host_id=hh.id
            JOIN brand_items bi ON s.brand_item_id=bi.id
            ORDER BY s.id DESC
        """, conn)
        conn.close()
        if df_all_sp.empty:
            st.info("입점 내역이 없습니다.")
        else:
            st.dataframe(df_all_sp.drop(columns=['id']), use_container_width=True, hide_index=True)
    else:
        # 호스트: 입점 신청 탭
        st.subheader("🎁 입점 신청")
        st.caption("입점업체가 등록한 제품을 확인하고 입점을 신청하세요. 체험 후 게스트에게 QR 주문을 유도할 수 있습니다.")

        conn = database.get_db_connection()
        df_all_items = pd.read_sql_query("""
            SELECT bi.id, h.name as brand_name, bi.item_name, bi.description, bi.stock_qty, bi.image
            FROM brand_items bi JOIN hosts h ON bi.brand_id=h.id
            WHERE bi.stock_qty > 0 ORDER BY bi.id DESC
        """, conn)
        conn.close()

        if df_all_items.empty:
            st.info("현재 입점 신청 가능한 제품이 없습니다.")
        else:
            # 카드형 UI
            for i in range(0, len(df_all_items), 2):
                row_data = df_all_items.iloc[i:i+2]
                cols = st.columns(2)
                for j, (_, item) in enumerate(row_data.iterrows()):
                    with cols[j]:
                        with st.container():
                            show_img(item['image'], width=240)
                            st.markdown(f"**{item['item_name']}**")
                            st.caption(f"🏷️ 공급업체: {item['brand_name']}")
                            st.caption(item['description'] or "")
                            st.markdown(f"📦 잔여 입점 수량: **{item['stock_qty']}개**")

                            key_prefix = f"apply_{item['id']}"
                            qty_key = f"{key_prefix}_qty"
                            btn_key = f"{key_prefix}_btn"

                            req_qty = st.number_input("신청 수량", min_value=1, max_value=int(item['stock_qty']), step=1, key=qty_key)
                            if st.button(f"🎁 입점 신청", key=btn_key, use_container_width=True, type="primary"):
                                conn2 = database.get_db_connection()
                                cursor2 = conn2.cursor()
                                try:
                                    q_dec = ('UPDATE brand_items SET stock_qty=stock_qty-%s WHERE id=%s'
                                             if database.DATABASE_URL else
                                             'UPDATE brand_items SET stock_qty=stock_qty-? WHERE id=?')
                                    cursor2.execute(q_dec, (req_qty, item['id']))
                                    q_ins = ('INSERT INTO sponsorships (brand_id,host_id,brand_item_id,qty,status) VALUES (%s,%s,%s,%s,%s)'
                                             if database.DATABASE_URL else
                                             'INSERT INTO sponsorships (brand_id,host_id,brand_item_id,qty,status) VALUES (?,?,?,?,?)')
                                    cursor2.execute(q_ins, (None, host_id, item['id'], req_qty, 'REQUESTED'))
                                    conn2.commit()
                                    st.success(f"✅ '{item['item_name']}' {req_qty}개 입점 신청 완료!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"오류: {e}")
                                finally:
                                    conn2.close()
                        st.markdown("")

        # 내가 신청한 입점 목록
        st.markdown("---")
        st.markdown("#### 📋 내 입점 신청 현황")
        conn = database.get_db_connection()
        q = ('SELECT bi.item_name as 제품, s.qty as 수량, s.status as 상태, s.created_at as 신청일시 FROM sponsorships s JOIN brand_items bi ON s.brand_item_id=bi.id WHERE s.host_id=%s ORDER BY s.id DESC'
             if database.DATABASE_URL else
             'SELECT bi.item_name as 제품, s.qty as 수량, s.status as 상태, s.created_at as 신청일시 FROM sponsorships s JOIN brand_items bi ON s.brand_item_id=bi.id WHERE s.host_id=? ORDER BY s.id DESC')
        df_my_sp = pd.read_sql_query(q, conn, params=(host_id,))
        conn.close()
        if df_my_sp.empty:
            st.info("신청한 입점이 없습니다.")
        else:
            st.dataframe(df_my_sp, use_container_width=True, hide_index=True)

# 작업 4: 호스트/관리자 공통 인사이트 탭 렌더링
with tab_list[-1]:
    render_insights_dashboard(host_id, is_master)

# ═══════════════════════════════════════
# MASTER ONLY: 사용자 관리 (TAB 4)
# ═══════════════════════════════════════
if is_master and len(tab_list) > 4:
    with tab_list[4]:
        st.subheader("👥 사용자 관리")
        conn = database.get_db_connection()
        df_users = pd.read_sql_query("SELECT id,username,name,role,is_master,email,phone,created_at FROM hosts ORDER BY id", conn)
        conn.close()
        st.dataframe(df_users, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════
# MASTER ONLY: 정산 대시보드 (TAB 5)
# ═══════════════════════════════════════
if is_master and len(tab_list) > 5:
    with tab_list[5]:
        st.title("💰 정산 관리 시스템")
        st.markdown("<p style='color:#888'>수익 구조: <b>(정가 - 판매가)의 50%</b>를 호스트와 플랫폼이 각각 배분</p>", unsafe_allow_html=True)
        conn = database.get_db_connection()
        date_func = "TO_CHAR(o.created_at,'MM/DD HH24:MI')" if database.DATABASE_URL else "strftime('%m/%d %H:%M',o.created_at)"
        q = f"""
            SELECT o.id, {date_func} as "일시", h.name as "호스트",
                   p.product_name as "상품", p.original_price as "정가", o.total_amount as "판매가", o.settlement_status as "상태"
            FROM orders o JOIN products p ON o.product_id=p.id
            JOIN hosts h ON p.owner_id=h.id ORDER BY o.id DESC
        """
        df_s = pd.read_sql_query(q, conn)
        if not df_s.empty:
            def calc_settlement(row, pct=0.5):
                gap = (row["정가"] - row["판매가"]) if row["정가"] and row["정가"] > row["판매가"] else 0
                return int(gap * pct)
            
            # 쿼리에 original_price 추가 필요
            df_s["플랫폼(50%)"] = df_s.apply(lambda r: calc_settlement(r, 0.5), axis=1)
            df_s["호스트(50%)"] = df_s.apply(lambda r: calc_settlement(r, 0.5), axis=1)
            pending_sale = df_s[df_s["상태"]=="PENDING"]["판매가"].sum()
            pending_platform = df_s[df_s["상태"]=="PENDING"]["플랫폼(50%)"].sum()
            pending_host = df_s[df_s["상태"]=="PENDING"]["호스트(50%)"].sum()
            
            c1,c2,c3 = st.columns(3)
            c1.metric("정산 대기 매출", f"{pending_sale:,}원")
            c2.metric("플랫폼 예상수익 (50%)", f"{pending_platform:,}원")
            c3.metric("호스트 지급예정 (50%)", f"{pending_host:,}원")
            st.markdown("---")
            st.dataframe(df_s.drop(columns=["id"]), use_container_width=True, hide_index=True)
            st.subheader("상태 업데이트")
            tid = st.selectbox("주문 ID", df_s["id"].tolist())
            nst = st.radio("변경 상태", ["PENDING","COMPLETED"], horizontal=True)
            if st.button("상태 반영 (Supabase 동기화)", type="primary"):
                curs = conn.cursor()
                q2 = ('UPDATE orders SET settlement_status=%s WHERE id=%s'
                      if database.DATABASE_URL else
                      'UPDATE orders SET settlement_status=? WHERE id=?')
                curs.execute(q2,(nst,tid))
                conn.commit()
                database.sync_order_to_supabase(tid)
                st.success(f"주문 #{tid} → {nst}")
                time.sleep(1)
                st.rerun()
        else:
            st.info("정산 데이터 없음")
        conn.close()

# ═══════════════════════════════════════
# MASTER ONLY: 문의사항 (TAB 6)
# ═══════════════════════════════════════
if is_master and len(tab_list) > 6:
    with tab_list[6]:
        st.subheader("📩 홈페이지 파트너 신청 문의사항")
        st.caption("랜딩 페이지의 '지금 시작하기' 단계별 폼을 통해 접수된 입점/호스트 문의 내역입니다.")
        
        conn = database.get_db_connection()
        date_func = "TO_CHAR(created_at,'YYYY-MM-DD HH24:MI')" if database.DATABASE_URL else "strftime('%Y-%m-%d %H:%M',created_at)"
        
        q_inq = f"""
            SELECT id, 
                   CASE WHEN inquiry_type='host' THEN '🏠 호스트' ELSE '🛍️ 브랜드' END as "구분",
                   name as "신청인 이름",
                   COALESCE(company_name, '') as "업체명",
                   contact as "연락처",
                   email as "이메일",
                   COALESCE(location, '') || COALESCE(platform, '') as "기타 정보",
                   COALESCE(category, '') as "카테고리",
                   message as "문의 세부내용",
                   {date_func} as "접수일시"
            FROM inquiries
            ORDER BY id DESC
        """
        
        try:
            df_inq = pd.read_sql_query(q_inq, conn)
            if df_inq.empty:
                st.info("새로 접수된 문의 내역이 없습니다.")
            else:
                st.dataframe(df_inq.drop(columns=['id']), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error("테이블 조회 오류 (DB가 갱신 중일 수 있습니다.)")
        finally:
            conn.close()
