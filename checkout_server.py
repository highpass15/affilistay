from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
from database import get_db_connection, init_db
import os
import httpx
import time
from typing import Dict
from pydantic import BaseModel
from datetime import datetime
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

# 클라우드 어드민 주소를 고정하여 즉시 연결되도록 합니다.
ADMIN_URL = 'https://affilistay-admin.onrender.com/'

# 카테고리 한글 매핑
ROOM_CATEGORIES = {
    'living_room': '거실',
    'bedroom': '침실',
    'kitchen': '주방',
    'bathroom': '화장실',
}

PRODUCT_CATEGORIES = {
    'furniture': '가구',
    'fabric': '패브릭',
    'appliance': '가전·디지털',
    'kitchenware': '주방용품',
    'food': '식품',
    'deco': '데코·식물',
    'lighting': '조명',
    'storage': '수납·정리',
    'hairdryer': '헤어드라이어',
    'lifestyle': '생활용품'
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
async def catalog_page(request: Request, category: str = Query(default=None)):
    """QR 접속 없이 플랫폼 전체 입점제품 및 숙소(호스트) 공간 구경"""
    conn = get_db_connection()

    if category and category in PRODUCT_CATEGORIES:
        products = _fetch_all(
            conn,
            "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id WHERE p.product_category = %s ORDER BY p.id",
            "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id WHERE p.product_category = ? ORDER BY p.id",
            (category,)
        )
    else:
        products = _fetch_all(
            conn,
            "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id ORDER BY p.product_category, p.id",
            "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id ORDER BY p.product_category, p.id"
        )
        
    hosts = _fetch_all(
        conn,
        "SELECT h.id, h.name as host_name, MIN(p.qr_code_id) as qr_code_id, v.location, v.image1 as venue_image, v.image2 as venue_image2, COUNT(p.id) as product_count FROM hosts h JOIN products p ON h.id = p.owner_id LEFT JOIN host_venues v ON h.id = v.host_id GROUP BY h.id, h.name, v.location, v.image1, v.image2",
        "SELECT h.id, h.name as host_name, MIN(p.qr_code_id) as qr_code_id, v.location, v.image1 as venue_image, v.image2 as venue_image2, COUNT(p.id) as product_count FROM hosts h JOIN products p ON h.id = p.owner_id LEFT JOIN host_venues v ON h.id = v.host_id GROUP BY h.id, h.name, v.location, v.image1, v.image2"
    )

    conn.close()

    categorized_by_item = {}
    for cat_key, cat_name in PRODUCT_CATEGORIES.items():
        cat_products = [p for p in products if p.get('product_category') == cat_key]
        if cat_products:
            categorized_by_item[cat_key] = {
                'name': cat_name,
                'products': cat_products
            }
            
    return templates.TemplateResponse(
        request=request,
        name="catalog.html",
        context={
            "prod_categories": PRODUCT_CATEGORIES,
            "categorized_by_item": categorized_by_item,
            "active_category": category,
            "all_products": products,
            "hosts": hosts,
        }
    )


# ─────────────────────────────────────────
# 숙소 쇼룸 메인 페이지
# ─────────────────────────────────────────
@app.get("/shop/{qr_code_id}", response_class=HTMLResponse)
async def shop_page(request: Request, qr_code_id: str, category: str = Query(default=None)):
    """
    QR 코드 ID로 진입 → 해당 제품의 호스트(owner_id) 기반으로
    같은 숙소의 모든 입점제품을 카테고리별로 표시합니다.
    """
    conn = get_db_connection()

    # 1. QR 코드에 해당하는 제품 조회 → owner_id 추출
    entry_product = _fetch_one(
        conn,
        "SELECT * FROM products WHERE qr_code_id = %s",
        "SELECT * FROM products WHERE qr_code_id = ?",
        (qr_code_id,)
    )

    if not entry_product:
        conn.close()
        return HTMLResponse(
            content="<html><body style='font-family:Outfit,sans-serif;text-align:center;padding-top:20%;background:#FAF9F6'>"
                    "<h2 style='font-weight:300'>유효하지 않은 QR 코드입니다</h2>"
                    "<p style='color:#888;font-size:14px'>만료되었거나 존재하지 않는 코드입니다.</p></body></html>",
            status_code=404
        )

    owner_id = entry_product.get('owner_id')

    # 2. 호스트 정보 조회
    host_info = _fetch_one(
        conn,
        "SELECT name FROM hosts WHERE id = %s",
        "SELECT name FROM hosts WHERE id = ?",
        (owner_id,)
    ) if owner_id else None

    host_name = host_info['name'] if host_info else "AFFILISTAY Showroom"

    # 3. 해당 호스트의 모든 제품을 카테고리별로 조회
    if category and category in ROOM_CATEGORIES:
        products = _fetch_all(
            conn,
            "SELECT * FROM products WHERE owner_id = %s AND room_category = %s ORDER BY id",
            "SELECT * FROM products WHERE owner_id = ? AND room_category = ? ORDER BY id",
            (owner_id, category)
        )
    else:
        products = _fetch_all(
            conn,
            "SELECT * FROM products WHERE owner_id = %s ORDER BY room_category, id",
            "SELECT * FROM products WHERE owner_id = ? ORDER BY room_category, id",
            (owner_id,)
        )

    conn.close()

    # 4. 카테고리별 제품 그룹핑
    categorized = {}
    for cat_key, cat_name in ROOM_CATEGORIES.items():
        cat_products = [p for p in products if p.get('room_category') == cat_key]
        if cat_products:
            categorized[cat_key] = {
                'name': cat_name,
                'products': cat_products
            }

    return templates.TemplateResponse(
        request=request,
        name="shop.html",
        context={
            "host_name": host_name,
            "qr_code_id": qr_code_id,
            "categories": ROOM_CATEGORIES,
            "categorized": categorized,
            "active_category": category,
            "all_products": products,
        }
    )


# ─────────────────────────────────────────
# 제품 상세 페이지
# ─────────────────────────────────────────
@app.get("/shop/{qr_code_id}/product/{product_id}", response_class=HTMLResponse)
async def product_detail(request: Request, qr_code_id: str, product_id: int):
    """개별 제품 상세 페이지"""
    conn = get_db_connection()

    product = _fetch_one(
        conn,
        "SELECT * FROM products WHERE id = %s",
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    )

    if not product:
        conn.close()
        return HTMLResponse(
            content="<html><body style='font-family:Outfit,sans-serif;text-align:center;padding-top:20%;background:#FAF9F6'>"
                    "<h2 style='font-weight:300'>제품을 찾을 수 없습니다</h2></body></html>",
            status_code=404
        )

    # 추가 이미지 조회
    images = _fetch_all(
        conn,
        "SELECT image_data FROM product_images WHERE product_id = %s ORDER BY sort_order",
        "SELECT image_data FROM product_images WHERE product_id = ? ORDER BY sort_order",
        (product_id,)
    )
    
    # 옵션 조회
    options_db = _fetch_all(
        conn,
        "SELECT name, values FROM product_options WHERE product_id = %s",
        "SELECT name, values FROM product_options WHERE product_id = ?",
        (product_id,)
    )
    # 옵션 값들을 리스트로 변환
    options = []
    for opt in options_db:
        options.append({
            'name': opt['name'],
            'values': [v.strip() for v in opt['values'].split(',')]
        })

    # 리뷰 조회
    reviews = _fetch_all(
        conn,
        "SELECT * FROM reviews WHERE product_id = %s ORDER BY created_at DESC",
        "SELECT * FROM reviews WHERE product_id = ? ORDER BY created_at DESC",
        (product_id,)
    )

    # 문의 조회
    inquiries = _fetch_all(
        conn,
        "SELECT * FROM product_inquiries WHERE product_id = %s ORDER BY created_at DESC",
        "SELECT * FROM product_inquiries WHERE product_id = ? ORDER BY created_at DESC",
        (product_id,)
    )

    cross_sell_products = _fetch_all(
        conn,
        "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id WHERE p.owner_id != %s ORDER BY RANDOM() LIMIT 4",
        "SELECT p.*, h.name as host_name FROM products p JOIN hosts h ON p.owner_id = h.id WHERE p.owner_id != ? ORDER BY RANDOM() LIMIT 4",
        (product['owner_id'],)
    )

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="product_detail.html",
        context={
            "product": product,
            "images": images if images else [{'image_data': product['image_url']}],
            "options": options,
            "reviews": reviews,
            "inquiries": inquiries,
            "qr_code_id": qr_code_id,
            "room_label": ROOM_CATEGORIES.get(product.get('room_category', ''), ''),
            "product_category_label": PRODUCT_CATEGORIES.get(product.get('product_category', ''), ''),
            "cross_sell_products": cross_sell_products,
        }
    )


