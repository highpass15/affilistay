import streamlit as st
+import pandas as pd
+import uuid
+import qrcode
+from io import BytesIO
+import database
+import os
+import time
+
+# --- UI & 디자인 설정 ---
+st.set_page_config(
+    page_title="AffiliStay | Admin Portal",
+    page_icon="💰",
+    layout="wide",
+    initial_sidebar_state="expanded"
+)
+
+# 데이터베이스 초기화
+database.init_db()
+
+# --- 영구 주소 설정 ---
+CHECKOUT_URL = "https://affilistay-showroom.onrender.com"
+
+# --- 인증 시스템 ---
+def check_auth():
+    if 'authenticated' not in st.session_state:
+        st.session_state['authenticated'] = False
+    if 'auth_mode' not in st.session_state:
+        st.session_state['auth_mode'] = 'login'
+        
+    if st.session_state['authenticated']:
+        return True
+
+    col_l, col_m, col_r = st.columns([1, 1.2, 1])
+    with col_m:
+        st.markdown("<h2 style='text-align: center;'>AffiliStay Portal</h2>", unsafe_allow_html=True)
+        if st.session_state['auth_mode'] == 'login':
+            u = st.text_input("Username")
+            p = st.text_input("Password", type="password")
+            if st.button("Login", use_container_width=True, type="primary"):
+                conn = database.get_db_connection()
+                cursor = conn.cursor()
+                if database.DATABASE_URL:
+                    cursor.execute('SELECT id, username, name, is_master, role FROM hosts WHERE username = %s AND password = %s', (u, p))
+                else:
+                    cursor.execute('SELECT id, username, name, is_master, role FROM hosts WHERE username = ? AND password = ?', (u, p))
+                user = cursor.fetchone()
+                conn.close()
+                if user:
+                    st.session_state.update({"authenticated": True, "host_id": user[0], "username": user[1], "name": user[2], "is_master": user[3], "role": user[4]})
+                    st.rerun()
+                else:
+                    st.error("Invalid credentials.")
+            if st.button("Need an account? Sign up", use_container_width=True):
+                st.session_state['auth_mode'] = 'signup'
+                st.rerun()
+        else:
+            # 회원가입 로직
+            st.markdown("#### 회원가입")
+            role_choice = st.radio("유형", ["HOST", "GUEST"], horizontal=True)
+            
+            full_name = st.text_input("이름(법인명)")
+            phone = st.text_input("핸드폰 연락처")
+            email = st.text_input("이메일 주소")
+            signup_path = st.selectbox("가입 경로", ["네이버광고", "지인소개", "인스타", "메일광고", "기타"])
+            
+            new_username = st.text_input("사용할 아이디")
+            new_password = st.text_input("비밀번호", type="password")
+            
+            if st.button("가입 신청", use_container_width=True, type="primary"):
+                conn = database.get_db_connection()
+                cursor = conn.cursor()
+                try:
+                    if database.DATABASE_URL:
+                        cursor.execute(
+                            'INSERT INTO hosts (username, password, name, phone, email, signup_path, role, is_master) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
+                            (new_username, new_password, full_name, phone, email, signup_path, role_choice, False)
+                        )
+                    else:
+                        cursor.execute(
+                            'INSERT INTO hosts (username, password, name, phone, email, signup_path, role, is_master) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
+                            (new_username, new_password, full_name, phone, email, signup_path, role_choice, False)
+                        )
+                    conn.commit()
+                    st.success("가입 완료! 로그인 해주세요.")
+                    st.session_state['auth_mode'] = 'login'
+                    st.rerun()
+                except:
+                    st.error("아이디 중복 또는 가입 오류")
+                finally:
+                    conn.close()
+            
+            if st.button("Back to Login", use_container_width=True):
+                st.session_state['auth_mode'] = 'login'
+                st.rerun()
+    return False
+
+if not check_auth():
+    st.stop()
+
+# --- 메인 대시보드 ---
+with st.sidebar:
+    st.title("AFFILISTAY.")
+    st.caption(f"접속: {st.session_state['name']} ({'MASTER' if st.session_state['is_master'] else st.session_state['role']})")
+    if st.button("Logout"):
+        st.session_state['authenticated'] = False
+        st.rerun()
+
+tabs_list = ["🛍️ 상품", "📦 주문"]
+if st.session_state['is_master']:
+    tabs_list += ["👥 사용자 관리", "💰 정산 대시보드"]
+else:
+    tabs_list.append("💌 마케팅")
+
+tab_list = st.tabs(tabs_list)
+
+# 🛍️ 상품 관리
+with tab_list[0]:
+    st.subheader("제품 및 쇼룸 관리")
+    conn = database.get_db_connection()
+    if st.session_state['is_master']:
+        df_p = pd.read_sql_query('SELECT id, brand_name, product_name, price, qr_code_id FROM products', conn)
+    else:
+        param = (st.session_state['host_id'],)
+        query = 'SELECT id, brand_name, product_name, price, qr_code_id FROM products WHERE owner_id = %s' if database.DATABASE_URL else 'SELECT id, brand_name, product_name, price, qr_code_id FROM products WHERE owner_id = ?'
+        df_p = pd.read_sql_query(query, conn, params=param)
+    st.dataframe(df_p, use_container_width=True)
+    conn.close()
+
+# 💰 정산 대시보드 (마스터 전용)
+if st.session_state['is_master']:
+    with tab_list[3]:
+        st.title("💰 정산 관리 시스템")
+        st.markdown("<p style='color: #888;'>판매가 기준 <b>플랫폼 20% / 호스트 10%</b> 자동 수익 배분 현황입니다.</p>", unsafe_allow_html=True)
+        
+        conn = database.get_db_connection()
+        date_func = "TO_CHAR(o.created_at, 'MM/DD HH:MI')" if database.DATABASE_URL else "strftime('%m/%d %H:%M', o.created_at)"
+        query = f'''
+            SELECT o.id, {date_func} as "일시", h.name as "호스트", p.product_name as "상품", o.total_amount as "판매가", o.settlement_status as "상태"
+            FROM orders o JOIN products p ON o.product_id = p.id
+            JOIN hosts h ON p.owner_id = h.id ORDER BY o.id DESC
+        '''
+        df_settle = pd.read_sql_query(query, conn)
+        
+        if not df_settle.empty:
+            df_settle["플랫폼(20%)"] = (df_settle["판매가"] * 0.20).astype(int)
+            df_settle["호스트(10%)"] = (df_settle["판매가"] * 0.10).astype(int)
+            df_settle["잔여(70%)"] = (df_settle["판매가"] * 0.70).astype(int)
+            
+            c1, c2, c3 = st.columns(3)
+            pending_sum = df_settle[df_settle["상태"] == "PENDING"]["판매가"].sum()
+            c1.metric("정산 대기액", f"{pending_sum:,}원")
+            c2.metric("플랫폼 예상수익", f"{int(pending_sum * 0.20):,}원")
+            c3.metric("호스트 지급예정", f"{int(pending_sum * 0.10):,}원")
+            
+            st.markdown("---")
+            st.dataframe(df_settle.drop(columns=["id"]), use_container_width=True, hide_index=True)
+            
+            st.subheader("정산 상태 업데이트")
+            target_id = st.selectbox("업데이트할 주문 ID 선택", df_settle["id"].tolist())
+            new_status = st.radio("변경할 상태", ["PENDING", "COMPLETED"], horizontal=True)
+            
+            if st.button("상태 반영하기", type="primary"):
+                cursor = conn.cursor()
+                if database.DATABASE_URL:
+                    cursor.execute('UPDATE orders SET settlement_status = %s WHERE id = %s', (new_status, target_id))
+                else:
+                    cursor.execute('UPDATE orders SET settlement_status = ? WHERE id = ?', (new_status, target_id))
+                conn.commit()
+                
+                # Supabase 동기화
+                database.sync_order_to_supabase(target_id)
+                
+                st.success(f"주문 #{target_id} 상태 변경 완료")
+                time.sleep(1)
+                st.rerun()
+        else:
+            st.info("정산할 데이터가 없습니다.")
+        conn.close()
+
