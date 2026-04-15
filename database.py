import sqlite3
import os
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

# 수파베이스 클라이언트 초기화 (Client 타입 힌트 없이)
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
            qr_code_id TEXT UNIQUE NOT NULL,
            owner_id INTEGER REFERENCES hosts(id),
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
            total_amount INTEGER NOT NULL,
            payment_status TEXT DEFAULT 'PAID',
            settlement_status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS hosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE, password TEXT, name TEXT,
            role TEXT, entity_type TEXT, phone TEXT, email TEXT,
            signup_path TEXT, desired_product_type TEXT,
            is_master BOOLEAN, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_name TEXT, product_name TEXT, price INTEGER,
            qr_code_id TEXT UNIQUE, owner_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER, customer_name TEXT,
            phone_number TEXT, shipping_address TEXT,
            total_amount INTEGER, payment_status TEXT,
            settlement_status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

    # 마스터 계정 초기화 확인
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

    conn.commit()
    conn.close()

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
