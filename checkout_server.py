from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
from database import get_db_connection
import os

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
    'lighting': '조명',
    'bedding': '침구',
    'kitchenware': '주방용품',
    'lifestyle': '생활/소품'
}

# 정적 파일(이미지 등) 서비스 설정
static_dir = os.path.join(os.path.dirname(__file__), 'static')
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
templates = Jinja2Templates(directory=template_dir)

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
        "SELECT h.id, h.name as host_name, MIN(p.qr_code_id) as qr_code_id, v.location, v.image1 as venue_image, COUNT(p.id) as product_count FROM hosts h JOIN products p ON h.id = p.owner_id LEFT JOIN host_venues v ON h.id = v.host_id GROUP BY h.id, h.name, v.location, v.image1",
        "SELECT h.id, h.name as host_name, MIN(p.qr_code_id) as qr_code_id, v.location, v.image1 as venue_image, COUNT(p.id) as product_count FROM hosts h JOIN products p ON h.id = p.owner_id LEFT JOIN host_venues v ON h.id = v.host_id GROUP BY h.id, h.name, v.location, v.image1"
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
            "qr_code_id": qr_code_id,
            "room_label": ROOM_CATEGORIES.get(product.get('room_category', ''), ''),
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

    return templates.TemplateResponse(
        request=request,
        name="order_form.html",
        context={
            "product": product,
            "qr_code_id": qr_code_id,
            "cross_sell_products": cross_sell_products,
        }
    )


# ─────────────────────────────────────────
# 주문 처리 API
# ─────────────────────────────────────────
@app.post("/shop/{qr_code_id}/order", response_class=HTMLResponse)
async def process_order(
    qr_code_id: str,
    product_id: int = Form(...),
    customer_name: str = Form(...),
    phone_number: str = Form(...),
    shipping_address: str = Form(...),
    delivery_note: str = Form(default=""),
):
    """
    주문 처리 → orders 테이블 INSERT →
    관리자 주문현황/정산 탭에 자동 반영
    """
    conn = get_db_connection()

    if _is_pg():
        with conn.cursor() as cur:
            cur.execute('SELECT id, price FROM products WHERE id = %s', (product_id,))
            product = cur.fetchone()
            if product:
                cur.execute('''
                    INSERT INTO orders (product_id, customer_name, phone_number, shipping_address, delivery_note, total_amount)
                    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                ''', (product[0], customer_name, phone_number, shipping_address, delivery_note, product[1]))
                order_id = cur.fetchone()[0]
    else:
        product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
        if product:
            cursor = conn.execute('''
                INSERT INTO orders (product_id, customer_name, phone_number, shipping_address, delivery_note, total_amount)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (product['id'], customer_name, phone_number, shipping_address, delivery_note, product['price']))
            order_id = cursor.lastrowid

    conn.commit()
    conn.close()

    if not product:
        return HTMLResponse(content="<h1>제품을 찾을 수 없습니다</h1>", status_code=404)

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
    import database
    database.init_db()
    print("[SERVER] AffiliStay Showroom Server is running on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
