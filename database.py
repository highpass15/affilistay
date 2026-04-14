import sqlite3
+import os
+import psycopg2
+from psycopg2.extras import RealDictCursor
+
+# DATABASE_URL 환경변수가 있으면 PostgreSQL(클라우드), 없으면 SQLite(로컬) 사용
+DATABASE_URL = os.environ.get('DATABASE_URL')
+DB_PATH = os.path.join(os.path.dirname(__file__), 'mvp_v2_ecommerce.db')
+
+def get_db_connection():
+    if DATABASE_URL:
+        conn = psycopg2.connect(DATABASE_URL)
+        return conn
+    else:
+        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
+        conn.row_factory = sqlite3.Row
+        return conn
+
+def init_db():
+    conn = get_db_connection()
+    cursor = conn.cursor()
+    
+    if DATABASE_URL:
+        # PostgreSQL
+        cursor.execute('''
+        CREATE TABLE IF NOT EXISTS hosts (
+            id SERIAL PRIMARY KEY,
+            username TEXT UNIQUE NOT NULL,
+            password TEXT NOT NULL,
+            name TEXT,
+            is_master BOOLEAN DEFAULT FALSE,
+            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
+        )
+        ''')
+        cursor.execute('''
+        CREATE TABLE IF NOT EXISTS products (
+            id SERIAL PRIMARY KEY,
+            brand_name TEXT NOT NULL,
+            product_name TEXT NOT NULL,
+            price INTEGER NOT NULL,
+            qr_code_id TEXT UNIQUE NOT NULL,
+            owner_id INTEGER REFERENCES hosts(id),
+            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
+        )
+        ''')
+        cursor.execute('''
+        CREATE TABLE IF NOT EXISTS orders (
+            id SERIAL PRIMARY KEY,
+            product_id INTEGER REFERENCES products(id),
+            customer_name TEXT NOT NULL,
+            phone_number TEXT NOT NULL,
+            shipping_address TEXT NOT NULL,
+            total_amount INTEGER NOT NULL,
+            payment_status TEXT DEFAULT 'PAID',
+            settlement_status TEXT DEFAULT 'PENDING',
+            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
+        )
+        ''')
+        
+        # 기존 테이블에 컬럼 추가 시도
+        try:
+            cursor.execute('ALTER TABLE products ADD COLUMN owner_id INTEGER REFERENCES hosts(id)')
+        except:
+            conn.rollback()
+            cursor = conn.cursor()
+    else:
+        # SQLite
+        cursor.execute('''
+        CREATE TABLE IF NOT EXISTS hosts (
+            id INTEGER PRIMARY KEY AUTOINCREMENT,
+            username TEXT UNIQUE NOT NULL,
+            password TEXT NOT NULL,
+            name TEXT,
+            is_master BOOLEAN DEFAULT FALSE,
+            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
+        )
+        ''')
+        cursor.execute('''
+        CREATE TABLE IF NOT EXISTS products (
+            id INTEGER PRIMARY KEY AUTOINCREMENT,
+            brand_name TEXT NOT NULL,
+            product_name TEXT NOT NULL,
+            price INTEGER NOT NULL,
+            qr_code_id TEXT UNIQUE NOT NULL,
+            owner_id INTEGER REFERENCES hosts(id),
+            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
+        )
+        ''')
+        cursor.execute('''
+        CREATE TABLE IF NOT EXISTS orders (
+            id INTEGER PRIMARY KEY AUTOINCREMENT,
+            product_id INTEGER REFERENCES products(id),
+            customer_name TEXT NOT NULL,
+            phone_number TEXT NOT NULL,
+            shipping_address TEXT NOT NULL,
+            total_amount INTEGER NOT NULL,
+            payment_status TEXT DEFAULT 'PAID',
+            settlement_status TEXT DEFAULT 'PENDING',
+            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
+        )
+        ''')
+        try:
+            cursor.execute('ALTER TABLE products ADD COLUMN owner_id INTEGER REFERENCES hosts(id)')
+        except:
+            pass
+    
+    # 초기 마스터 계정 생성 로직 (없을 경우)
+    try:
+        master_id = 'jwchoi1207'
+        master_pw = 'b3356choi!'
+        if DATABASE_URL:
+            cursor.execute('SELECT id FROM hosts WHERE username = %s', (master_id,))
+            if not cursor.fetchone():
+                cursor.execute(
+                    'INSERT INTO hosts (username, password, name, is_master) VALUES (%s, %s, %s, %s)',
+                    (master_id, master_pw, 'Master Admin', True)
+                )
+        else:
+            cursor.execute('SELECT id FROM hosts WHERE username = ?', (master_id,))
+            if not cursor.fetchone():
+                cursor.execute(
+                    'INSERT INTO hosts (username, password, name, is_master) VALUES (?, ?, ?, ?)',
+                    (master_id, master_pw, 'Master Admin', True)
+                )
+    except:
+        pass
+
+    conn.commit()
+    conn.close()
+
+if __name__ == "__main__":
+    init_db()
+
