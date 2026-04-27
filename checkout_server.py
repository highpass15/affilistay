from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
from database import get_db_connection, get_public_content_version, init_db
import os
import httpx
import time
from typing import Dict, List
from pydantic import BaseModel
from datetime import datetime
from urllib.parse import quote
from decimal import Decimal, InvalidOperation
import fcm_service
import base64
from dotenv import load_dotenv

load_dotenv()
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET")
PAYPAL_API_BASE = "https://api-m.sandbox.paypal.com" # Use live API base in production

class PageViewEvent(BaseModel):
    session_id: str
    product_id: int = None
    host_id: int = None
    page_url: str
    duration_seconds: int
    enter_time: str

app = FastAPI(title="AffiliStay Showroom Platform")

@app.on_event("startup")
def run_migrations():
    """앱 시작 시 누락된 데이터베이스 컬럼을 자동 추가합니다."""
    init_db()
    conn = get_db_connection()
    try:
        if _is_pg():
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS fcm_token TEXT")
                cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS session_id TEXT")
            conn.commit()
        else:
            try:
                conn.execute("ALTER TABLE orders ADD COLUMN fcm_token TEXT")
                conn.execute("ALTER TABLE orders ADD COLUMN session_id TEXT")
                conn.commit()
            except:
                pass
    except Exception as e:
        print(f"[Migration Error] {e}")
    finally:
        conn.close()

# 클라우드 어드민 주소를 고정하여 즉시 연결되도록 합니다.
ADMIN_URL = "https://affilistay-admin.onrender.com/"

@app.get("/api/force-migrate")
def force_migrate():
    conn = get_db_connection()
    try:
        if _is_pg():
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS fcm_token TEXT")
                cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS session_id TEXT")
            conn.commit()
            return {"status": "success", "msg": "pg migrated"}
        else:
            try:
                conn.execute("ALTER TABLE orders ADD COLUMN fcm_token TEXT")
                conn.execute("ALTER TABLE orders ADD COLUMN session_id TEXT")
            except:
                pass
            conn.commit()
            return {"status": "success", "msg": "sqlite migrated"}
    except Exception as e:
        import traceback
        return {"status": "error", "msg": str(e), "traceback": traceback.format_exc()}
    finally:
        conn.close()


@app.get("/api/public-content-version")
def public_content_version():
    return JSONResponse(
        {"version": get_public_content_version()},
        headers={"Cache-Control": "no-store, max-age=0"},
    )

# ???? ???/??? ??
ROOM_CATEGORIES = {
    "living_room": "거실",
    "bedroom": "침실",
    "kitchen": "주방",
    "bathroom": "욕실",
}

ROOM_ICONS = {
    "living_room": "🛋️",
    "bedroom": "🛏️",
    "kitchen": "🍳",
    "bathroom": "🛁",
}

PRODUCT_CATEGORIES = {
    "lighting": "조명",
    "hairdryer": "헤어드라이어",
    "furniture": "가구",
    "fabric": "패브릭",
    "appliance": "가전·디지털",
    "kitchenware": "주방용품",
    "food": "식품",
    "deco": "데코·식물",
    "storage": "수납·정리",
    "lifestyle": "생활용품",
}

PRODUCT_ICONS = {
    "lighting": "💡",
    "hairdryer": "💨",
    "furniture": "🪑",
    "fabric": "🧵",
    "appliance": "🔌",
    "kitchenware": "🍽️",
    "food": "🥯",
    "deco": "🪴",
    "storage": "📦",
    "lifestyle": "🧴",
}

# 정적 파일(이미지 등) 서비스 설정
static_dir = os.path.join(os.path.dirname(__file__), 'static')
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
templates = Jinja2Templates(directory=template_dir)

# ─────────────────────────────────────────
# 실시간 환율 관리 (Frankfurter API 사용)
# ─────────────────────────────────────────
EXCHANGE_RATES_CACHE = {
    "timestamp": 0,
    "rates": {"USD": 0.00072, "JPY": 0.11, "CNY": 0.0052}, # 기본값 (업데이트 실패 시 대비)
}

async def get_exchange_rates() -> Dict:
    """KRW 기준 최신 환율을 가져오고 1시간 동안 캐싱합니다."""
    now = time.time()
    if now - EXCHANGE_RATES_CACHE["timestamp"] < 3600: # 1시간
        return EXCHANGE_RATES_CACHE["rates"]
    
    try:
        async with httpx.AsyncClient() as client:
            # KRW 기준 환율 가져오기
            resp = await client.get("https://api.frankfurter.app/latest?from=KRW")
            if resp.status_code == 200:
                data = resp.json()
                rates = data.get("rates", {})
                # USD, JPY, CNY 필터링 (없으면 기존 캐시 유지)
                for c in ["USD", "JPY", "CNY"]:
                    if c in rates:
                        EXCHANGE_RATES_CACHE["rates"][c] = rates[c]
                EXCHANGE_RATES_CACHE["timestamp"] = now
    except Exception as e:
        print(f"[ERROR] Failed to fetch exchange rates: {e}")
        
    return EXCHANGE_RATES_CACHE["rates"]

@app.get("/api/exchange-rates")
async def api_get_rates():
    rates = await get_exchange_rates()
    return {"status": "success", "base": "KRW", "rates": rates}

# ─────────────────────────────────────────
# Customer Login (SNS Login)
# ─────────────────────────────────────────
@app.get("/customer/login", response_class=HTMLResponse)
async def customer_login_page(request: Request, return_url: str = Query(default="/")):
    """Customer login page."""
    safe_return_url = _safe_return_to(return_url, "/catalog")
    return templates.TemplateResponse(
        request=request,
        name="customer_login.html",
        context={"request": request, "return_url": safe_return_url},
    )