# ─────────────────────────────────────────
# 주문서 페이지
# ─────────────────────────────────────────
@app.get("/shop/{qr_code_id}/order/{product_id}", response_class=HTMLResponse)
async def order_form(request: Request, qr_code_id: str, product_id: int):
    """주문서 작성 페이지"""
    conn = get_db_connection()

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
    params = dict(request.query_params)
    selected_options_str = ", ".join([f"{k}: {v}" for k, v in params.items()])

    return templates.TemplateResponse(
        request=request,
        name="order_form.html",
        context={
            "product": product,
            "qr_code_id": qr_code_id,
            "selected_options": selected_options_str,
            "cross_sell_products": cross_sell_products,
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
):
    """주문 처리 → PayPal 결제 링크 생성 → 리다이렉트"""
    import traceback
    try:
        conn = get_db_connection()

    if _is_pg():
        with conn.cursor() as cur:
            cur.execute('SELECT id, price, product_name FROM products WHERE id = %s', (product_id,))
            product = cur.fetchone()
            if product:
                cur.execute('''
                    INSERT INTO orders (product_id, customer_name, phone_number, shipping_address, delivery_note, total_amount, selected_options, fcm_token, session_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                ''', (product[0], customer_name, phone_number, shipping_address, delivery_note, product[1], selected_options, fcm_token, session_id))
                order_id = cur.fetchone()[0]
    else:
        product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
        if product:
            cursor = conn.execute('''
                INSERT INTO orders (product_id, customer_name, phone_number, shipping_address, delivery_note, total_amount, selected_options, fcm_token, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (product['id'], customer_name, phone_number, shipping_address, delivery_note, product['price'], selected_options, fcm_token, session_id))
            order_id = cursor.lastrowid

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
            return HTMLResponse(content="<h1>PayPal API Error</h1>", status_code=500)
            
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
                "cancel_url": f"{base_url}/shop/{qr_code_id}",
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
        return HTMLResponse(content=f"<pre>{traceback.format_exc()}</pre>", status_code=500)

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
