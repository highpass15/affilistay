import database
import os
import psycopg2

def migrate():
    print("Migration starting...")
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    # 1. hosts 테이블 생성
    if database.DATABASE_URL:
        # PostgreSQL
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS hosts (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            is_master BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
    else:
        # SQLite
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS hosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            is_master BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
    
    # 2. products 테이블에 owner_id 컬럼 추가
    try:
        cursor.execute('ALTER TABLE products ADD COLUMN owner_id INTEGER REFERENCES hosts(id)')
        print("Column 'owner_id' added to 'products' table.")
    except Exception as e:
        print(f"Skipping ADD COLUMN owner_id: {e}")
        conn.rollback()
        cursor = conn.cursor()

    # 3. 초기 마스터 계정 생성 (사용자 요청: admin / master1234 예시)
    try:
        # PostgreSQL과 SQLite 공용 INSERT IGNORE 패턴 대신 SELECT 후 체크
        cursor.execute('SELECT id FROM hosts WHERE username = %s' if database.DATABASE_URL else 'SELECT id FROM hosts WHERE username = ?', ('admin',))
        if not cursor.fetchone():
            if database.DATABASE_URL:
                cursor.execute(
                    'INSERT INTO hosts (username, password, name, is_master) VALUES (%s, %s, %s, %s) RETURNING id',
                    ('admin', 'master1234', 'Master Admin', True)
                )
            else:
                cursor.execute(
                    'INSERT INTO hosts (username, password, name, is_master) VALUES (?, ?, ?, ?)',
                    ('admin', 'master1234', 'Master Admin', True)
                )
            print("Master account 'admin' created.")
        else:
            print("Master account 'admin' already exists.")
    except Exception as e:
        print(f"Error creating master account: {e}")

    # 4. 기존 제품들을 마스터 계정 소유로 업데이트
    cursor.execute('SELECT id FROM hosts WHERE is_master = TRUE LIMIT 1')
    master = cursor.fetchone()
    if master:
        master_id = master[0]
        if database.DATABASE_URL:
            cursor.execute('UPDATE products SET owner_id = %s WHERE owner_id IS NULL', (master_id,))
        else:
            cursor.execute('UPDATE products SET owner_id = ? WHERE owner_id IS NULL', (master_id,))
        print(f"Existing products associated with master (ID: {master_id}).")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == '__main__':
    migrate()