@app.post("/customer/login")
async def customer_login_process(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    return_url: str = Form(default="/")
):
    """
    ?? ???/???? ??? ??
    MVP ????? ???? ?? ?? ???? ??/??? ??
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # ???? ?? ?? ??
    cursor.execute("SELECT id FROM customers WHERE email = %s" if os.environ.get('DATABASE_URL') else "SELECT id FROM customers WHERE email = ?", (email,))
    customer = cursor.fetchone()
    
    if not customer:
        # ??? ???? ??
        cursor.execute(
            "INSERT INTO customers (email, password, provider) VALUES (%s, %s, 'email') RETURNING id" if os.environ.get('DATABASE_URL') else "INSERT INTO customers (email, password, provider) VALUES (?, ?, 'email')",
            (email, password)
        )
        if not os.environ.get('DATABASE_URL'):
            customer_id = cursor.lastrowid
        else:
            customer_id = cursor.fetchone()[0]
        conn.commit()
    else:
        customer_id = customer['id'] if isinstance(customer, sqlite3.Row) or os.environ.get('DATABASE_URL') else customer[0]
        
    conn.close()
    
    # ??? ??: ?? ?? ?? ?? (???? MVP? ?? ????? ??? ????? ??)
    safe_return_url = _safe_return_to(return_url, "/catalog")
    response = RedirectResponse(url=safe_return_url, status_code=303)
    response.set_cookie(key="customer_id", value=str(customer_id), httponly=True)
    return response

@app.get("/customer/login/sns/{provider}")
async def customer_sns_login(provider: str, return_url: str = Query(default="/")):
    """
    SNS ?? ??? (Mock)
    MVP ????? SNS ?? ?? ? ?? SNS ?? ???? ?? ??/??? ? ??? ??
    """
    mock_email = f"user_{provider}@example.com"
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM customers WHERE email = %s" if os.environ.get('DATABASE_URL') else "SELECT id FROM customers WHERE email = ?", (mock_email,))
    customer = cursor.fetchone()
    
    if not customer:
        cursor.execute(
            "INSERT INTO customers (email, provider, provider_id) VALUES (%s, %s, %s) RETURNING id" if os.environ.get('DATABASE_URL') else "INSERT INTO customers (email, provider, provider_id) VALUES (?, ?, ?)",
            (mock_email, provider, f"mock_id_{provider}")
        )
        if not os.environ.get('DATABASE_URL'):
            customer_id = cursor.lastrowid
        else:
            customer_id = cursor.fetchone()[0]
        conn.commit()
    else:
        customer_id = customer['id'] if isinstance(customer, sqlite3.Row) or os.environ.get('DATABASE_URL') else customer[0]
        
    conn.close()
    
    safe_return_url = _safe_return_to(return_url, "/catalog")
    response = RedirectResponse(url=safe_return_url, status_code=303)
    response.set_cookie(key="customer_id", value=str(customer_id), httponly=True)
    return response

@app.get("/customer/logout")
async def customer_logout(return_url: str = Query(default="/catalog")):
    safe_return_url = _safe_return_to(return_url, "/catalog")
    response = RedirectResponse(url=safe_return_url, status_code=303)
    response.delete_cookie("customer_id")
    return response

@app.post("/api/portone/verify")
async def verify_portone_payment(request: Request):
    """
    PortOne(아임포트) 결제 완료 후 검증 및 주문 DB 저장
    MVP 단계에서는 클라이언트 데이터를 신뢰하여 저장합니다. (운영 시에는 PortOne API로 실제 결제 금액 교차 검증 필요)
    """
    try:
        data = await request.json()
        imp_uid = data.get('imp_uid')
        merchant_uid = data.get('merchant_uid')
        qr_code_id = data.get('qr_code_id', '')
        items = data.get('items', [])
        customer_name = data.get('customer_name', '')
        phone_number = data.get('phone_number', '')
        shipping_address = data.get('shipping_address', '')
        delivery_note = data.get('delivery_note', '')
        payment_method = data.get('payment_method', 'card')

        if not items:
            return JSONResponse(content={"status": "error", "message": "장바구니가 비어있습니다."})

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 클라이언트가 쿠키로 보낸 customer_id 확인 (없으면 비회원)
        customer_id = request.cookies.get("customer_id")
        
        order_ids = []
        for item in items:
            p_id = item.get('id')
            qty = int(item.get('quantity', 1))
            price = int(item.get('price', 0))
            opts = item.get('options', {})

            cursor.execute("SELECT price FROM products WHERE id = %s" if _is_pg() else "SELECT price FROM products WHERE id = ?", (p_id,))
            db_product = cursor.fetchone()
            if not db_product:
                continue

            real_price = db_product[0]
            item_total = real_price * qty
            # MVP용 15% 할인 적용
            item_total = int(item_total * 0.85)

            for _ in range(qty):
                if _is_pg():
                    cursor.execute("""
                        INSERT INTO orders (
                            product_id, customer_id, customer_name, phone_number, shipping_address, delivery_note,
                            total_amount, payment_method, imp_uid, payment_status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PAID')
                        RETURNING id
                    """, (p_id, customer_id, customer_name, phone_number, shipping_address, delivery_note, real_price, payment_method, imp_uid))
                    order_id = cursor.fetchone()[0]
                else:
                    cursor.execute("""
                        INSERT INTO orders (
                            product_id, customer_id, customer_name, phone_number, shipping_address, delivery_note,
                            total_amount, payment_method, imp_uid, payment_status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PAID')
                    """, (p_id, customer_id, customer_name, phone_number, shipping_address, delivery_note, real_price, payment_method, imp_uid))
                    order_id = cursor.lastrowid
                order_ids.append(order_id)

        conn.commit()
        conn.close()

        # 첫 번째 주문 번호 기준으로 완료 페이지 이동
        redirect_url = f"/order-complete/{order_ids[0]}?qr={qr_code_id}&clear_cart=true" if order_ids else "/"
        return JSONResponse(content={"status": "success", "redirect_url": redirect_url})

    except Exception as e:
        print("PortOne verify error:", e)
        return JSONResponse(content={"status": "error", "message": str(e)})

# ─────────────────────────────────────────
# PayPal API 연동 모듈 (다중 주문 처리)
# ─────────────────────────────────────────

# ─────────────────────────────────────────
# 헬퍼 함수: DB 호환 쿼리 실행
# ─────────────────────────────────────────
def _is_pg():
    """PostgreSQL 사용 여부 확인"""
    return bool(os.environ.get('DATABASE_URL'))

def _ph(param):
    """DB에 맞는 플레이스홀더 반환 (%s 또는 ?)"""
    return '%s' if _is_pg() else '?'

def _fetch_all(conn, query_pg, query_sqlite, params=None):
    """SELECT 결과를 dict 리스트로 반환"""
    query = query_pg if _is_pg() else query_sqlite
    if _is_pg():
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows]
    else:
        cursor = conn.execute(query, params or ())
        return [dict(row) for row in cursor.fetchall()]

def _fetch_one(conn, query_pg, query_sqlite, params=None):
    """SELECT 단일 결과를 dict로 반환"""
    query = query_pg if _is_pg() else query_sqlite
    if _is_pg():
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()
            return dict(zip(columns, row)) if row else None
    else:
        row = conn.execute(query, params or ()).fetchone()
        return dict(row) if row else None


def _catalog_image_map(conn):
    try:
        rows = _fetch_all(
            conn,
            "SELECT product_id, image_data, sort_order FROM product_images ORDER BY product_id, sort_order, id",
            "SELECT product_id, image_data, sort_order FROM product_images ORDER BY product_id, sort_order, id",
        )
    except Exception:
        return {}
    image_map = {}
    for row in rows:
        image_map.setdefault(row["product_id"], row["image_data"])
    return image_map


def _catalog_gallery_map(conn):
    try:
        rows = _fetch_all(
            conn,
            "SELECT product_id, image_data, sort_order FROM product_images ORDER BY product_id, sort_order, id",
            "SELECT product_id, image_data, sort_order FROM product_images ORDER BY product_id, sort_order, id",
        )
    except Exception:
        return {}
    gallery_map = {}
    for row in rows:
        gallery_map.setdefault(row["product_id"], []).append(row["image_data"])
    return gallery_map



def _category_items(labels, icons, counts=None):
    counts = counts or {}
    return [
        {
            "key": key,
            "label": label,
            "icon": icons.get(key, "*"),
            "count": int(counts.get(key, 0) or 0),
        }
        for key, label in labels.items()
    ]


def _catalog_filter_counts(conn, selected_category="all", selected_room="all"):
    try:
        rows = _fetch_all(
            conn,
            "SELECT product_category, room_category FROM products",
            "SELECT product_category, room_category FROM products",
        )
    except Exception:
        return (
            {key: 0 for key in PRODUCT_CATEGORIES},
            {key: 0 for key in ROOM_CATEGORIES},
        )

    category_counts = {key: 0 for key in PRODUCT_CATEGORIES}
    room_counts = {key: 0 for key in ROOM_CATEGORIES}

    for row in rows:
        product_category = row.get("product_category")
        room_category = row.get("room_category")

        if product_category in PRODUCT_CATEGORIES and (
            selected_room == "all" or room_category == selected_room
        ):
            category_counts[product_category] += 1

        if room_category in ROOM_CATEGORIES and (
            selected_category == "all" or product_category == selected_category
        ):
            room_counts[room_category] += 1

    return category_counts, room_counts


def _safe_return_to(raw_return_to, fallback):
    if raw_return_to and raw_return_to.startswith("/") and not raw_return_to.startswith("//"):
        return raw_return_to
    return fallback


def _encode_return_to(path):
    return quote(path, safe="")


def _coerce_image_data(value):
    if value is None:
        return None
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return base64.b64encode(value).decode("ascii")
    return str(value)


def _coerce_int(value, default=0):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, Decimal):
        return int(value)
    try:
        normalized = str(value).replace(",", "").strip()
        if not normalized:
            return default
        return int(Decimal(normalized))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _normalize_product_record(product):
    if not product:
        return product
    product["image_url"] = _coerce_image_data(product.get("image_url"))
    product["price"] = _coerce_int(product.get("price"))
    product["original_price"] = _coerce_int(product.get("original_price"), product["price"])
    for key in (
        "brand_name",
        "product_name",
        "description",
        "detailed_description",
        "host_name",
        "host_location",
        "host_description",
        "room_category",
        "product_category",
    ):
        if product.get(key) is None:
            continue
        product[key] = str(product.get(key))
    return product


def _decorate_catalog_products(products, image_map, gallery_map=None):
    gallery_map = gallery_map or {}
    for product in products:
        _normalize_product_record(product)
        original_price = product.get("original_price") or product.get("price") or 0
        price = product.get("price") or 0
        gallery_images = _build_gallery_images(
            product.get("image_url"),
            [{"image_data": image_data} for image_data in gallery_map.get(product["id"], [])],
        )
        product["primary_image"] = gallery_images[0] if gallery_images else None
        product["gallery_images"] = gallery_images
        product["gallery_count"] = len(gallery_images)
        product["room_label"] = ROOM_CATEGORIES.get(product.get("room_category"), "??")
        product["room_icon"] = ROOM_ICONS.get(product.get("room_category"), "?")
        product["category_label"] = PRODUCT_CATEGORIES.get(product.get("product_category"), "????")
        product["category_icon"] = PRODUCT_ICONS.get(product.get("product_category"), "?")
        product["discount_rate"] = int(((original_price - price) / original_price) * 100) if original_price and original_price > price else 0
    return products


def _unique_products(products: List[dict]) -> List[dict]:
    seen = set()
    unique = []
    for product in products:
        product_id = product.get("id")
        if not product_id or product_id in seen:
            continue
        seen.add(product_id)
        unique.append(product)
    return unique


def _build_gallery_images(primary_image, image_rows):
    gallery = []
    seen = set()
    for image_data in [primary_image, *[row.get("image_data") for row in image_rows]]:
        image_data = _coerce_image_data(image_data)
        if not image_data or image_data in seen:
            continue
        seen.add(image_data)
        gallery.append(image_data)
    return gallery


def _display_date(value):
    if hasattr(value, "strftime"):
        return value.strftime("%Y.%m.%d")
    if value is None:
        return ""
    return str(value)[:10]


def _decorate_recommendation_products(products, image_map, gallery_map=None):
    products = _decorate_catalog_products(products, image_map, gallery_map)
    for product in products:
        showroom_path = f"/showrooms/{product['owner_id']}" if product.get("owner_id") else "/catalog?view=spaces"
        product["showroom_path"] = showroom_path
        product["detail_path"] = (
            f"/shop/{product['qr_code_id']}/product/{product['id']}"
            f"?return_to={_encode_return_to(showroom_path)}"
        )
    return products


def _build_product_recommendations(conn, product):
    image_map = _catalog_image_map(conn)
    gallery_map = _catalog_gallery_map(conn)
    owner_id = product.get("owner_id")
    product_id = product.get("id")
    current_room = product.get("room_category")
    current_category = product.get("product_category")
    current_price = product.get("price") or 0

    same_owner_products = _fetch_all(
        conn,
        """
        SELECT p.*, h.name as host_name, v.location as host_location
        FROM products p
        JOIN hosts h ON p.owner_id = h.id
        LEFT JOIN host_venues v ON p.owner_id = v.host_id
        WHERE p.owner_id = %s AND p.id != %s
        ORDER BY p.id DESC
        """,
        """
        SELECT p.*, h.name as host_name, v.location as host_location
        FROM products p
        JOIN hosts h ON p.owner_id = h.id
        LEFT JOIN host_venues v ON p.owner_id = v.host_id
        WHERE p.owner_id = ? AND p.id != ?
        ORDER BY p.id DESC
        """,
        (owner_id, product_id),
    )
    same_owner_products = _decorate_recommendation_products(same_owner_products, image_map, gallery_map)

    same_showroom_products = same_owner_products
    if current_room:
        same_showroom_products = [item for item in same_owner_products if item.get("room_category") == current_room]
        if len(same_showroom_products) < 4:
            same_showroom_products = _unique_products(same_showroom_products + same_owner_products)
    same_showroom_products = same_showroom_products[:6]

    host_curated_products = [
        item for item in same_owner_products
        if item.get("room_category") != current_room or item.get("product_category") != current_category
    ]
    if not host_curated_products:
        excluded = {item["id"] for item in same_showroom_products}
        host_curated_products = [item for item in same_owner_products if item.get("id") not in excluded]
    host_curated_products = host_curated_products[:6]

    similar_candidates = _fetch_all(
        conn,
        """
        SELECT p.*, h.name as host_name, v.location as host_location
        FROM products p
        JOIN hosts h ON p.owner_id = h.id
        LEFT JOIN host_venues v ON p.owner_id = v.host_id
        WHERE p.owner_id != %s
        ORDER BY p.id DESC
        LIMIT 48
        """,
        """
        SELECT p.*, h.name as host_name, v.location as host_location
        FROM products p
        JOIN hosts h ON p.owner_id = h.id
        LEFT JOIN host_venues v ON p.owner_id = v.host_id
        WHERE p.owner_id != ?
        ORDER BY p.id DESC
        LIMIT 48
        """,
        (owner_id,),
    )
    similar_candidates = _decorate_recommendation_products(similar_candidates, image_map, gallery_map)

    def recommendation_score(item):
        category_match = item.get("product_category") == current_category
        room_match = item.get("room_category") == current_room
        price_gap = abs((item.get("price") or 0) - current_price)
        if category_match and room_match:
            affinity = 0
        elif category_match:
            affinity = 1
        elif room_match:
            affinity = 2
        else:
            affinity = 3
        return (
            affinity,
            price_gap,
            -int(item.get("discount_rate") or 0),
            -int(item.get("id") or 0),
        )

    similar_products = [
        item for item in similar_candidates
        if item.get("product_category") == current_category or item.get("room_category") == current_room
    ]
    if len(similar_products) < 6:
        similar_products = _unique_products(similar_products + similar_candidates)
    similar_products = sorted(similar_products, key=recommendation_score)[:6]

    return {
        "same_showroom_products": same_showroom_products,
        "host_curated_products": host_curated_products,
        "similar_products": similar_products,
    }


def _build_catalog_hosts(conn):
    try:
        hosts = _fetch_all(
            conn,
            """
            SELECT
                h.id,
                h.name as host_name,
                MIN(p.qr_code_id) as qr_code_id,
                v.location,
                v.description,
                v.image1 as venue_image,
                v.image2 as venue_image2,
                v.image3 as venue_image3,
                v.image4 as venue_image4,
                v.image5 as venue_image5,
                COUNT(p.id) as product_count
            FROM hosts h
            JOIN products p ON h.id = p.owner_id
            LEFT JOIN host_venues v ON h.id = v.host_id
            GROUP BY h.id, h.name, v.location, v.description, v.image1, v.image2, v.image3, v.image4, v.image5
            ORDER BY product_count DESC, h.id DESC
            """,
            """
            SELECT
                h.id,
                h.name as host_name,
                MIN(p.qr_code_id) as qr_code_id,
                v.location,
                v.description,
                v.image1 as venue_image,
                v.image2 as venue_image2,
                v.image3 as venue_image3,
                v.image4 as venue_image4,
                v.image5 as venue_image5,
                COUNT(p.id) as product_count
            FROM hosts h
            JOIN products p ON h.id = p.owner_id
            LEFT JOIN host_venues v ON h.id = v.host_id
            GROUP BY h.id, h.name, v.location, v.description, v.image1, v.image2, v.image3, v.image4, v.image5
            ORDER BY product_count DESC, h.id DESC
            """,
        )
    except Exception:
        return []
    for host in hosts:
        host["entry_path"] = f"/showrooms/{host['id']}"
        host["space_icon"] = "🏠"
        host["gallery_images"] = [
            img for img in [
                host.get("venue_image"),
                host.get("venue_image2"),
                host.get("venue_image3"),
                host.get("venue_image4"),
                host.get("venue_image5"),
            ] if img
        ]
        host["gallery_count"] = len(host["gallery_images"])
    return hosts


def _fetch_catalog_products(conn, category):
    base_pg = "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id ORDER BY p.id DESC"
    base_sqlite = "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id ORDER BY p.id DESC"
    filtered_pg = "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id WHERE p.product_category = %s ORDER BY p.id DESC"
    filtered_sqlite = "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id WHERE p.product_category = ? ORDER BY p.id DESC"

    try:
        if category != "all" and category in PRODUCT_CATEGORIES:
            products = _fetch_all(conn, filtered_pg, filtered_sqlite, (category,))
        else:
            products = _fetch_all(conn, base_pg, base_sqlite)
    except Exception:
        products = _fetch_all(conn, base_pg, base_sqlite)

    if category != "all":
        products = [p for p in products if p.get("product_category") == category]
    return products


def _build_showroom_context(conn, host_id):
    showroom = _fetch_one(
        conn,
        """
        SELECT
            h.id,
            h.name as host_name,
            v.location,
            v.description,
            v.image1 as venue_image,
            v.image2 as venue_image2,
            v.image3 as venue_image3,
            v.image4 as venue_image4,
            v.image5 as venue_image5
        FROM hosts h
        LEFT JOIN host_venues v ON h.id = v.host_id
        WHERE h.id = %s
        """,
        """
        SELECT
            h.id,
            h.name as host_name,
            v.location,
            v.description,
            v.image1 as venue_image,
            v.image2 as venue_image2,
            v.image3 as venue_image3,
            v.image4 as venue_image4,
            v.image5 as venue_image5
        FROM hosts h
        LEFT JOIN host_venues v ON h.id = v.host_id
        WHERE h.id = ?
        """,
        (host_id,),
    )
    if not showroom:
        return None, []

    showroom["gallery_images"] = [
        img for img in [
            showroom.get("venue_image"),
            showroom.get("venue_image2"),
            showroom.get("venue_image3"),
            showroom.get("venue_image4"),
            showroom.get("venue_image5"),
        ] if img
    ]

    products = _fetch_all(
        conn,
        "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id WHERE p.owner_id = %s ORDER BY p.room_category, p.id DESC",
        "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id WHERE p.owner_id = ? ORDER BY p.room_category, p.id DESC",
        (host_id,),
    )
    image_map = _catalog_image_map(conn)
    gallery_map = _catalog_gallery_map(conn)
    return showroom, _decorate_catalog_products(products, image_map, gallery_map)


# ─────────────────────────────────────────
# 기본 라우트
# ─────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, qr: str = Query(default=None)):
    """
    랜딩 페이지 또는 QR 리다이렉트 처리.
    기존 QR 링크 /?qr=XXXX 호환성 유지.
    """
    if qr:
        return RedirectResponse(url=f"/shop/{qr}", status_code=301)
    return templates.TemplateResponse(
        request=request, name="landing.html", context={"admin_url": ADMIN_URL}
    )

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# ─────────────────────────────────────────
# 파트너 문의 API
# ─────────────────────────────────────────
@app.post("/api/inquiry")
async def receive_inquiry(
    inquiry_type: str = Form(...),
    name: str = Form(...),
    contact: str = Form(...),
    email: str = Form(...),
    company_name: str = Form(default=""),
    job_title: str = Form(default=""),
    location: str = Form(default=""),
    platform: str = Form(default=""),
    category: str = Form(default=""),
    message: str = Form(default="")
):
    conn = get_db_connection()
    if _is_pg():
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO inquiries (inquiry_type, name, contact, email, company_name, job_title, location, platform, category, message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (inquiry_type, name, contact, email, company_name, job_title, location, platform, category, message))
    else:
        conn.execute('''
            INSERT INTO inquiries (inquiry_type, name, contact, email, company_name, job_title, location, platform, category, message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (inquiry_type, name, contact, email, company_name, job_title, location, platform, category, message))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "성공적으로 접수되었습니다."}


# ─────────────────────────────────────────
# 글로벌 카탈로그 (전체 룩북)
# ─────────────────────────────────────────
@app.get("/catalog", response_class=HTMLResponse)
async def catalog_page(
    request: Request,
    view: str = Query(default="products"),
    category: str = Query(default="all"),
    room: str = Query(default="all"),
):
    """QR 접속 없이 플랫폼 전체 입점제품 및 숙소(호스트) 공간 구경"""
    if view not in {"products", "spaces"}:
        view = "products"

    public_content_version = get_public_content_version()
    conn = get_db_connection()
    products = []
    hosts = []
    category_counts, room_counts = _catalog_filter_counts(conn, category, room)

    if view == "products":
        products = _fetch_catalog_products(conn, category)

        if room != "all" and room in ROOM_CATEGORIES:
            products = [p for p in products if p.get("room_category") == room]

        image_map = _catalog_image_map(conn)
        gallery_map = _catalog_gallery_map(conn)
        products = _decorate_catalog_products(products, image_map, gallery_map)
    else:
        hosts = _build_catalog_hosts(conn)

    conn.close()

    if view == "products":
        current_url = f"/catalog?view={view}&category={category}&room={room}"
    else:
        current_url = "/catalog?view=spaces"

    current_url_encoded = _encode_return_to(current_url)
    customer_logged_in = bool(request.cookies.get("customer_id"))

    return templates.TemplateResponse(
        request=request,
        name="catalog.html",
        context={
            "view": view,
            "category": category,
            "room": room,
            "products": products,
            "hosts": hosts,
            "prod_categories": PRODUCT_CATEGORIES,
            "prod_category_items": _category_items(PRODUCT_CATEGORIES, PRODUCT_ICONS, category_counts),
            "room_categories": ROOM_CATEGORIES,
            "room_category_items": _category_items(ROOM_CATEGORIES, ROOM_ICONS, room_counts),
            "has_space_data": len(hosts) > 0,
            "admin_url": ADMIN_URL,
            "current_url": current_url,
            "current_url_encoded": current_url_encoded,
            "customer_logged_in": customer_logged_in,
            "customer_login_url": f"/customer/login?return_url={current_url_encoded}",
            "customer_logout_url": f"/customer/logout?return_url={current_url_encoded}",
            "public_content_version": public_content_version,
        },
    )


@app.get("/showrooms/{host_id}", response_class=HTMLResponse)
async def showroom_detail(request: Request, host_id: int):
    public_content_version = get_public_content_version()
    conn = get_db_connection()
    showroom, products = _build_showroom_context(conn, host_id)
    conn.close()

    if not showroom:
        return HTMLResponse(content="<h1>존재하지 않는 쇼룸입니다.</h1>", status_code=404)

    current_url = f"/showrooms/{host_id}"

    return templates.TemplateResponse(
        request=request,
        name="showroom.html",
        context={
            "showroom": showroom,
            "products": products,
            "admin_url": ADMIN_URL,
            "current_url": current_url,
            "current_url_encoded": _encode_return_to(current_url),
            "public_content_version": public_content_version,
        },
    )


# ─────────────────────────────────────────
# 숙소 쇼룸 메인 페이지
# ─────────────────────────────────────────
@app.get("/shop/{qr_code_id}", response_class=HTMLResponse)
async def shop_page(request: Request, qr_code_id: str, category: str = Query(default=None)):
    """
    QR ??? ?? ?? ?? ?? ?? ?? ??? ?? ??? ?? ????.
    """
    conn = get_db_connection()
    entry_product = _fetch_one(
        conn,
        "SELECT id, owner_id FROM products WHERE qr_code_id = %s",
        "SELECT id, owner_id FROM products WHERE qr_code_id = ?",
        (qr_code_id,),
    )

    if not entry_product:
        conn.close()
        return HTMLResponse(
            content="<html><body style='font-family:Outfit,sans-serif;text-align:center;padding-top:20%;background:#FAF9F6'>"
                    "<h2 style='font-weight:300'>???? ?? QR ?????</h2>"
                    "<p style='color:#888;font-size:14px'>?????? ???? ?? ?????.</p></body></html>",
            status_code=404,
        )

    showroom_path = (
        f"/showrooms/{entry_product['owner_id']}"
        if entry_product.get("owner_id")
        else "/catalog?view=spaces"
    )
    conn.close()
    return RedirectResponse(
        url=(
            f"/shop/{qr_code_id}/product/{entry_product['id']}"
            f"?return_to={_encode_return_to(showroom_path)}"
        ),
        status_code=303,
    )


@app.get("/shop/{qr_code_id}/product/{product_id}", response_class=HTMLResponse)
async def product_detail(
    request: Request,
    qr_code_id: str,
    product_id: int,
    return_to: str = Query(default=""),
):
    """?? ?? ?? ?? ???"""
    public_content_version = get_public_content_version()
    conn = get_db_connection()

    product = _fetch_one(
        conn,
        """
        SELECT p.*, h.name as host_name, v.location as host_location, v.description as host_description
        FROM products p
        JOIN hosts h ON p.owner_id = h.id
        LEFT JOIN host_venues v ON p.owner_id = v.host_id
        WHERE p.id = %s
        """,
        """
        SELECT p.*, h.name as host_name, v.location as host_location, v.description as host_description
        FROM products p
        JOIN hosts h ON p.owner_id = h.id
        LEFT JOIN host_venues v ON p.owner_id = v.host_id
        WHERE p.id = ?
        """,
        (product_id,),
    )

    if not product:
        conn.close()
        return HTMLResponse(
            content="<html><body style='font-family:Outfit,sans-serif;text-align:center;padding-top:20%;background:#FAF9F6'>"
                    "<h2 style='font-weight:300'>??? ?? ? ????</h2></body></html>",
            status_code=404,
        )

    product = _normalize_product_record(product)
    showroom_path = f"/showrooms/{product['owner_id']}" if product.get("owner_id") else "/catalog?view=spaces"
    return_to = _safe_return_to(return_to, showroom_path)

    try:
        images = _fetch_all(
            conn,
            "SELECT image_data FROM product_images WHERE product_id = %s ORDER BY sort_order",
            "SELECT image_data FROM product_images WHERE product_id = ? ORDER BY sort_order",
            (product_id,),
        )
    except Exception:
        images = []

    try:
        options_db = _fetch_all(
            conn,
            'SELECT name, "values" FROM product_options WHERE product_id = %s',
            'SELECT name, "values" FROM product_options WHERE product_id = ?',
            (product_id,),
        )
    except Exception:
        options_db = []
    options = []
    for opt in options_db:
        option_name = str(opt.get("name") or "").strip()
        raw_values = opt.get("values") or ""
        option_values = [value.strip() for value in str(raw_values).split(",") if value and value.strip()]
        if not option_name or not option_values:
            continue
        options.append({"name": option_name, "values": option_values})

    try:
        reviews = _fetch_all(
            conn,
            "SELECT * FROM reviews WHERE product_id = %s ORDER BY created_at DESC",
            "SELECT * FROM reviews WHERE product_id = ? ORDER BY created_at DESC",
            (product_id,),
        )
    except Exception:
        reviews = []

    try:
        inquiries = _fetch_all(
            conn,
            "SELECT * FROM product_inquiries WHERE product_id = %s ORDER BY created_at DESC",
            "SELECT * FROM product_inquiries WHERE product_id = ? ORDER BY created_at DESC",
            (product_id,),
        )
    except Exception:
        inquiries = []

    for review in reviews:
        review["display_date"] = _display_date(review.get("created_at"))
    for inquiry in inquiries:
        inquiry["display_date"] = _display_date(inquiry.get("created_at"))

    try:
        recommendation_groups = _build_product_recommendations(conn, product)
    except Exception as exc:
        print(f"[Product Detail Recommendation Error] product_id={product_id}: {exc}")
        recommendation_groups = {
            "same_showroom_products": [],
            "host_curated_products": [],
            "similar_products": [],
        }

    gallery_images = _build_gallery_images(product.get("image_url"), images)
    product["room_icon"] = ROOM_ICONS.get(product.get("room_category"), "⌂")
    product["category_icon"] = PRODUCT_ICONS.get(product.get("product_category"), "✦")
    conn.close()

    context = {
        "request": request,
        "product": product,
        "gallery_images": gallery_images,
        "options": options,
        "reviews": reviews,
        "inquiries": inquiries,
        "qr_code_id": qr_code_id,
        "room_label": ROOM_CATEGORIES.get(product.get("room_category", ""), ""),
        "product_category_label": PRODUCT_CATEGORIES.get(product.get("product_category", ""), ""),
        "showroom_path": showroom_path,
        "same_showroom_products": recommendation_groups["same_showroom_products"],
        "host_curated_products": recommendation_groups["host_curated_products"],
        "similar_products": recommendation_groups["similar_products"],
        "return_to": return_to,
        "return_to_encoded": _encode_return_to(return_to),
        "public_content_version": public_content_version,
    }

    try:
        rendered = templates.get_template("product_detail.html").render(context)
    except Exception as exc:
        print(f"[Product Detail Render Error] product_id={product_id}: {exc}")
        fallback_context = {
            **context,
            "gallery_images": gallery_images[:1],
            "options": [],
            "reviews": [],
            "inquiries": [],
            "same_showroom_products": [],
            "host_curated_products": [],
            "similar_products": [],
        }
        rendered = templates.get_template("product_detail.html").render(fallback_context)

    return HTMLResponse(content=rendered)


@app.get("/shop/{qr_code_id}/cart")
async def view_cart(request: Request, qr_code_id: str, return_to: str = Query(default="")):
    """장바구니 페이지 (클라이언트의 localStorage 기반으로 렌더링)"""
    return_to = _safe_return_to(return_to, f"/shop/{qr_code_id}")
    return templates.TemplateResponse(
        request=request,
        name="cart.html",
        context={
            "qr_code_id": qr_code_id,
            "return_to": return_to,
            "return_to_encoded": _encode_return_to(return_to),
        }
    )


# ─────────────────────────────────────────
# 주문서 페이지
# ─────────────────────────────────────────
@app.get("/shop/{qr_code_id}/order/{product_id}", response_class=HTMLResponse)
async def order_form(
    request: Request,
    qr_code_id: str,
    product_id: int,
    return_to: str = Query(default=""),
):
    """주문서 작성 페이지"""
    conn = get_db_connection()
    return_to = _safe_return_to(return_to, f"/shop/{qr_code_id}/product/{product_id}")

    product = _fetch_one(
        conn,
        "SELECT * FROM products WHERE id = %s",
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    )

    if not product:
        conn.close()
        return HTMLResponse(content="<h1>제품을 찾을 수 없습니다</h1>", status_code=404)

    cross_sell_products = _fetch_all(
        conn,
        "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id WHERE p.owner_id != %s ORDER BY RANDOM() LIMIT 4",
        "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id WHERE p.owner_id != ? ORDER BY RANDOM() LIMIT 4",
        (product['owner_id'],)
    )
    
    conn.close()

    # 선택된 옵션 파싱 (쿼리 스트링에서)
    params = {k: v for k, v in dict(request.query_params).items() if k != "return_to"}
    selected_options_str = ", ".join([f"{k}: {v}" for k, v in params.items()])

    return templates.TemplateResponse(
        request=request,
        name="order_form.html",
        context={
            "product": product,
            "qr_code_id": qr_code_id,
            "selected_options": selected_options_str,
            "cross_sell_products": cross_sell_products,
            "return_to": return_to,
            "return_to_encoded": _encode_return_to(return_to),
        }
    )


# ─────────────────────────────────────────
# 주문 처리 API
# ─────────────────────────────────────────
@app.post("/shop/{qr_code_id}/order")
async def process_order(
    request: Request,
    qr_code_id: str,
    product_id: int = Form(...),
    customer_name: str = Form(...),
    phone_number: str = Form(...),
    shipping_address: str = Form(...),
    delivery_note: str = Form(default=""),
    selected_options: str = Form(default=""),
    fcm_token: str = Form(default=""),
    session_id: str = Form(default=""),
    return_to: str = Form(default=""),
):
    """주문 처리 → PayPal 결제 링크 생성 → 리다이렉트"""
    conn = get_db_connection()
    return_to = _safe_return_to(return_to, f"/shop/{qr_code_id}")

    if _is_pg():
        with conn.cursor() as cur:
            cur.execute('SELECT id, price, product_name FROM products WHERE id = %s', (product_id,))
            product = cur.fetchone()
            if product:
                try:
                    cur.execute('''
                        INSERT INTO orders (product_id, customer_name, phone_number, shipping_address, delivery_note, total_amount, selected_options, fcm_token, session_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                    ''', (product[0], customer_name, phone_number, shipping_address, delivery_note, product[1], selected_options, fcm_token, session_id))
                    order_id = cur.fetchone()[0]
                except Exception as e:
                    import traceback
                    return HTMLResponse(content=f"<h1>DB Insert Error</h1><pre>{traceback.format_exc()}</pre>", status_code=500)
    else:
        product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
        if product:
            try:
                cursor = conn.execute('''
                    INSERT INTO orders (product_id, customer_name, phone_number, shipping_address, delivery_note, total_amount, selected_options, fcm_token, session_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (product['id'], customer_name, phone_number, shipping_address, delivery_note, product['price'], selected_options, fcm_token, session_id))
                order_id = cursor.lastrowid
            except Exception as e:
                import traceback
                return HTMLResponse(content=f"<h1>DB Insert Error</h1><pre>{traceback.format_exc()}</pre>", status_code=500)

    conn.commit()
    conn.close()

    if not product:
        return HTMLResponse(content="<h1>제품을 찾을 수 없습니다</h1>", status_code=404)

    # ── PayPal 결제 링크 생성 ──
    rates = await get_exchange_rates()
    usd_rate = rates.get("USD", 0.00072)
    amount_krw = product['price'] if not _is_pg() else product[1]
    final_amount_usd = round(amount_krw * usd_rate, 2)

    auth_string = f"{PAYPAL_CLIENT_ID}:{PAYPAL_SECRET}"
    b64_auth = base64.b64encode(auth_string.encode()).decode()

    try:
        async with httpx.AsyncClient() as client:
            # 1. 엑세스 토큰 발급
            token_resp = await client.post(
                f"{PAYPAL_API_BASE}/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                headers={
                    "Authorization": f"Basic {b64_auth}",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            if token_resp.status_code != 200:
                return HTMLResponse(content=f"<h1>PayPal API Error</h1><pre>{token_resp.text}</pre>", status_code=500)
                
            access_token = token_resp.json().get("access_token")

            # 2. 페이팔 오더 생성
            base_url = str(request.base_url).rstrip("/")
            if "onrender.com" in base_url:
                base_url = base_url.replace("http://", "https://")

            order_payload = {
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": "USD",
                        "value": str(final_amount_usd)
                    },
                    "custom_id": str(order_id)
                }],
                "application_context": {
                    "return_url": f"{base_url}/api/paypal/return?order_id={order_id}&qr_code_id={qr_code_id}&currency=USD&exchange_rate={usd_rate}",
                    "cancel_url": f"{base_url}{return_to}",
                    "user_action": "PAY_NOW"
                }
            }
            
            order_resp = await client.post(
                f"{PAYPAL_API_BASE}/v2/checkout/orders",
                json=order_payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if order_resp.status_code not in (200, 201):
                return HTMLResponse(content=f"<h1>PayPal Order Error: {order_resp.text}</h1>", status_code=500)
                
            order_data = order_resp.json()
            
            approve_link = None
            for link in order_data.get("links", []):
                if link.get("rel") == "approve":
                    approve_link = link.get("href")
                    break
                    
            if approve_link:
                return RedirectResponse(url=approve_link, status_code=303)
            else:
                return HTMLResponse(content="<h1>No PayPal approve link found</h1>", status_code=500)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"<h1>PayPal API Exception</h1><pre>{traceback.format_exc()}</pre>", status_code=500)


# ─────────────────────────────────────────
# 장바구니 통합 주문 처리 API
# ─────────────────────────────────────────
@app.get("/shop/{qr_code_id}/order_cart", response_class=HTMLResponse)
async def order_cart_form(request: Request, qr_code_id: str, return_to: str = Query(default="")):
    """장바구니 다중 상품 주문서 작성 페이지"""
    conn = get_db_connection()
    return_to = _safe_return_to(return_to, f"/shop/{qr_code_id}/cart")
    cross_sell_products = _fetch_all(
        conn,
        "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id ORDER BY RANDOM() LIMIT 4",
        "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id ORDER BY RANDOM() LIMIT 4",
        ()
    )
    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="order_cart_form.html",
        context={
            "qr_code_id": qr_code_id,
            "return_to": return_to,
            "return_to_encoded": _encode_return_to(return_to),
            "product": {"price": 0, "product_name": "장바구니 상품"}, # JS에서 덮어씀
            "cross_sell_products": cross_sell_products,
        }
    )

import json

@app.post("/shop/{qr_code_id}/order_cart")
async def process_cart_order(
    request: Request,
    qr_code_id: str,
    items_json: str = Form(...),
    customer_name: str = Form(...),
    phone_number: str = Form(...),
    shipping_address: str = Form(...),
    delivery_note: str = Form(default=""),
    fcm_token: str = Form(default=""),
    session_id: str = Form(default=""),
    return_to: str = Form(default=""),
):
    """장바구니 다중 상품 주문 처리 → PayPal 결제 링크 생성 → 리다이렉트"""
    return_to = _safe_return_to(return_to, f"/shop/{qr_code_id}/cart")
    
    try:
        items = json.loads(items_json)
    except:
        return HTMLResponse(content="<h1>잘못된 장바구니 데이터입니다.</h1>", status_code=400)
        
    if not items:
        return HTMLResponse(content="<h1>장바구니가 비어있습니다.</h1>", status_code=400)

    conn = get_db_connection()
    order_ids = []
    total_amount_krw = 0
    
    try:
        # PostgreSQL/SQLite 공통: 여러 줄 insert
        for item in items:
            p_id = item.get('id')
            qty = item.get('quantity', 1)
            options_str = ", ".join([f"{k}: {v}" for k, v in item.get('options', {}).items()])
            
            # DB 가격 재확인 (보안)
            p_db = _fetch_one(conn, "SELECT price FROM products WHERE id = %s", "SELECT price FROM products WHERE id = ?", (p_id,))
            if not p_db: continue
            
            real_price = p_db['price'] if not _is_pg() else p_db[0]
            item_total = real_price * qty
            total_amount_krw += item_total
            
            # 수량만큼 반복해서 insert하거나(기존 1주문 1상품 구조 유지 시) quantity 컬럼을 추가해야함.
            # 관리자 호환을 위해 quantity만큼 반복 insert
            for _ in range(qty):
                if _is_pg():
                    with conn.cursor() as cur:
                        cur.execute('''
                            INSERT INTO orders (product_id, customer_name, phone_number, shipping_address, delivery_note, total_amount, selected_options, fcm_token, session_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                        ''', (p_id, customer_name, phone_number, shipping_address, delivery_note, real_price, options_str, fcm_token, session_id))
                        order_ids.append(cur.fetchone()[0])
                else:
                    cursor = conn.execute('''
                        INSERT INTO orders (product_id, customer_name, phone_number, shipping_address, delivery_note, total_amount, selected_options, fcm_token, session_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (p_id, customer_name, phone_number, shipping_address, delivery_note, real_price, options_str, fcm_token, session_id))
                    order_ids.append(cursor.lastrowid)

        conn.commit()
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"<h1>DB Insert Error</h1><pre>{traceback.format_exc()}</pre>", status_code=500)
    finally:
        conn.close()

    if not order_ids:
        return HTMLResponse(content="<h1>처리할 상품이 없습니다.</h1>", status_code=400)

    # ── PayPal 결제 링크 생성 ──
    rates = await get_exchange_rates()
    usd_rate = rates.get("USD", 0.00072)
    final_amount_usd = round(total_amount_krw * usd_rate, 2)

    auth_string = f"{PAYPAL_CLIENT_ID}:{PAYPAL_SECRET}"
    b64_auth = base64.b64encode(auth_string.encode()).decode()

    try:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                f"{PAYPAL_API_BASE}/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                headers={
                    "Authorization": f"Basic {b64_auth}",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            if token_resp.status_code != 200:
                return HTMLResponse(content=f"<h1>PayPal API Error</h1><pre>{token_resp.text}</pre>", status_code=500)
                
            access_token = token_resp.json().get("access_token")

            base_url = str(request.base_url).rstrip("/")
            if "onrender.com" in base_url:
                base_url = base_url.replace("http://", "https://")

            # 여러 order_id를 넘기기 위해 대표값 하나만 custom_id로 쓰고 나머지는 return URL에 파라미터로 붙임. 
            # (return 에서 paypal_order_id = ? 로 일괄 업데이트 하는 것이 더 안전하므로 custom_id는 크게 중요하지 않음)
            primary_order_id = order_ids[0]
            order_ids_str = ",".join(map(str, order_ids))

            order_payload = {
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": "USD",
                        "value": str(final_amount_usd)
                    },
                    "custom_id": str(primary_order_id)
                }],
                "application_context": {
                    "return_url": f"{base_url}/api/paypal/return_cart?order_ids={order_ids_str}&qr_code_id={qr_code_id}&currency=USD&exchange_rate={usd_rate}",
                    "cancel_url": f"{base_url}{return_to}",
                    "user_action": "PAY_NOW"
                }
            }
            
            order_resp = await client.post(
                f"{PAYPAL_API_BASE}/v2/checkout/orders",
                json=order_payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if order_resp.status_code not in (200, 201):
                return HTMLResponse(content=f"<h1>PayPal Order Error: {order_resp.text}</h1>", status_code=500)
                
            order_data = order_resp.json()
            paypal_order_id = order_data.get("id")

            # 모든 주문에 paypal_order_id 저장 (매우 중요)
            conn = get_db_connection()
            if _is_pg():
                with conn.cursor() as cur:
                    cur.execute(f"UPDATE orders SET paypal_order_id = %s WHERE id IN ({','.join(['%s']*len(order_ids))})", 
                              [paypal_order_id] + order_ids)
            else:
                conn.execute(f"UPDATE orders SET paypal_order_id = ? WHERE id IN ({','.join(['?']*len(order_ids))})", 
                           [paypal_order_id] + order_ids)
            conn.commit()
            conn.close()

            approve_link = None
            for link in order_data.get("links", []):
                if link.get("rel") == "approve":
                    approve_link = link.get("href")
                    break
                    
            if approve_link:
                return RedirectResponse(url=approve_link, status_code=303)
            else:
                return HTMLResponse(content="<h1>No PayPal approve link found</h1>", status_code=500)
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"<h1>PayPal API Exception</h1><pre>{traceback.format_exc()}</pre>", status_code=500)


@app.get("/api/paypal/return_cart")
async def paypal_return_cart(
    request: Request,
    token: str = Query(...), 
    PayerID: str = Query(None),
    order_ids: str = Query(...), # comma separated list
    qr_code_id: str = Query(...),
    currency: str = Query(default="USD"),
    exchange_rate: float = Query(default=1.0)
):
    """장바구니 페이팔 결제 승인 후 돌아오는 콜백 엔드포인트"""
    paypal_order_id = token
    
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        return HTMLResponse(content="<h1>PayPal credentials missing</h1>", status_code=500)
        
    auth_string = f"{PAYPAL_CLIENT_ID}:{PAYPAL_SECRET}"
    b64_auth = base64.b64encode(auth_string.encode()).decode()
    
    async with httpx.AsyncClient() as client:
        # 1. 토큰 발급
        token_resp = await client.post(
            f"{PAYPAL_API_BASE}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            headers={
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )
        if token_resp.status_code != 200:
            return HTMLResponse(content="<h1>Failed to authenticate with PayPal</h1>", status_code=500)
            
        access_token = token_resp.json().get("access_token")
        
        # 2. 결제 캡처 (최종 출금 승인)
        capture_resp = await client.post(
            f"{PAYPAL_API_BASE}/v2/checkout/orders/{paypal_order_id}/capture",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        )
        
        if capture_resp.status_code not in (200, 201):
            return HTMLResponse(content=f"<h1>PayPal Capture Error: {capture_resp.text}</h1>", status_code=500)
            
        capture_data = capture_resp.json()
        status = capture_data.get("status")
        
        if status != "COMPLETED":
            return HTMLResponse(content=f"<h1>PayPal Capture Not Completed: {status}</h1>", status_code=400)
            
    # 3. DB 업데이트
    conn = get_db_connection()
    fcm_tokens = []
    
    order_id_list = [int(oid.strip()) for oid in order_ids.split(",") if oid.strip()]
    if not order_id_list:
        return HTMLResponse(content="<h1>Invalid order IDs</h1>", status_code=400)
        
    try:
        if _is_pg():
            with conn.cursor() as cur:
                cur.execute(f'''
                    UPDATE orders SET payment_status = 'PAID', currency = %s, exchange_rate = %s
                    WHERE paypal_order_id = %s RETURNING fcm_token
                ''', (currency, exchange_rate, paypal_order_id))
                rows = cur.fetchall()
                for row in rows:
                    if row[0] and row[0] not in fcm_tokens:
                        fcm_tokens.append(row[0])
        else:
            conn.execute(f'''
                UPDATE orders SET payment_status = 'PAID', currency = ?, exchange_rate = ?
                WHERE paypal_order_id = ?
            ''', (currency, exchange_rate, paypal_order_id))
            rows = conn.execute('SELECT fcm_token FROM orders WHERE paypal_order_id = ?', (paypal_order_id,)).fetchall()
            for row in rows:
                if row[0] and row[0] not in fcm_tokens:
                    fcm_tokens.append(row[0])
        
        conn.commit()
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"<h1>DB Error</h1><pre>{traceback.format_exc()}</pre>", status_code=500)
    finally:
        conn.close()
    
    # 4. Supabase 동기화
    import database
    for oid in order_id_list:
        try:
            database.sync_order_to_supabase(oid)
        except:
            pass
    
    # 5. 푸시 알림 전송 (대표 1건만 발송하거나 내용 변경)
    for fcm_token in fcm_tokens:
        try:
            fcm_service.send_push_notification(
                token=fcm_token,
                title="장바구니 결제 완료 안내",
                body=f"고객님의 주문(총 {len(order_id_list)}건) 결제가 완료되었습니다. 곧 배송 준비를 시작하겠습니다.",
                data={"order_id": str(order_id_list[0])} # 메인 order id 전달
            )
        except Exception as e:
            print("FCM Push error:", e)
            
    # 6. 완료 페이지로 이동
    return RedirectResponse(url=f"/order-complete/{order_id_list[0]}?qr={qr_code_id}&clear_cart=true", status_code=303)

@app.get("/api/paypal/return")
async def paypal_return(
    request: Request,
    token: str = Query(...), 
    order_id: int = Query(...),
    qr_code_id: str = Query(...),
    currency: str = Query(default="USD"),
    exchange_rate: float = Query(default=1.0)
):
    """페이팔 결제 완료 후 사용자가 돌아오는 엔드포인트"""
    paypal_order_id = token
    
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        return HTMLResponse(content="<h1>PayPal credentials missing</h1>", status_code=500)
        
    auth_string = f"{PAYPAL_CLIENT_ID}:{PAYPAL_SECRET}"
    b64_auth = base64.b64encode(auth_string.encode()).decode()
    
    async with httpx.AsyncClient() as client:
        # 1. 토큰 발급
        token_resp = await client.post(
            f"{PAYPAL_API_BASE}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            headers={
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )
        if token_resp.status_code != 200:
            return HTMLResponse(content="<h1>Failed to authenticate with PayPal</h1>", status_code=500)
            
        access_token = token_resp.json().get("access_token")
        
        # 2. 결제 캡처 (최종 출금 승인)
        capture_resp = await client.post(
            f"{PAYPAL_API_BASE}/v2/checkout/orders/{paypal_order_id}/capture",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        )
        
        if capture_resp.status_code not in (200, 201):
            return HTMLResponse(content=f"<h1>PayPal Capture Error: {capture_resp.text}</h1>", status_code=500)
            
        capture_data = capture_resp.json()
        status = capture_data.get("status")
        
        if status != "COMPLETED":
            return HTMLResponse(content=f"<h1>PayPal Capture Not Completed: {status}</h1>", status_code=400)
            
    # 3. DB 업데이트
    conn = get_db_connection()
    fcm_token = None
    if _is_pg():
        with conn.cursor() as cur:
            cur.execute('''
                UPDATE orders SET paypal_order_id = %s, payment_status = 'PAID', currency = %s, exchange_rate = %s
                WHERE id = %s RETURNING fcm_token
            ''', (paypal_order_id, currency, exchange_rate, order_id))
            row = cur.fetchone()
            if row: fcm_token = row[0]
    else:
        conn.execute('''
            UPDATE orders SET paypal_order_id = ?, payment_status = 'PAID', currency = ?, exchange_rate = ?
            WHERE id = ?
        ''', (paypal_order_id, currency, exchange_rate, order_id))
        row = conn.execute('SELECT fcm_token FROM orders WHERE id = ?', (order_id,)).fetchone()
        if row: fcm_token = row[0]
    
    conn.commit()
    conn.close()
    
    # 4. Supabase 동기화
    import database
    database.sync_order_to_supabase(order_id)
    
    # 5. 푸시 알림 전송
    if fcm_token:
        try:
            fcm_service.send_push_notification(
                token=fcm_token,
                title="결제 완료 안내",
                body=f"고객님의 주문(#{order_id}) 결제가 완료되었습니다. 곧 배송 준비를 시작하겠습니다.",
                data={"order_id": str(order_id), "type": "payment_complete"}
            )
        except Exception as e:
            print(f"FCM Push Error: {e}")
            
    # 6. 완료 페이지로 이동
    return RedirectResponse(url=f"/order-complete/{order_id}?qr={qr_code_id}", status_code=303)


# ─────────────────────────────────────────
# 주문 완료 페이지
# ─────────────────────────────────────────
@app.get("/order-complete/{order_id}", response_class=HTMLResponse)
async def order_complete(request: Request, order_id: int, qr: str = Query(default="")):
    """주문 완료 확인 페이지"""
    conn = get_db_connection()

    order = _fetch_one(
        conn,
        """SELECT o.*, p.product_name, p.brand_name, p.price
           FROM orders o JOIN products p ON o.product_id = p.id
           WHERE o.id = %s""",
        """SELECT o.*, p.product_name, p.brand_name, p.price
           FROM orders o JOIN products p ON o.product_id = p.id
           WHERE o.id = ?""",
        (order_id,)
    )

    conn.close()

    if not order:
        return HTMLResponse(content="<h1 style='text-align:center; margin-top:50px;'>주문 내역을 찾을 수 없습니다.</h1>", status_code=404)
        
    if order.get('payment_status') != 'PAID':
        return HTMLResponse(
            content=f"""
            <div style='text-align:center; font-family:sans-serif; margin-top:50px;'>
                <h2>결제가 아직 완료되지 않았습니다 🚫</h2>
                <p>정상적인 페이팔 결제 과정을 거치지 않은 주문이거나, 아직 처리 중입니다.</p>
                <a href='/shop/{qr}' style='display:inline-block; margin-top:20px; padding:10px 20px; background:#000; color:#fff; text-decoration:none; border-radius:5px;'>쇼룸으로 돌아가기</a>
            </div>
            """, 
            status_code=403
        )

    return templates.TemplateResponse(
        request=request,
        name="order_complete.html",
        context={
            "order": order,
            "order_id": order_id,
            "qr_code_id": qr,
        }
    )


# ─────────────────────────────────────────
# 레거시 호환: 기존 /buy/{qr_code_id} 라우트 유지
# ─────────────────────────────────────────
@app.get("/buy/{qr_code_id}", response_class=HTMLResponse)
async def legacy_checkout(request: Request, qr_code_id: str):
    """기존 직접 결제 라우트 → 새로운 쇼룸으로 리다이렉트"""
    return RedirectResponse(url=f"/shop/{qr_code_id}", status_code=301)


if __name__ == "__main__":
    init_db()
    # fcm_service.py 의 의존성을 안전하게 임포트 
    try:
        import fcm_service
        # fcm_service.init_firebase() # 서비스 워커에서 이미 초기화
    except Exception as e:
        print(f"FCM Init Error: {e}")
        
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ─────────────────────────────────────────
# ── 웹사이트 방문 체류 시간 및 고객 트래킹 API ──
# ─────────────────────────────────────────
@app.post("/api/track/page_view")
async def track_page_view(event: PageViewEvent):
    """
    프론트엔드에서 beforeunload 이벤트를 통해 체류 시간(duration_seconds)을 기록함.
    """
    conn = get_db_connection()
    try:
        if _is_pg():
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO page_views (session_id, product_id, host_id, page_url, enter_time, duration_seconds)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (event.session_id, event.product_id, event.host_id, event.page_url, event.enter_time, event.duration_seconds))
        else:
            conn.execute('''
                INSERT INTO page_views (session_id, product_id, host_id, page_url, enter_time, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (event.session_id, event.product_id, event.host_id, event.page_url, event.enter_time, event.duration_seconds))
        conn.commit()
    except Exception as e:
        print(f"Tracking error: {e}")
    finally:
        conn.close()
    return {"status": "success"}

# ─────────────────────────────────────────
# 리뷰/문의 제출 처리
# ─────────────────────────────────────────
@app.post("/shop/{qr_code_id}/product/{product_id}/review")
async def post_review(
    qr_code_id: str,
    product_id: int,
    customer_name: str = Form(...),
    rating: int = Form(5),
    comment: str = Form(...),
):
    conn = get_db_connection()
    q = ("INSERT INTO reviews (product_id, customer_name, rating, comment) VALUES (%s,%s,%s,%s)"
         if _is_pg() else "INSERT INTO reviews (product_id, customer_name, rating, comment) VALUES (?,?,?,?)")
    if _is_pg():
        with conn.cursor() as cur: cur.execute(q, (product_id, customer_name, rating, comment))
    else:
        conn.execute(q, (product_id, customer_name, rating, comment))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/shop/{qr_code_id}/product/{product_id}?tab=reviews", status_code=303)

@app.post("/shop/{qr_code_id}/product/{product_id}/inquiry")
async def post_inquiry(
    qr_code_id: str,
    product_id: int,
    customer_name: str = Form(...),
    type: str = Form(...),
    content: str = Form(...),
):
    conn = get_db_connection()
    q = ("INSERT INTO product_inquiries (product_id, customer_name, type, content) VALUES (%s,%s,%s,%s)"
         if _is_pg() else "INSERT INTO product_inquiries (product_id, customer_name, type, content) VALUES (?,?,?,?)")
    if _is_pg():
        with conn.cursor() as cur: cur.execute(q, (product_id, customer_name, type, content))
    else:
        conn.execute(q, (product_id, customer_name, type, content))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/shop/{qr_code_id}/product/{product_id}?tab=inquiries", status_code=303)
