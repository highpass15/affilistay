import sqlite3
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# DATABASE_URL 환경변수가 있으면 PostgreSQL(클라우드), 없으면 SQLite(로컬) 사용
DATABASE_URL = os.environ.get('DATABASE_URL')
DB_PATH = os.path.join(os.path.dirname(__file__), 'mvp_v2_ecommerce.db')

def get_db_connection():
    if DATABASE_URL:
        # 클라우드 환경 (PostgreSQL)
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        # 로컬 환경 (SQLite)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # PostgreSQL과 SQLite 공용 호환 SQL
    # SQLite는 SERIAL 대신 AUTOINCREMENT 사용하므로 분기가 필요할 수 있음
    if DATABASE_URL:
        # PostgreSQL 문법
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            brand_name TEXT NOT NULL,
            product_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            qr_code_id TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            product_id INTEGER,
            customer_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            shipping_address TEXT NOT NULL,
            total_amount INTEGER NOT NULL,
            payment_status TEXT DEFAULT 'PAID',
            settlement_status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
        ''')
    else:
        # SQLite 문법
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_name TEXT NOT NULL,
            product_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            qr_code_id TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            customer_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            shipping_address TEXT NOT NULL,
            total_amount INTEGER NOT NULL,
            payment_status TEXT DEFAULT 'PAID',
            settlement_status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
        ''')
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Cloud-ready Database Initialized.")
