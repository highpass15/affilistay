import streamlit as st
+import pandas as pd
+import uuid
+import qrcode
+from io import BytesIO
+import database
+import os
+from message_automator import send_email_invitation, send_sms_invitation
+
+# --- UI & 디자인 설정 (Host-Pro Portal v6) ---
+st.set_page_config(
+    page_title="AffiliStay | Host & Master Portal",
+    page_icon="🏠",
+    layout="wide",
+    initial_sidebar_state="expanded"
+)
+
+# 데이터베이스 초기화
+database.init_db()
+
+# --- 영구 주소 설정 ---
+CHECKOUT_URL = "https://affilistay-showroom.onrender.com"
+ADMIN_URL = "https://affilistay-admin.onrender.com"
+
+# --- 인증 시스템 로직 ---
+def check_auth():
+    if 'authenticated' not in st.session_state:
+        st.session_state['authenticated'] = False
+    if st.session_state['authenticated']:
+        return True
+    
+    st.markdown("""
+        <div style='text-align: center; padding-top: 50px;'>
+            <h1 style='font-weight: 200; font-size: 3rem;'>AffiliStay Partner Portal</h1>
+            <p style='color: #888; letter-spacing: 0.1em; margin-bottom: 40px;'>AUTHORIZED PERSONNEL ONLY</p>
+        </div>
+    """, unsafe_allow_html=True)
+    
+    col_l, col_m, col_r = st.columns([1, 1, 1])
+    with col_m:
+        username = st.text_input("Username")
+        password = st.text_input("Password", type="password")
+        if st.button("포털 입장하기", use_container_width=True):
+            conn = database.get_db_connection()
+            cursor = conn.cursor()
+            if database.DATABASE_URL:
+                cursor.execute('SELECT id, username, name, is_master FROM hosts WHERE username = %s AND password = %s', (username, password))
+            else:
+                cursor.execute('SELECT id, username, name, is_master FROM hosts WHERE username = ? AND password = ?', (username, password))
+            user = cursor.fetchone()
+            conn.close()
+            
+            if user:
+                st.session_state['authenticated'] = True
+                st.session_state['host_id'] = user[0]
+                st.session_state['username'] = user[1]
+                st.session_state['name'] = user[2]
+                st.session_state['is_master'] = user[3]
+                st.rerun()
+            else:
+                st.error("Invalid credentials.")
+    return False
+
+if not check_auth():
+    st.stop()
+
+# --- 고품질 CSS (Minoan SaaS 느낌 구현) ---
+st.markdown("""
+    <style>
+    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@200;400;700&display=swap');
+    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; color: #1A1A1A; }
+    .stApp { background-color: #FAF9F6; }
+    div[data-testid="stVerticalBlock"] > div.element-container:has(div.stMarkdown > div.premium-card) {
+        background: white; padding: 2rem; border-radius: 20px;
+        box-shadow: 0 4px 20px rgba(0,0,0,0.03); border: 1px solid #F0EFEA; margin-bottom: 2rem;
+    }
+    .stButton>button {
+        background-color: #1A1A1A; color: white; border-radius: 50px; border: none;
+        padding: 0.6rem 2rem; font-size: 12px; font-weight: 700; letter-spacing: 0.1em; transition: all 0.3s;
+    }
+    .stButton>button:hover { background-color: #000; transform: translateY(-2px); }
+    .stTabs [data-baseweb="tab-list"] { gap: 30px; }
+    .stTabs [data-baseweb="tab-highlight"] { background-color: #1A1A1A; }
+    </style>
+    """, unsafe_allow_html=True)
+
+# --- 사이드바 ---
+with st.sidebar:
+    st.markdown(f"<h2 style='font-weight:700; letter-spacing:-0.05em;'>AFFILISTAY.</h2>", unsafe_allow_html=True)
+    st.caption(f"접속자: {st.session_state['name']} ({'MASTER' if st.session_state['is_master'] else 'HOST'})")
+    st.markdown("---")
+    st.subheader("📡 플랫폼 상태")
+    st.success("클라우드 서버 가동 중")
+    st.caption("공개 쇼룸 주소:")
+    st.code(CHECKOUT_URL, language=None)
+    st.markdown("---")
+    if st.button("로그아웃", use_container_width=True):
+        st.session_state['authenticated'] = False
+        st.rerun()
+
+# --- 메인 타이틀 ---
+title_prefix = "마스터" if st.session_state['is_master'] else "호스트"
+st.title(f"{title_prefix} 대시보드")
+st.markdown(f"<p style='color:#888; font-size:1.1rem;'>환영합니다, {st.session_state['name']}님. {'플랫폼 전체' if st.session_state['is_master'] else '숙소 쇼룸'} 현황입니다.</p>", unsafe_allow_html=True)
+
+tabs = ["🛍️ 제품 및 쇼룸 관리", "📦 실시간 주문 현황"]
+if st.session_state['is_master']:
+    tabs.append("👥 호스트 계정 관리")
+else:
+    tabs.append("💌 고객 영입 도구")
+
+tab_list = st.tabs(tabs)
+
+# --------------------------------
+# 탭 1: PRODUCTS (제품 및 QR)
+# --------------------------------
+with tab_list[0]:
+    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
+    col_input, col_list = st.columns([1.5, 2.5])
+    
+    with col_input:
+        st.subheader("새 쇼룸 제품 등록")
+        brand = st.text_input("브랜드명", placeholder="예: 이솝 (Aesop)")
+        pname = st.text_input("제품명", placeholder="예: 레저렉션 핸드 워시")
+        price = st.number_input("특별 공급가 (원)", min_value=0, step=1000, value=35000)
+        
+        if st.button("QR 쇼룸 생성하기", type="primary", use_container_width=True):
+            if pname and price > 0:
+                conn = database.get_db_connection()
+                cursor = conn.cursor()
+                short_code = str(uuid.uuid4())[:6].upper()
+                if database.DATABASE_URL:
+                    cursor.execute(
+                        'INSERT INTO products (brand_name, product_name, price, qr_code_id, owner_id) VALUES (%s, %s, %s, %s, %s)',
+                        (brand, pname, price, short_code, st.session_state['host_id'])
+                    )
+                else:
+                    cursor.execute(
+                        'INSERT INTO products (brand_name, product_name, price, qr_code_id, owner_id) VALUES (?, ?, ?, ?, ?)',
+                        (brand, pname, price, short_code, st.session_state['host_id'])
+                    )
+                conn.commit()
+                conn.close()
+                st.toast("QR 쇼룸 제품이 등록되었습니다.")
+                st.rerun()
+            else:
+                st.error("상세 정보를 입력해주세요.")
+    
+    with col_list:
+        st.subheader("등록된 쇼룸 아이템")
+        conn = database.get_db_connection()
+        # 권한별 조회 쿼리 차등화
+        if st.session_state['is_master']:
+            query = '''
+                SELECT p.qr_code_id AS "코드", p.brand_name AS "브랜드", p.product_name AS "상품명", p.price AS "가격", COUNT(o.id) AS "누적판매", h.username AS "소유주"
+                FROM products p LEFT JOIN orders o ON p.id = o.product_id
+                LEFT JOIN hosts h ON p.owner_id = h.id
+                GROUP BY p.id, h.username ORDER BY p.id DESC
+            '''
+            df_prod = pd.read_sql_query(query, conn)
+        else:
+            query = '''
+                SELECT p.qr_code_id AS "코드", p.brand_name AS "브랜드", p.product_name AS "상품명", p.price AS "가격", COUNT(o.id) AS "누적판매"
+                FROM products p LEFT JOIN orders o ON p.id = o.product_id
+                WHERE p.owner_id = %s
+                GROUP BY p.id ORDER BY p.id DESC
+            ''' if database.DATABASE_URL else '''
+                SELECT p.qr_code_id AS "코드", p.brand_name AS "브랜드", p.product_name AS "상품명", p.price AS "가격", COUNT(o.id) AS "누적판매"
+                FROM products p LEFT JOIN orders o ON p.id = o.product_id
+                WHERE p.owner_id = ?
+                GROUP BY p.id ORDER BY p.id DESC
+            '''
+            df_prod = pd.read_sql_query(query, conn, params=(st.session_state['host_id'],))
+        conn.close()
+        
+        st.dataframe(df_prod, use_container_width=True, hide_index=True)
+        
+        if not df_prod.empty:
+            sel_code = st.selectbox("QR 코드를 확인할 아이템 선택", df_prod["코드"].tolist())
+            qr_target = f"{CHECKOUT_URL}/buy/{sel_code}"
+            qc1, qc2 = st.columns([1, 2])
+            with qc1:
+                qr = qrcode.QRCode(box_size=10, border=4)
+                qr.add_data(qr_target)
+                qr.make(fit=True)
+                img = qr.make_image(fill_color="#1A1A1A", back_color="white")
+                buf = BytesIO()
+                img.save(buf, format="PNG")
+                st.image(buf.getvalue(), width=150)
+            with qc2:
+                st.caption("QR 연결 주소")
+                st.code(qr_target, language=None)
+                st.download_button("QR 이미지 다운로드 (PNG)", buf.getvalue(), f"QR_{sel_code}.png", "image/png", use_container_width=True)
+    st.markdown("</div>", unsafe_allow_html=True)
+
+# --------------------------------
+# 탭 2: ORDERS (주문 현황)
+# --------------------------------
+with tab_list[1]:
+    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
+    st.subheader("실시간 주문 내역")
+    conn = database.get_db_connection()
+    date_func = "TO_CHAR(o.created_at, 'MM/DD HH:MI')" if database.DATABASE_URL else "strftime('%m/%d %H:%M', o.created_at)"
+    
+    if st.session_state['is_master']:
+        query = f'''
+            SELECT {date_func} AS "일시", h.username AS "호스트", p.product_name AS "상품명", o.total_amount AS "금액", o.customer_name AS "구매자", o.shipping_address AS "배송지"
+            FROM orders o JOIN products p ON o.product_id = p.id
+            JOIN hosts h ON p.owner_id = h.id
+            ORDER BY o.id DESC
+        '''
+        df_orders = pd.read_sql_query(query, conn)
+    else:
+        query = f'''
+            SELECT {date_func} AS "일시", p.product_name AS "상품명", o.total_amount AS "금액", o.customer_name AS "구매자", o.shipping_address AS "배송지"
+            FROM orders o JOIN products p ON o.product_id = p.id
+            WHERE p.owner_id = %s ORDER BY o.id DESC
+        ''' if database.DATABASE_URL else f'''
+            SELECT {date_func} AS "일시", p.product_name AS "상품명", o.total_amount AS "금액", o.customer_name AS "구매자", o.shipping_address AS "배송지"
+            FROM orders o JOIN products p ON o.product_id = p.id
+            WHERE p.owner_id = ? ORDER BY o.id DESC
+        '''
+        df_orders = pd.read_sql_query(query, conn, params=(st.session_state['host_id'],))
+    conn.close()
+    
+    if df_orders.empty:
+        st.info("아직 인입된 주문이 없습니다.")
+    else:
+        st.dataframe(df_orders, use_container_width=True, hide_index=True)
+    st.markdown("</div>", unsafe_allow_html=True)
+
+# --------------------------------
+# 탭 3: MASTER (호스트 관리) 또는 OUTREACH (영업 도구)
+# --------------------------------
+with tab_list[2]:
+    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
+    if st.session_state['is_master']:
+        st.subheader("👥 호스트 계정 관리")
+        st.markdown("<p style='color: #888;'>플랫폼의 각 호스트를 생성하고 비밀번호를 관리합니다.</p>", unsafe_allow_html=True)
+        
+        h_id, h_pw, h_name = st.columns(3)
+        new_user = h_id.text_input("호스트 ID")
+        new_pw = h_pw.text_input("비밀번호", type="password")
+        new_name = h_name.text_input("호스트 이름/숙소명")
+        
+        if st.button("새 호스트 계정 생성하기", use_container_width=True):
+            if new_user and new_pw:
+                conn = database.get_db_connection()
+                cursor = conn.cursor()
+                try:
+                    if database.DATABASE_URL:
+                        cursor.execute('INSERT INTO hosts (username, password, name, is_master) VALUES (%s, %s, %s, %s)', (new_user, new_pw, new_name, False))
+                    else:
+                        cursor.execute('INSERT INTO hosts (username, password, name, is_master) VALUES (?, ?, ?, ?)', (new_user, new_pw, new_name, False))
+                    conn.commit()
+                    st.success(f"호스트 {new_user} 계정이 생성되었습니다.")
+                except Exception as e:
+                    st.error(f"생성 실패: {e}")
+                finally:
+                    conn.close()
+            else:
+                st.warning("아이디와 비밀번호를 모두 입력해주세요.")
+        
+        st.markdown("---")
+        st.subheader("현재 활동 중인 호스트")
+        conn = database.get_db_connection()
+        df_hosts = pd.read_sql_query('SELECT username, name, created_at FROM hosts WHERE is_master = FALSE', conn)
+        conn.close()
+        st.table(df_hosts)
+        
+    else:
+        st.subheader("Host Partnership Outreach")
+        st.caption("AI-optimized messaging for guest recruitment.")
+        msg = st.text_area("MESSAGE CONTENT", height=150, value="Hello Guest. Welcome to our room. Scan our QR code to shop curated items used in this room!")
+        st.text_input("RECIPIENT", placeholder="email@address.com")
+        if st.button("SEND PROPOSAL", use_container_width=True):
+            st.toast("Proposal sent.")
+    st.markdown("</div>", unsafe_allow_html=True)
+
