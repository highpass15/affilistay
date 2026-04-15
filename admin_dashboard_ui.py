import streamlit as st
import pandas as pd
import uuid
import qrcode
from io import BytesIO
import database
import os
import time

# --- UI & 디자인 설정 ---
st.set_page_config(
    page_title="AffiliStay | Admin Portal",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 데이터베이스 초기화
database.init_db()

# --- 영구 주소 설정 (쇼룸 체크아웃 페이지) ---
CHECKOUT_BASE_URL = "https://affilistay-showroom.onrender.com"


# ─────────────────────────────────────────
# QR 코드 이미지 생성 헬퍼 함수
# ─────────────────────────────────────────
def generate_qr_image(url: str) -> BytesIO:
    """URL을 받아 QR 코드 PNG 이미지를 BytesIO로 반환합니다."""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ─────────────────────────────────────────
# 인증 시스템
# ─────────────────────────────────────────
def check_auth():
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    if 'auth_mode' not in st.session_state:
        st.session_state['auth_mode'] = 'login'

    if st.session_state['authenticated']:
        return True

    col_l, col_m, col_r = st.columns([1, 1.2, 1])
    with col_m:
        st.markdown("<h2 style='text-align: center;'>AffiliStay Portal</h2>", unsafe_allow_html=True)
        if st.session_state['auth_mode'] == 'login':
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True, type="primary"):
                conn = database.get_db_connection()
                cursor = conn.cursor()
                if database.DATABASE_URL:
                    cursor.execute(
                        'SELECT id, username, name, is_master, role FROM hosts WHERE username = %s AND password = %s',
                        (u, p)
                    )
                else:
                    cursor.execute(
                        'SELECT id, username, name, is_master, role FROM hosts WHERE username = ? AND password = ?',
                        (u, p)
                    )
                user = cursor.fetchone()
                conn.close()
                if user:
                    st.session_state.update({
                        "authenticated": True,
                        "host_id": user[0],
                        "username": user[1],
                        "name": user[2],
                        "is_master": user[3],
                        "role": user[4]
                    })
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
            if st.button("계정이 없으신가요? 회원가입", use_container_width=True):
                st.session_state['auth_mode'] = 'signup'
                st.rerun()
        else:
            st.markdown("#### 회원가입")
            role_choice = st.radio("유형 선택", ["HOST (숙소 운영자)", "GUEST (쇼룸 게스트)"], horizontal=True)
            actual_role = "HOST" if "HOST" in role_choice else "GUEST"

            full_name = st.text_input("이름(법인명)")
            phone = st.text_input("핸드폰 연락처")
            email = st.text_input("이메일 주소")
            signup_path = st.selectbox("가입경로", ["네이버광고", "지인소개", "인스타", "메일광고", "기타"])

            desired_prod = ""
            if actual_role == "GUEST":
                desired_prod = st.text_input("원하는 제품 유형")

            new_username = st.text_input("사용할 아이디")
            new_password = st.text_input("비밀번호", type="password")

            if st.button("가입 신청", use_container_width=True, type="primary"):
                conn = database.get_db_connection()
                cursor = conn.cursor()
                try:
                    if database.DATABASE_URL:
                        cursor.execute(
                            'INSERT INTO hosts (username, password, name, phone, email, signup_path, role, desired_product_type, is_master) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                            (new_username, new_password, full_name, phone, email, signup_path, actual_role, desired_prod, False)
                        )
                    else:
                        cursor.execute(
                            'INSERT INTO hosts (username, password, name, phone, email, signup_path, role, desired_product_type, is_master) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                            (new_username, new_password, full_name, phone, email, signup_path, actual_role, desired_prod, False)
                        )
                    conn.commit()
                    st.success("가입 신청 완료! 로그인 해주세요.")
                    st.session_state['auth_mode'] = 'login'
                    st.rerun()
                except Exception as e:
                    st.error(f"가입 오류 (아이디 중복 등): {e}")
                finally:
                    conn.close()

            if st.button("로그인으로 돌아가기", use_container_width=True):
                st.session_state['auth_mode'] = 'login'
                st.rerun()
    return False


if not check_auth():
    st.stop()


# ─────────────────────────────────────────
# 게스트 전용 페이지
# ─────────────────────────────────────────
if st.session_state['role'] == 'GUEST':
    st.title(f"🛋️ Welcome, {st.session_state['name']}님!")
    st.markdown("---")
    st.info("쇼룸 게스트님을 위한 맞춤형 큐레이션 페이지를 준비 중입니다. 잠시만 기다려 주세요!")
    if st.button("로그아웃"):
        st.session_state['authenticated'] = False
        st.rerun()
    st.stop()


# ─────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────
with st.sidebar:
    st.title("AFFILISTAY.")
    st.caption(f"접속: {st.session_state['name']} ({'MASTER' if st.session_state['is_master'] else 'HOST'})")
    st.markdown("---")
    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state['authenticated'] = False
        st.rerun()


