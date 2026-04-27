import sqlite3
import os
import base64
import time
import psycopg2
from psycopg2.extras import RealDictCursor

# supabase 패키지가 없을 경우 안전하게 처리
try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    create_client = None
    SUPABASE_AVAILABLE = False

# --- 환경 변수 설정 ---
DATABASE_URL = os.environ.get('DATABASE_URL')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mvp_v2_ecommerce.db')
PUBLIC_CONTENT_META_KEY = "public_content_version"

# 수파베이스 클라이언트 초기화
supabase = None
if SUPABASE_AVAILABLE and create_client and SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        pass

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    else:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    if DATABASE_URL:
        # ── 기존 테이블 ──────────────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS hosts (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            role TEXT DEFAULT 'HOST',
            entity_type TEXT DEFAULT 'Individual',
            phone TEXT,
            email TEXT,
            address_road TEXT,
            address_detail TEXT,
            postal_code TEXT,
            phone_verified BOOLEAN DEFAULT FALSE,
            phone_verified_at TIMESTAMP,
            signup_path TEXT,
            desired_product_type TEXT,
            is_master BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            brand_name TEXT NOT NULL,
            product_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            original_price INTEGER,
            qr_code_id TEXT UNIQUE NOT NULL,
            owner_id INTEGER REFERENCES hosts(id),
            room_category TEXT DEFAULT 'living_room',
            product_category TEXT DEFAULT 'lifestyle',
            description TEXT,
            detailed_description TEXT,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_images (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            image_data TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_options (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            "values" TEXT NOT NULL -- 콤마로 구분된 값들
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            customer_name TEXT NOT NULL,
            rating INTEGER DEFAULT 5,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_inquiries (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
            customer_name TEXT NOT NULL,
            type TEXT NOT NULL, -- 배송/취소/환불/기타
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # ── 신규: 고객 테이블 (SNS 로그인 등) ────────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT, -- 일반 로그인용 (SNS 로그인의 경우 NULL일 수 있음)
            name TEXT,
            phone TEXT,
            default_address TEXT,
            provider TEXT DEFAULT 'email', -- email, kakao, naver, facebook
            provider_id TEXT, -- SNS 고유 ID
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id),
            customer_id INTEGER REFERENCES customers(id), -- 로그인한 경우
            customer_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            shipping_address TEXT NOT NULL,
            delivery_note TEXT,
            total_amount INTEGER NOT NULL,
            currency TEXT DEFAULT 'KRW',
            exchange_rate REAL DEFAULT 1.0,
            paypal_order_id TEXT,
            payment_method TEXT DEFAULT 'paypal', -- paypal, kakaopay, tosspay, naverpay, card, vbank
            imp_uid TEXT, -- 포트원 결제 고유번호
            payment_status TEXT DEFAULT 'PENDING',
            settlement_status TEXT DEFAULT 'PENDING',
            shipping_status TEXT DEFAULT 'PREPARING',
            fcm_token TEXT,
            selected_options TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # ── 신규 테이블 ──────────────────────────────
        # 호스트 숙소 프로필 (위치, 사진 2장)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS host_venues (
            id SERIAL PRIMARY KEY,
            host_id INTEGER REFERENCES hosts(id) UNIQUE,
            location TEXT,
            description TEXT,
            image1 TEXT,
            image2 TEXT,
            image3 TEXT,
            image4 TEXT,
            image5 TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # 입점업체가 등록한 입점 가능 제품
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS brand_items (
            id SERIAL PRIMARY KEY,
            brand_id INTEGER REFERENCES hosts(id),
            item_name TEXT NOT NULL,
            description TEXT,
            stock_qty INTEGER DEFAULT 0,
            image TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sponsorships (
            id SERIAL PRIMARY KEY,
            brand_id INTEGER REFERENCES hosts(id),
            host_id INTEGER REFERENCES hosts(id),
            brand_item_id INTEGER REFERENCES brand_items(id),
            qty INTEGER DEFAULT 1,
            message TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # 홈페이지 홈페이지 파트너 신청 문의
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS inquiries (
            id SERIAL PRIMARY KEY,
            inquiry_type TEXT NOT NULL,
            name TEXT NOT NULL,
            contact TEXT NOT NULL,
            email TEXT NOT NULL,
            company_name TEXT,
            job_title TEXT,
            location TEXT,
            platform TEXT,
            category TEXT,
            message TEXT,
            status TEXT DEFAULT 'UNREAD',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # 고객 방문 및 체류 시간 기록용
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS page_views (
            id SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            product_id INTEGER,
            host_id INTEGER,
            page_url TEXT,
            enter_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            duration_seconds INTEGER DEFAULT 0
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS site_meta (
            meta_key TEXT PRIMARY KEY,
            meta_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
    else:

        # SQLite
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS hosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE, password TEXT, name TEXT,
            role TEXT DEFAULT 'HOST', entity_type TEXT DEFAULT 'Individual',
            phone TEXT, email TEXT, address_road TEXT, address_detail TEXT,
            postal_code TEXT, phone_verified BOOLEAN DEFAULT FALSE, phone_verified_at TIMESTAMP,
            signup_path TEXT, desired_product_type TEXT,
            is_master BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_name TEXT, product_name TEXT, 
            price INTEGER, original_price INTEGER,
            qr_code_id TEXT UNIQUE, owner_id INTEGER,
            room_category TEXT DEFAULT 'living_room',
            product_category TEXT DEFAULT 'lifestyle',
            description TEXT, detailed_description TEXT, image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            image_data TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            name TEXT NOT NULL,
            "values" TEXT NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            customer_name TEXT NOT NULL,
            rating INTEGER DEFAULT 5,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            customer_name TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT,
            name TEXT,
            phone TEXT,
            default_address TEXT,
            provider TEXT DEFAULT 'email',
            provider_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            customer_id INTEGER,
            customer_name TEXT, phone_number TEXT,
            shipping_address TEXT, delivery_note TEXT, total_amount INTEGER,
            currency TEXT DEFAULT 'KRW', exchange_rate REAL DEFAULT 1.0,
            paypal_order_id TEXT,
            payment_method TEXT DEFAULT 'paypal',
            imp_uid TEXT,
            payment_status TEXT DEFAULT 'PENDING',
            settlement_status TEXT DEFAULT 'PENDING',
            shipping_status TEXT DEFAULT 'PREPARING',
            fcm_token TEXT,
            selected_options TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS host_venues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host_id INTEGER UNIQUE, location TEXT, description TEXT,
            image1 TEXT, image2 TEXT, image3 TEXT, image4 TEXT, image5 TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS brand_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id INTEGER, item_name TEXT NOT NULL,
            description TEXT, stock_qty INTEGER DEFAULT 0, image TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sponsorships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id INTEGER, host_id INTEGER, brand_item_id INTEGER,
            qty INTEGER DEFAULT 1, message TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inquiry_type TEXT NOT NULL,
            name TEXT NOT NULL,
            contact TEXT NOT NULL,
            email TEXT NOT NULL,
            company_name TEXT,
            job_title TEXT,
            location TEXT,
            platform TEXT,
            category TEXT,
            message TEXT,
            status TEXT DEFAULT 'UNREAD',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS page_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            product_id INTEGER,
            host_id INTEGER,
            page_url TEXT,
            enter_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            duration_seconds INTEGER DEFAULT 0
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS site_meta (
            meta_key TEXT PRIMARY KEY,
            meta_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

    # 마스터 계정 초기화

    master_id = 'jwchoi1207'
    master_pw = 'b3356choi!'
    if DATABASE_URL:
        cursor.execute('SELECT id FROM hosts WHERE username = %s', (master_id,))
    else:
        cursor.execute('SELECT id FROM hosts WHERE username = ?', (master_id,))
    if not cursor.fetchone():
        if DATABASE_URL:
            cursor.execute(
                'INSERT INTO hosts (username, password, name, is_master, role) VALUES (%s, %s, %s, %s, %s)',
                (master_id, master_pw, 'Master Admin', True, 'HOST')
            )
        else:
            cursor.execute(
                'INSERT INTO hosts (username, password, name, is_master, role) VALUES (?, ?, ?, ?, ?)',
                (master_id, master_pw, 'Master Admin', True, 'HOST')
            )

    # ── 마이그레이션: 기존 테이블에 누락 컬럼 추가 ──
    if DATABASE_URL:
        migrations = [
            "ALTER TABLE hosts ADD COLUMN IF NOT EXISTS address_road TEXT",
            "ALTER TABLE hosts ADD COLUMN IF NOT EXISTS address_detail TEXT",
            "ALTER TABLE hosts ADD COLUMN IF NOT EXISTS postal_code TEXT",
            "ALTER TABLE hosts ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE",
            "ALTER TABLE hosts ADD COLUMN IF NOT EXISTS phone_verified_at TIMESTAMP",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES hosts(id)",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS room_category TEXT DEFAULT 'living_room'",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS product_category TEXT DEFAULT 'lifestyle'",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS original_price INTEGER",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS detailed_description TEXT",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url TEXT",
            "CREATE TABLE IF NOT EXISTS product_images (id SERIAL PRIMARY KEY, product_id INTEGER, image_data TEXT, sort_order INTEGER DEFAULT 0)",
            'CREATE TABLE IF NOT EXISTS product_options (id SERIAL PRIMARY KEY, product_id INTEGER, name TEXT, "values" TEXT)',
            "ALTER TABLE host_venues ADD COLUMN IF NOT EXISTS image3 TEXT",
            "ALTER TABLE host_venues ADD COLUMN IF NOT EXISTS image4 TEXT",
            "ALTER TABLE host_venues ADD COLUMN IF NOT EXISTS image5 TEXT",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'KRW'",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS exchange_rate REAL DEFAULT 1.0",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS paypal_order_id TEXT",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_status TEXT DEFAULT 'PREPARING'",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS fcm_token TEXT",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS selected_options TEXT",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_note TEXT",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS session_id TEXT",
            "CREATE TABLE IF NOT EXISTS reviews (id SERIAL PRIMARY KEY, product_id INTEGER, customer_name TEXT, rating INTEGER, comment TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE IF NOT EXISTS product_inquiries (id SERIAL PRIMARY KEY, product_id INTEGER, customer_name TEXT, type TEXT, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE IF NOT EXISTS site_meta (meta_key TEXT PRIMARY KEY, meta_value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        ]
        for sql in migrations:
            try:
                cursor.execute(sql)
            except Exception:
                pass
    else:
        sqlite_migrations = [
            "ALTER TABLE hosts ADD COLUMN address_road TEXT",
            "ALTER TABLE hosts ADD COLUMN address_detail TEXT",
            "ALTER TABLE hosts ADD COLUMN postal_code TEXT",
            "ALTER TABLE hosts ADD COLUMN phone_verified BOOLEAN DEFAULT FALSE",
            "ALTER TABLE hosts ADD COLUMN phone_verified_at TIMESTAMP",
            "ALTER TABLE orders ADD COLUMN session_id TEXT",
            "ALTER TABLE products ADD COLUMN owner_id INTEGER",
            "ALTER TABLE products ADD COLUMN room_category TEXT DEFAULT 'living_room'",
            "ALTER TABLE products ADD COLUMN product_category TEXT DEFAULT 'lifestyle'",
            "ALTER TABLE products ADD COLUMN original_price INTEGER",
            "ALTER TABLE products ADD COLUMN description TEXT",
            "ALTER TABLE products ADD COLUMN detailed_description TEXT",
            "ALTER TABLE products ADD COLUMN image_url TEXT",
            "ALTER TABLE host_venues ADD COLUMN image3 TEXT",
            "ALTER TABLE host_venues ADD COLUMN image4 TEXT",
            "ALTER TABLE host_venues ADD COLUMN image5 TEXT",
            "CREATE TABLE IF NOT EXISTS product_images (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, image_data TEXT NOT NULL, sort_order INTEGER DEFAULT 0)",
            'CREATE TABLE IF NOT EXISTS product_options (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, name TEXT NOT NULL, "values" TEXT NOT NULL)',
            "CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, customer_name TEXT NOT NULL, rating INTEGER DEFAULT 5, comment TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE IF NOT EXISTS product_inquiries (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, customer_name TEXT NOT NULL, type TEXT NOT NULL, content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE IF NOT EXISTS site_meta (meta_key TEXT PRIMARY KEY, meta_value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        ]
        for sql in sqlite_migrations:
            try:
                cursor.execute(sql)
            except Exception:
                pass

    conn.commit()
    conn.close()


# ── 이미지 변환 헬퍼 ─────────────────────────────────
def file_to_base64(uploaded_file) -> str:
    """Streamlit UploadedFile → base64 문자열"""
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    data = uploaded_file.read()
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    return base64.b64encode(data).decode('utf-8')

def base64_to_bytes(b64_str: str) -> bytes:
    """base64 문자열 → bytes (st.image에 직접 사용)"""
    return base64.b64decode(b64_str)


def fetch_product_images(conn, product_id):
    cursor = conn.cursor()
    query = (
        "SELECT image_data FROM product_images WHERE product_id=%s ORDER BY sort_order, id"
        if DATABASE_URL else
        "SELECT image_data FROM product_images WHERE product_id=? ORDER BY sort_order, id"
    )
    cursor.execute(query, (product_id,))
    return [row[0] for row in cursor.fetchall()]


def fetch_product_options(conn, product_id):
    cursor = conn.cursor()
    query = (
        'SELECT name, "values" FROM product_options WHERE product_id=%s ORDER BY id'
        if DATABASE_URL else
        'SELECT name, "values" FROM product_options WHERE product_id=? ORDER BY id'
    )
    cursor.execute(query, (product_id,))
    return cursor.fetchall()


def _new_public_version():
    return str(time.time_ns())


def _ensure_site_meta_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS site_meta (
            meta_key TEXT PRIMARY KEY,
            meta_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _seed_public_content_version(cursor):
    _ensure_site_meta_table(cursor)
    initial_version = _new_public_version()
    if DATABASE_URL:
        cursor.execute(
            """
            INSERT INTO site_meta (meta_key, meta_value, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (meta_key) DO NOTHING
            """,
            (PUBLIC_CONTENT_META_KEY, initial_version),
        )
    else:
        cursor.execute(
            """
            INSERT OR IGNORE INTO site_meta (meta_key, meta_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (PUBLIC_CONTENT_META_KEY, initial_version),
        )


def bump_public_content_version(conn):
    cursor = conn.cursor()
    _seed_public_content_version(cursor)
    next_version = _new_public_version()
    if DATABASE_URL:
        cursor.execute(
            "UPDATE site_meta SET meta_value=%s, updated_at=CURRENT_TIMESTAMP WHERE meta_key=%s",
            (next_version, PUBLIC_CONTENT_META_KEY),
        )
    else:
        cursor.execute(
            "UPDATE site_meta SET meta_value=?, updated_at=CURRENT_TIMESTAMP WHERE meta_key=?",
            (next_version, PUBLIC_CONTENT_META_KEY),
        )
    return next_version


def get_public_content_version():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        _seed_public_content_version(cursor)
        query = (
            "SELECT meta_value FROM site_meta WHERE meta_key=%s"
            if DATABASE_URL else
            "SELECT meta_value FROM site_meta WHERE meta_key=?"
        )
        cursor.execute(query, (PUBLIC_CONTENT_META_KEY,))
        row = cursor.fetchone()
        conn.commit()
        if not row:
            return _new_public_version()
        if isinstance(row, sqlite3.Row):
            return row["meta_value"]
        if isinstance(row, dict):
            return row.get("meta_value")
        return row[0]
    finally:
        conn.close()


# ── 수파베이스 동기화 ────────────────────────────────
def sync_order_to_supabase(order_id):
    """주문 정산 데이터를 수파베이스에 미러링합니다."""
    if not supabase:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if DATABASE_URL:
            cursor.execute("""
                SELECT o.id, o.total_amount, o.settlement_status, p.owner_id
                FROM orders o JOIN products p ON o.product_id = p.id
                WHERE o.id = %s
            """, (order_id,))
        else:
            cursor.execute("""
                SELECT o.id, o.total_amount, o.settlement_status, p.owner_id
                FROM orders o JOIN products p ON o.product_id = p.id
                WHERE o.id = ?
            """, (order_id,))
        row = cursor.fetchone()
        if row:
            total = row[1]
            data = {
                "order_id": row[0],
                "amount": total,
                "platform_revenue": int(total * 0.20),
                "host_revenue": int(total * 0.10),
                "host_id": row[3],
                "status": row[2],
            }
            supabase.table("settlements").upsert(data, on_conflict="order_id").execute()
    except Exception as e:
        print(f"Supabase Sync Error: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("DB 초기화 완료")
