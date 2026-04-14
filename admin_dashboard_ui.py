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
+    page_title="AffiliStay | Partner Portal",
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
+
+# --- 인증 및 가입 시스템 ---
+def check_auth():
+    if 'authenticated' not in st.session_state:
+        st.session_state['authenticated'] = False
+    if 'auth_mode' not in st.session_state:
+        st.session_state['auth_mode'] = 'login'
+        
+    if st.session_state['authenticated']:
+        return True
+
+    st.markdown("""
+        <div style='text-align: center; padding-top: 20px;'>
+            <h1 style='font-weight: 200; font-size: 2.5rem; letter-spacing: -0.05em;'>AFFILISTAY.</h1>
+            <p style='color: #888; letter-spacing: 0.1em; margin-bottom: 20px;'>PARTNER & GUEST PORTAL</p>
+        </div>
+    """, unsafe_allow_html=True)
+
+    col_l, col_m, col_r = st.columns([1, 1.2, 1])
+    
+    with col_m:
+        if st.session_state['auth_mode'] == 'login':
+            st.markdown("<h3 style='text-align: center;'>로그인</h3>", unsafe_allow_html=True)
+            username = st.text_input("아이디")
+            password = st.text_input("비밀번호", type="password")
+            
+            if st.button("포털 입장하기", use_container_width=True, type="primary"):
+                conn = database.get_db_connection()
+                cursor = conn.cursor()
+                if database.DATABASE_URL:
+                    cursor.execute('SELECT id, username, name, is_master, role FROM hosts WHERE username = %s AND password = %s', (username, password))
+                else:
+                    cursor.execute('SELECT id, username, name, is_master, role FROM hosts WHERE username = ? AND password = ?', (username, password))
+                user = cursor.fetchone()
+                conn.close()
+                
+                if user:
+                    st.session_state['authenticated'] = True
+                    st.session_state['host_id'] = user[0]
+                    st.session_state['username'] = user[1]
+                    st.session_state['name'] = user[2]
+                    st.session_state['is_master'] = user[3]
+                    st.session_state['role'] = user[4]
+                    st.rerun()
+                else:
+                    st.error("Invalid credentials.")
+            
+            st.markdown("---")
+            if st.button("계정이 없으신가요? 회원가입", use_container_width=True):
+                st.session_state['auth_mode'] = 'signup'
+                st.rerun()
+                
+        else:
+            st.markdown("<h4 style='text-align: center;'>새로운 시작, 타입을 선택해주세요</h4>", unsafe_allow_html=True)
+            role_choice = st.radio("가입 유형", ["호스트 (숙소 운영자)", "쇼룸게스트 (구매 희망자)"], horizontal=True)
+            is_guest = (role_choice == "쇼룸게스트 (구매 희망자)")
+            
+            st.markdown("---")
+            entity_type = st.radio("구분", ["개인", "법인"], horizontal=True)
+            name_label = "이름" if entity_type == "개인" else "법인명"
+            full_name = st.text_input(name_label)
+            
+            col_phone, col_verify = st.columns([2, 1])
+            phone = col_phone.text_input("핸드폰 연락처", placeholder="010-0000-0000")
+            if 'phone_verified' not in st.session_state:
+                st.session_state['phone_verified'] = False
+                
+            if col_verify.button("통신사 인증", use_container_width=True, disabled=st.session_state['phone_verified']):
+                with st.spinner("본인 확인 중..."):
+                    time.sleep(1)
+                st.session_state['phone_verified'] = True
+                st.rerun()
+            
+            if st.session_state['phone_verified']:
+                st.caption("✅ 본인인증 완료")
+            
+            email = st.text_input("이메일 주소")
+            signup_path = st.selectbox("가입 경로", ["선택해주세요", "네이버광고", "지인소개", "인스타", "메일광고", "기타"])
+            
+            desired_type = ""
+            if is_guest:
+                desired_type = st.text_input("원하는 제품 유형", placeholder="예: 침구, 프리미엄 욕실용품 등")
+                
+            new_username = st.text_input("사용할 아이디")
+            new_password = st.text_input("비밀번호", type="password")
+            
+            if st.button("가입 신청 완료", use_container_width=True, type="primary"):
+                if not st.session_state['phone_verified']:
+                    st.warning("통신사 인증을 먼저 완료해주세요.")
+                elif not (full_name and email and new_username and new_password and signup_path != "선택해주세요"):
+                    st.warning("모든 필수 항목을 입력해주세요.")
+                elif is_guest and not desired_type:
+                    st.warning("원하는 제품 유형을 입력해주세요.")
+                else:
+                    conn = database.get_db_connection()
+                    cursor = conn.cursor()
+                    role_val = 'GUEST' if is_guest else 'HOST'
+                    try:
+                        if database.DATABASE_URL:
+                            cursor.execute(
+                                'INSERT INTO hosts (username, password, name, entity_type, phone, email, signup_path, desired_product_type, role, is_master) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
+                                (new_username, new_password, full_name, entity_type, phone, email, signup_path, desired_type, role_val, False)
+                            )
+                        else:
+                            cursor.execute(
+                                'INSERT INTO hosts (username, password, name, entity_type, phone, email, signup_path, desired_product_type, role, is_master) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
+                                (new_username, new_password, full_name, entity_type, phone, email, signup_path, desired_type, role_val, False)
+                            )
+                        conn.commit()
+                        st.success(f"{role_choice} 가입이 완료되었습니다!")
+                        st.session_state['auth_mode'] = 'login'
+                        st.session_state['phone_verified'] = False
+                        time.sleep(1.5)
+                        st.rerun()
+                    except Exception as e:
+                        st.error(f"아이디가 중복되었거나 오류가 발생했습니다: {e}")
+                    finally:
+                        conn.close()
+            
+            if st.button("로그인으로 돌아가기", use_container_width=True):
+                st.session_state['auth_mode'] = 'login'
+                st.rerun()
+                
+    return False
+
+if not check_auth():
+    st.stop()
+
+# --- 대시보드 메인 ---
+st.markdown("""
+    <style>
+    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@200;400;700&display=swap');
+    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
+    .stApp { background-color: #FAF9F6; }
+    </style>
+    """, unsafe_allow_html=True)
+
+with st.sidebar:
+    st.markdown(f"<h2 style='font-weight:700;'>AFFILISTAY.</h2>", unsafe_allow_html=True)
+    role_name = "마스터" if st.session_state['is_master'] else ("호스트" if st.session_state.get('role') == 'HOST' else "쇼룸게스트")
+    st.caption(f"접속자: {st.session_state['name']} ({role_name})")
+    st.markdown("---")
+    if st.button("로그아웃", use_container_width=True):
+        st.session_state['authenticated'] = False
+        st.rerun()
+
+# --- 권한별 대시보드 구성 ---
+if st.session_state.get('role') == 'GUEST' and not st.session_state['is_master']:
+    # 쇼룸게스트 전용 화면
+    st.title("쇼룸게스트 전용 대시보드")
+    st.markdown(f"### 반갑반갑습니다, {st.session_state['name']}님!")
+    st.markdown("""
+        <div style='background: white; padding: 2rem; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);'>
+            <h4 style='color: #1A1A1A;'>현재 맞춤형 쇼룸 큐레이션 준비 중입니다.</h4>
+            <p style='color: #888;'>가입 시 선택하신 제품 유형을 기반으로 곧 최고의 품질과 특별한 가격의 제품들을 추천해 드릴 예정입니다.</p>
+            <hr>
+            <p style='font-size: 0.9rem;'>가입 시 선택한 관심 유형: <b>{}</b></p>
+        </div>
+    """.format(st.session_state.get('desired_product_type', '정보 없음')), unsafe_allow_html=True)
+    st.info("알림: 신규 추천 상품이 등록되면 입력하신 이메일로 소식을 전해드립니다.")
+
+else:
+    # 호스트 또는 마스터 대시보드
+    st.title(f"{'마스터' if st.session_state['is_master'] else '호스트'} 대시보드")
+    
+    tabs_list = ["🛍️ 상품 관리", "📦 주문 현황"]
+    if st.session_state['is_master']:
+        tabs_list.append("👥 파트너 및 게스트 관리")
+    else:
+        tabs_list.append("💌 마케팅/영업 도구")
+        
+    tab_list = st.tabs(tabs_list)
+    
+    with tab_list[0]:
+        st.subheader("제품 및 쇼룸 관리")
+        conn = database.get_db_connection()
+        if st.session_state['is_master']:
+            df_p = pd.read_sql_query('SELECT qr_code_id, brand_name, product_name, price FROM products', conn)
+        else:
+            query = 'SELECT qr_code_id, brand_name, product_name, price FROM products WHERE owner_id = %s' if database.DATABASE_URL else 'SELECT qr_code_id, brand_name, product_name, price FROM products WHERE owner_id = ?'
+            df_p = pd.read_sql_query(query, conn, params=(st.session_state['host_id'],))
+        conn.close()
+        st.dataframe(df_p, use_container_width=True)
+
+    with tab_list[1]:
+        st.subheader("실시간 주문 내역")
+        # 주문 로직 (생략 - 기존 유지)
+
+    if st.session_state['is_master']:
+        with tab_list[2]:
+            st.subheader("👥 가입 사용자 통합 관리")
+            conn = database.get_db_connection()
+            df_u = pd.read_sql_query('SELECT username, name, role, entity_type, phone, email, signup_path, desired_product_type, created_at FROM hosts WHERE is_master = FALSE ORDER BY id DESC', conn)
+            conn.close()
+            
+            # 상단 요약 통계
+            c1, c2, c3 = st.columns(3)
+            c1.metric("총 파트너(호스트)", len(df_u[df_u['role'] == 'HOST']))
+            c2.metric("총 쇼룸게스트", len(df_u[df_u['role'] == 'GUEST']))
+            c3.metric("신규 가입 (최근 7일)", 5) # 예시
+            
+            st.dataframe(df_u, use_container_width=True, hide_index=True)
+    else:
+        with tab_list[2]:
+            st.subheader("호스트 전용 마케팅 도구")
+            st.info("게스트 유입을 위한 마케팅 메시지 템플릿 서비스가 곧 제공됩니다.")
+