# ─────────────────────────────────────────
# 탭 구성
# ─────────────────────────────────────────
tabs_list = ["🛍️ 상품 관리 & QR", "📦 주문 현황"]
if st.session_state['is_master']:
    tabs_list += ["👥 사용자 관리", "💰 정산 대시보드"]
else:
    tabs_list.append("💌 마케팅")

tab_list = st.tabs(tabs_list)


# ─────────────────────────────────────────
# TAB 0 : 상품 관리 & QR 생성
# ─────────────────────────────────────────
with tab_list[0]:
    host_id = st.session_state['host_id']
    is_master = st.session_state['is_master']

    # ── 상단: 제품 등록 폼 ──────────────────
    st.subheader("➕ 새 제품 등록 & QR 생성")
    with st.form("product_register_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            brand_name = st.text_input("브랜드명 *", placeholder="예) 아르캉시엘")
            product_name = st.text_input("제품명 *", placeholder="예) 침구 세트 5종")
        with col2:
            price = st.number_input("판매가격 (원) *", min_value=0, step=1000, format="%d")
            st.markdown(" ")  # 간격 맞추기
            st.markdown(" ")
        submitted = st.form_submit_button("🎯 제품 등록 & QR 코드 생성", use_container_width=True, type="primary")

    if submitted:
        if not brand_name or not product_name or price <= 0:
            st.error("브랜드명, 제품명, 가격은 필수 입력 항목입니다.")
        else:
            qr_id = str(uuid.uuid4())[:12]  # 고유 QR ID 생성
            checkout_url = f"{CHECKOUT_BASE_URL}/?qr={qr_id}"
            conn = database.get_db_connection()
            cursor = conn.cursor()
            try:
                if database.DATABASE_URL:
                    cursor.execute(
                        'INSERT INTO products (brand_name, product_name, price, qr_code_id, owner_id) VALUES (%s, %s, %s, %s, %s)',
                        (brand_name, product_name, price, qr_id, host_id)
                    )
                else:
                    cursor.execute(
                        'INSERT INTO products (brand_name, product_name, price, qr_code_id, owner_id) VALUES (?, ?, ?, ?, ?)',
                        (brand_name, product_name, price, qr_id, host_id)
                    )
                conn.commit()
                st.success(f"✅ '{product_name}' 등록 완료!")

                # QR 코드 즉시 표시
                qr_buf = generate_qr_image(checkout_url)
                col_qr, col_info = st.columns([1, 2])
                with col_qr:
                    st.image(qr_buf, caption="QR 코드", width=200)
                    # 다운로드 버튼
                    qr_buf.seek(0)
                    st.download_button(
                        label="📥 QR 이미지 다운로드",
                        data=qr_buf,
                        file_name=f"QR_{brand_name}_{product_name}.png",
                        mime="image/png",
                        use_container_width=True
                    )
                with col_info:
                    st.markdown(f"""
                    **브랜드**: {brand_name}
                    **제품명**: {product_name}
                    **가격**: {price:,}원
                    **QR 링크**: `{checkout_url}`
                    """)
                    st.code(checkout_url, language=None)

            except Exception as e:
                st.error(f"등록 오류: {e}")
            finally:
                conn.close()

    st.markdown("---")

    # ── 하단: 등록된 제품 리스트 & 개별 QR 재발급 ──
    st.subheader("📋 내 제품 리스트")
    conn = database.get_db_connection()
    if is_master:
        query = """
            SELECT p.id, p.brand_name, p.product_name, p.price, p.qr_code_id, h.name as 담당호스트
            FROM products p LEFT JOIN hosts h ON p.owner_id = h.id
            ORDER BY p.id DESC
        """
        df = pd.read_sql_query(query, conn)
    else:
        if database.DATABASE_URL:
            df = pd.read_sql_query(
                'SELECT id, brand_name, product_name, price, qr_code_id FROM products WHERE owner_id = %s ORDER BY id DESC',
                conn, params=(host_id,)
            )
        else:
            df = pd.read_sql_query(
                'SELECT id, brand_name, product_name, price, qr_code_id FROM products WHERE owner_id = ? ORDER BY id DESC',
                conn, params=(host_id,)
            )
    conn.close()

    if df.empty:
        st.info("아직 등록된 제품이 없습니다. 위 폼에서 첫 번째 제품을 등록해 보세요!")
    else:
        # 가격에 콤마 포맷 적용
        display_df = df.copy()
        display_df['price'] = display_df['price'].apply(lambda x: f"{x:,}원")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.markdown("#### 🔄 기존 제품 QR 재발급")
        selected_id = st.selectbox(
            "QR을 재발급할 제품 선택",
            options=df['id'].tolist(),
            format_func=lambda x: f"[{x}] {df[df['id']==x]['brand_name'].values[0]} - {df[df['id']==x]['product_name'].values[0]}"
        )
        if st.button("📱 선택 제품 QR 코드 보기", use_container_width=True):
            row = df[df['id'] == selected_id].iloc[0]
            checkout_url = f"{CHECKOUT_BASE_URL}/?qr={row['qr_code_id']}"
            qr_buf = generate_qr_image(checkout_url)
            col_qr2, col_info2 = st.columns([1, 2])
            with col_qr2:
                st.image(qr_buf, caption="QR 코드", width=200)
                qr_buf.seek(0)
                st.download_button(
                    label="📥 QR 다운로드",
                    data=qr_buf,
                    file_name=f"QR_{row['brand_name']}_{row['product_name']}.png",
                    mime="image/png",
                    use_container_width=True
                )
            with col_info2:
                st.markdown(f"""
                **브랜드**: {row['brand_name']}
                **제품명**: {row['product_name']}
                **가격**: {int(row['price']):,}원
                """)
                st.code(checkout_url, language=None)


