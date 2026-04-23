import sqlite3
import os
import base64
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
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id),
            customer_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            shipping_address TEXT NOT NULL,
            delivery_note TEXT,
            total_amount INTEGER NOT NULL,
            payment_status TEXT DEFAULT 'PAID',
            settlement_status TEXT DEFAULT 'PENDING',
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
    else:
        # SQLite
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS hosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE, password TEXT, name TEXT,
            role TEXT DEFAULT 'HOST', entity_type TEXT DEFAULT 'Individual',
            phone TEXT, email TEXT, signup_path TEXT, desired_product_type TEXT,
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
            description TEXT, image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER, customer_name TEXT, phone_number TEXT,
            shipping_address TEXT, delivery_note TEXT, total_amount INTEGER,
            payment_status TEXT DEFAULT 'PAID',
            settlement_status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS host_venues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host_id INTEGER UNIQUE, location TEXT, description TEXT,
            image1 TEXT, image2 TEXT,
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
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES hosts(id)",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS room_category TEXT DEFAULT 'living_room'",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url TEXT",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS original_price INTEGER",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS product_category TEXT DEFAULT 'lifestyle'",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS settlement_status TEXT DEFAULT 'PENDING'",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_note TEXT",
        ]
        for sql in migrations:
            try:
                cursor.execute(sql)
            except Exception:
                pass

    conn.commit()
    conn.close()


# ── 이미지 변환 헬퍼 ─────────────────────────────────
def file_to_base64(uploaded_file) -> str:
    """Streamlit UploadedFile → base64 문자열"""
    return base64.b64encode(uploaded_file.read()).decode('utf-8')

def base64_to_bytes(b64_str: str) -> bytes:
    """base64 문자열 → bytes (st.image에 직접 사용)"""
    return base64.b64decode(b64_str)


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