# ─────────────────────────────────────────
# TAB 1 : 주문 현황
# ─────────────────────────────────────────
with tab_list[1]:
    st.subheader("📦 주문 현황")
    conn = database.get_db_connection()
    if is_master:
        if database.DATABASE_URL:
            order_query = """
                SELECT o.id, o.customer_name, o.phone_number, p.product_name, o.total_amount, o.payment_status, o.settlement_status, o.created_at
                FROM orders o JOIN products p ON o.product_id = p.id
                ORDER BY o.id DESC
            """
        else:
            order_query = "SELECT o.id, o.customer_name, p.product_name, o.total_amount, o.payment_status, o.settlement_status FROM orders o JOIN products p ON o.product_id = p.id ORDER BY o.id DESC"
        df_orders = pd.read_sql_query(order_query, conn)
    else:
        if database.DATABASE_URL:
            df_orders = pd.read_sql_query(
                "SELECT o.id, o.customer_name, o.phone_number, p.product_name, o.total_amount, o.payment_status, o.settlement_status, o.created_at FROM orders o JOIN products p ON o.product_id = p.id WHERE p.owner_id = %s ORDER BY o.id DESC",
                conn, params=(host_id,)
            )
        else:
            df_orders = pd.read_sql_query(
                "SELECT o.id, o.customer_name, p.product_name, o.total_amount, o.payment_status, o.settlement_status FROM orders o JOIN products p ON o.product_id = p.id WHERE p.owner_id = ? ORDER BY o.id DESC",
                conn, params=(host_id,)
            )
    conn.close()

    if df_orders.empty:
        st.info("아직 접수된 주문이 없습니다.")
    else:
        st.dataframe(df_orders, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────
# TAB 3 : 정산 대시보드 (마스터 전용)
# ─────────────────────────────────────────
if st.session_state['is_master']:
    with tab_list[3]:
        st.title("💰 정산 관리 시스템")
        st.markdown("<p style='color:#888'>판매가 기준 <b>플랫폼 20%(카드수수료 포함) / 호스트 수익 10%</b> 자동 계산 시스템</p>", unsafe_allow_html=True)

        conn = database.get_db_connection()
        date_func = "TO_CHAR(o.created_at, 'MM/DD HH24:MI')" if database.DATABASE_URL else "strftime('%m/%d %H:%M', o.created_at)"
        settle_query = f"""
            SELECT o.id, {date_func} as "일시", h.name as "호스트", p.product_name as "상품",
                   o.total_amount as "판매가", o.settlement_status as "상태"
            FROM orders o
            JOIN products p ON o.product_id = p.id
            JOIN hosts h ON p.owner_id = h.id
            ORDER BY o.id DESC
        """
        df_settle = pd.read_sql_query(settle_query, conn)

        if not df_settle.empty:
            df_settle["플랫폼(20%)"] = (df_settle["판매가"] * 0.20).astype(int)
            df_settle["호스트(10%)"] = (df_settle["판매가"] * 0.10).astype(int)
            df_settle["잔액(70%)"]   = (df_settle["판매가"] * 0.70).astype(int)

            c1, c2, c3 = st.columns(3)
            pending_sum = df_settle[df_settle["상태"] == "PENDING"]["판매가"].sum()
            c1.metric("정산 대기 합계",  f"{pending_sum:,}원")
            c2.metric("플랫폼 예상수익", f"{int(pending_sum * 0.20):,}원")
            c3.metric("호스트 지급예정", f"{int(pending_sum * 0.10):,}원")

            st.markdown("---")
            st.dataframe(df_settle.drop(columns=["id"]), use_container_width=True, hide_index=True)

            st.subheader("정산 상태 업데이트")
            target_id  = st.selectbox("업데이트할 주문 ID", df_settle["id"].tolist())
            new_status = st.radio("변경 상태", ["PENDING", "COMPLETED"], horizontal=True)

            if st.button("상태 반영하기 (Supabase 동기화)", type="primary"):
                cursor = conn.cursor()
                if database.DATABASE_URL:
                    cursor.execute('UPDATE orders SET settlement_status = %s WHERE id = %s', (new_status, target_id))
                else:
                    cursor.execute('UPDATE orders SET settlement_status = ? WHERE id = ?', (new_status, target_id))
                conn.commit()
                database.sync_order_to_supabase(target_id)
                st.success(f"주문 #{target_id} → {new_status} 변경 완료")
                time.sleep(1)
                st.rerun()
        else:
            st.info("정산할 데이터가 아직 없습니다.")
        conn.close()
