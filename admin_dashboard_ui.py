import streamlit as st
import pandas as pd
import uuid
import qrcode
from io import BytesIO
import database
import os
import time

st.set_page_config(
    page_title="AffiliStay 파트너 센터",
    page_icon="🛋️",
    layout="wide",
    initial_sidebar_state="expanded"
)

database.init_db()

CHECKOUT_BASE_URL = "https://affilistay-showroom.onrender.com"

# ─────────────────────────────────────────
# 헬퍼 함수
# ─────────────────────────────────────────
def make_qr(url: str) -> BytesIO:
    qr = qrcode.QRCode(version=1, box_size=8, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#2C2520", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def ph(text="이미지 없음"):
    """이미지가 없을 때 표시할 플레이스홀더"""
    st.markdown(
        f"<div style='background:#F0EBE3;border-radius:12px;padding:32px;text-align:center;"
        f"color:#9C9288;font-size:12px;'>{text}</div>",
        unsafe_allow_html=True
    )

def show_img(b64_str, width=280):
    if b64_str:
        try:
            st.image(database.base64_to_bytes(b64_str), width=width)
        except Exception:
            ph()
    else:
        ph()

# ─────────────────────────────────────────
# 인증 시스템
# ─────────────────────────────────────────
def check_auth():
    for key, default in [('authenticated', False), ('auth_mode', 'login')]:
        if key not in st.session_state:
            st.session_state[key] = default

    if st.session_state['authenticated']:
        return True

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<h2 style='text-align:center;font-weight:300;letter-spacing:0.05em'>AFFILISTAY.</h2>", unsafe_allow_html=True)

        if st.session_state['auth_mode'] == 'login':
            st.markdown("#### 로그인")
            with st.form("login_form", clear_on_submit=False):
                u = st.text_input("아이디")
                p = st.text_input("비밀번호", type="password")
                if st.form_submit_button("로그인", use_container_width=True, type="primary"):
                    conn = database.get_db_connection()
                    cursor = conn.cursor()
                    q = ('SELECT id,username,name,is_master,role FROM hosts WHERE username=%s AND password=%s'
                         if database.DATABASE_URL else
                         'SELECT id,username,name,is_master,role FROM hosts WHERE username=? AND password=?')
                    cursor.execute(q, (u, p))
                    user = cursor.fetchone()
                    conn.close()
                    if user:
                        st.session_state.update({
                            "authenticated": True, "host_id": user[0],
                            "username": user[1], "name": user[2],
                            "is_master": bool(user[3]), "role": user[4]
                        })
                        st.rerun()
                    else:
                        st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
            
            if st.button("계정이 없으신가요? 회원가입", use_container_width=True):
                st.session_state['auth_mode'] = 'signup'
                st.rerun()

        else:
            st.markdown("#### 회원가입")

            # 역할 선택 (3가지)
            role_map = {
                "🏠 호스트 (숙소 운영자)": "HOST",
                "🎁 입점업체 (제품 공급사)": "BRAND",
                "🛋️ 게스트 (쇼룸 방문자)": "GUEST"
            }
            role_label = st.radio("가입 유형을 선택하세요", list(role_map.keys()), horizontal=False)
            actual_role = role_map[role_label]

            st.markdown("---")
            full_name = st.text_input("이름 / 업체명")
            phone     = st.text_input("연락처")
            email     = st.text_input("이메일")
            signup_path = st.selectbox("가입 경로", ["SNS", "지인소개", "검색", "광고", "기타"])
            new_username = st.text_input("사용할 아이디")
            new_password = st.text_input("비밀번호", type="password")

            if st.button("가입 신청", use_container_width=True, type="primary"):
                conn = database.get_db_connection()
                cursor = conn.cursor()
                try:
                    q = ('INSERT INTO hosts (username,password,name,phone,email,signup_path,role,is_master) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)'
                         if database.DATABASE_URL else
                         'INSERT INTO hosts (username,password,name,phone,email,signup_path,role,is_master) VALUES (?,?,?,?,?,?,?,?)')
                    cursor.execute(q, (new_username, new_password, full_name, phone, email, signup_path, actual_role, False))
                    conn.commit()
                    st.success(f"✅ 가입 완료! [{role_label}] 계정으로 로그인해 주세요.")
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
# 사이드바
# ─────────────────────────────────────────
role      = st.session_state['role']
is_master = st.session_state['is_master']
host_id   = st.session_state['host_id']
uname     = st.session_state['name']

ROLE_LABELS = {"HOST": "숙소 호스트", "BRAND": "입점사(브랜드)", "GUEST": "게스트"}
role_display = "MASTER" if is_master else ROLE_LABELS.get(role, "파트너")

with st.sidebar:
    st.markdown(f"### AFFILISTAY.")
    st.caption(f"**{uname}** ({role_display})")
    st.markdown("---")
    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state['authenticated'] = False
        st.rerun()

# ─────────────────────────────────────────
# 공통 UI 컴포넌트: 상품 & QR / 주문 현황
# ─────────────────────────────────────────
def render_tab_qr(host_id, is_master):
    st.subheader("➕ 새 제품 등록 & QR 생성")
    ROOM_MAP = {
        '거실': 'living_room', '침실': 'bedroom', '주방': 'kitchen', '화장실': 'bathroom',
    }
    PROD_CAT_MAP = {
        '🛋️ 가구': 'furniture',
        '🧶 패브릭': 'fabric',
        '📺 가전·디지털': 'appliance',
        '🍳 주방용품': 'kitchenware',
        '🥯 식품': 'food',
        '🪴 데코·식물': 'deco',
        '💡 조명': 'lighting',
        '📦 수납·정리': 'storage',
        '🛁 생활품': 'lifestyle',
        '🔌 헤어드라이어': 'hairdryer'
    }
    with st.form(f"product_register_form_{host_id}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            brand_name   = st.text_input("브랜드명 *")
            product_name = st.text_input("제품명 *")
            room_label   = st.selectbox("배치 공간 (룸 타입) *", list(ROOM_MAP.keys()))
            prod_cat_label = st.selectbox("품목 카테고리 *", list(PROD_CAT_MAP.keys()))
        with c2:
            original_price = st.number_input("정가 (할인 전 가격) *", min_value=0, step=1000, format="%d")
            price = st.number_input("판매가 (실제 결제 금액) *", min_value=0, step=1000, format="%d")
            prod_description = st.text_input("간결한 한줄 설명 (리스트 노출용)", placeholder="예: 구름처럼 포근한 조명")
            prod_images = st.file_uploader("제품 이미지들 * (첫 이미지가 메인)", type=["jpg","jpeg","png","webp"], accept_multiple_files=True)
        
        st.markdown("**🔍 상세 정보 및 옵션 설정**")
        detailed_description = st.text_area("제품 상세 상세설명 (상세페이지 노출)", placeholder="제품의 소재, 특징 등을 자세히 적어주세요. (줄바꿈 가능)", height=120)
        options_raw = st.text_area("제품 옵션 (형식: 옵션명: 값1, 값2)", placeholder="예: 색상: 화이트, 블랙\n사이즈: S, M, L", height=80)
        submitted = st.form_submit_button("🎯 등록 & QR 생성", use_container_width=True, type="primary")

    if submitted:
        if not brand_name or not product_name or price <= 0 or not prod_images:
            st.error("브랜드명, 제품명, 가격, 그리고 최소 한 장의 이미지를 등록해 주세요.")
        else:
            qr_id = str(uuid.uuid4())[:12]
            url   = f"{CHECKOUT_BASE_URL}/shop/{qr_id}"
            main_img_b64 = database.file_to_base64(prod_images[0])
            conn = database.get_db_connection()
            try:
                cursor = conn.cursor()
                # 1. 메인 제품 정보 저장
                q = ('INSERT INTO products (brand_name,product_name,price,original_price,qr_code_id,owner_id,room_category,product_category,description,detailed_description,image_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id'
                     if database.DATABASE_URL else
                     'INSERT INTO products (brand_name,product_name,price,original_price,qr_code_id,owner_id,room_category,product_category,description,detailed_description,image_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)')
                
                cursor.execute(q, (brand_name, product_name, price, original_price or price, qr_id, host_id, ROOM_MAP[room_label], PROD_CAT_MAP[prod_cat_label], prod_description or None, detailed_description or None, main_img_b64))
                
                new_product_id = cursor.fetchone()[0] if database.DATABASE_URL else cursor.lastrowid
                
                # 2. 추가 이미지 저장 (전체 이미지 저장)
                for i, img_file in enumerate(prod_images):
                    img_data = database.file_to_base64(img_file)
                    q_img = ('INSERT INTO product_images (product_id, image_data, sort_order) VALUES (%s,%s,%s)'
                            if database.DATABASE_URL else
                            'INSERT INTO product_images (product_id, image_data, sort_order) VALUES (?,?,?)')
                    cursor.execute(q_img, (new_product_id, img_data, i))

                # 3. 옵션 저장
                if options_raw:
                    lines = [line.strip() for line in options_raw.split('\n') if ':' in line]
                    for line in lines:
                        opt_name, opt_vals = [x.strip() for x in line.split(':', 1)]
                        q_opt = ('INSERT INTO product_options (product_id, name, values) VALUES (%s,%s,%s)'
                                if database.DATABASE_URL else
                                'INSERT INTO product_options (product_id, name, values) VALUES (?,?,?)')
                        cursor.execute(q_opt, (new_product_id, opt_name, opt_vals))

                conn.commit()
                st.success(f"✅ '{product_name}' 등록 완료!")
                buf = make_qr(url)
                cq, ci = st.columns([1, 2])
                with cq:
                    st.image(buf, width=180)
                    buf.seek(0)
                    st.download_button("📥 QR 다운로드", buf, f"QR_{product_name}.png", "image/png", use_container_width=True)
                with ci:
                    st.code(url, language=None)
            except Exception as e:
                st.error(f"오류: {e}")
            finally:
                conn.close()

    st.markdown("---")
    st.subheader("📋 전체/내 제품 목록")
    conn = database.get_db_connection()
    if is_master:
        df_p = pd.read_sql_query("SELECT p.id,p.brand_name,p.product_name,p.price,p.original_price,p.room_category,p.qr_code_id,h.name as owner FROM products p LEFT JOIN hosts h ON p.owner_id=h.id ORDER BY p.id DESC", conn)
    else:
        q = ('SELECT id,brand_name,product_name,price,original_price,room_category,qr_code_id FROM products WHERE owner_id=%s ORDER BY id DESC'
             if database.DATABASE_URL else
             'SELECT id,brand_name,product_name,price,original_price,room_category,qr_code_id FROM products WHERE owner_id=? ORDER BY id DESC')
        df_p = pd.read_sql_query(q, conn, params=(host_id,))
    conn.close()

    if df_p.empty:
        st.info("등록된 제품이 없습니다.")
    else:
        dsp = df_p.copy()
        def calc_discount(row):
            op = row['original_price'] if row['original_price'] and row['original_price'] > 0 else row['price']
            p = row['price']
            if op > p:
                return f"{int((op - p) / op * 100)}%"
            return "0%"
        
        dsp['discount'] = dsp.apply(calc_discount, axis=1)
        dsp['price'] = dsp['price'].apply(lambda x: f"{x:,}원")
        if 'original_price' in dsp.columns:
            dsp['original_price'] = dsp['original_price'].apply(lambda x: f"{x:,}원" if x else "-")
        ROOM_LABEL_MAP = {'living_room': '거실', 'bedroom': '침실', 'kitchen': '주방', 'bathroom': '화장실'}
        if 'room_category' in dsp.columns:
            dsp['room_category'] = dsp['room_category'].map(ROOM_LABEL_MAP).fillna('-')
        st.dataframe(dsp, use_container_width=True, hide_index=True)

        st.markdown("#### 🔄 QR 재발급")
        sel = st.selectbox("제품 선택 (QR 다운로드용)", df_p['id'].tolist(),
                           format_func=lambda x: f"[{x}] {df_p[df_p['id']==x]['brand_name'].values[0]} - {df_p[df_p['id']==x]['product_name'].values[0]}")
        if st.button("📱 선택 제품 QR 보기", key=f"qr_regen_{host_id}"):
            row = df_p[df_p['id']==sel].iloc[0]
            url = f"{CHECKOUT_BASE_URL}/shop/{row['qr_code_id']}"
            buf = make_qr(url)
            cq2, ci2 = st.columns([1, 2])
            with cq2:
                st.image(buf, width=180)
                buf.seek(0)
                st.download_button("📥 다운로드", buf, f"QR_{row['product_name']}.png", "image/png", key=f"qr_dl_{host_id}")
            with ci2:
                st.code(url, language=None)

def render_tab_orders(host_id, is_master):
    st.subheader("📦 주문 현황")
    conn = database.get_db_connection()
    if is_master:
        df_o = pd.read_sql_query("SELECT o.id,o.customer_name,o.phone_number,o.shipping_address,o.delivery_note,p.product_name,p.brand_name,o.total_amount,o.payment_status,o.settlement_status,o.created_at FROM orders o JOIN products p ON o.product_id=p.id ORDER BY o.id DESC", conn)
    else:
        q = ('SELECT o.id,o.customer_name,o.phone_number,o.shipping_address,o.delivery_note,p.product_name,o.total_amount,o.payment_status,o.settlement_status,o.created_at FROM orders o JOIN products p ON o.product_id=p.id WHERE p.owner_id=%s ORDER BY o.id DESC'
             if database.DATABASE_URL else
             'SELECT o.id,o.customer_name,o.phone_number,o.shipping_address,o.delivery_note,p.product_name,o.total_amount,o.payment_status,o.settlement_status,o.created_at FROM orders o JOIN products p ON o.product_id=p.id WHERE p.owner_id=? ORDER BY o.id DESC')
        df_o = pd.read_sql_query(q, conn, params=(host_id,))
    conn.close()
    if df_o.empty:
        st.info("아직 고객 주문이 없습니다.")
    else:
        st.dataframe(df_o, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────
# GUEST 페이지
# ─────────────────────────────────────────
if role == 'GUEST' and not is_master:
    st.title(f"🛋️ 안녕하세요, {uname}님!")
    st.info("쇼룸 게스트님을 위한 큐레이션 페이지를 준비 중입니다.")
    st.stop()

# ─────────────────────────────────────────
# BRAND (입점업체) 페이지
# ─────────────────────────────────────────
if role == 'BRAND' and not is_master:
    tab_qr, tab_ord, tab1, tab2, tab3, tab4 = st.tabs([
        "🛍️ 상품 & QR (다이렉트 판매)",
        "📦 고객 주문 현황",
        "📦 브랜드 제품 풀(Pool) 관리",
        "🏠 호스트 숙소 탐색",
        "📤 호스트 입점 제안",
        "📊 전체 입점 현황"
    ])
    
    with tab_qr: render_tab_qr(host_id, is_master)
    with tab_ord: render_tab_orders(host_id, is_master)

    # ── TAB1: 내 입점 제품 관리 ──────────────────
    with tab1:
        st.subheader("📦 입점 제품 등록 · 관리")
        st.caption("숙소에 비치할 입점 가능 제품을 등록하세요.")

        with st.form("brand_item_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                item_name = st.text_input("제품명 *")
                description = st.text_area("제품 소개", height=80)
            with c2:
                stock_qty = st.number_input("입점 가능 재고 수량 *", min_value=0, step=1)
                item_img = st.file_uploader("제품 이미지", type=["jpg","jpeg","png","webp"])
            submitted = st.form_submit_button("✅ 제품 등록", use_container_width=True, type="primary")

        if submitted:
            if not item_name or stock_qty < 0 or not item_img:
                st.error("제품명, 재고 수량, 그리고 제품 이미지를 모두 입력해 주세요.")
            else:
                img_b64 = database.file_to_base64(item_img) if item_img else None
                conn = database.get_db_connection()
                cursor = conn.cursor()
                try:
                    q = ('INSERT INTO brand_items (brand_id,item_name,description,stock_qty,image) VALUES (%s,%s,%s,%s,%s)'
                         if database.DATABASE_URL else
                         'INSERT INTO brand_items (brand_id,item_name,description,stock_qty,image) VALUES (?,?,?,?,?)')
                    cursor.execute(q, (host_id, item_name, description, stock_qty, img_b64))
                    conn.commit()
                    st.success(f"'{item_name}' 등록 완료!")
                    st.rerun()
                except Exception as e:
                    st.error(f"오류: {e}")
                finally:
                    conn.close()

        st.markdown("---")
        st.markdown("#### 🗂️ 등록된 제품 목록")
        conn = database.get_db_connection()
        q = ('SELECT id,item_name,description,stock_qty,image FROM brand_items WHERE brand_id=%s ORDER BY id DESC'
             if database.DATABASE_URL else
             'SELECT id,item_name,description,stock_qty,image FROM brand_items WHERE brand_id=? ORDER BY id DESC')
        df_items = pd.read_sql_query(q, conn, params=(host_id,))
        conn.close()

        if df_items.empty:
            st.info("아직 등록된 입점 제품이 없습니다.")
        else:
            for _, row in df_items.iterrows():
                with st.container():
                    c1, c2 = st.columns([1, 3])
                    with c1:
                        show_img(row['image'], width=120)
                    with c2:
                        st.markdown(f"**[#{row['id']}] {row['item_name']}**")
                        st.caption(row['description'] or "설명 없음")
                        st.markdown(f"📦 입점 가능 재고: **{row['stock_qty']}개**")
                    st.divider()

    # ── TAB2: 호스트 숙소 탐색 ──────────────────
    with tab2:
        st.subheader("🏠 호스트 숙소 탐색")
        st.caption("입점 제품을 비치할 숙소를 확인하세요.")
        conn = database.get_db_connection()
        df_venues = pd.read_sql_query("""
            SELECT v.id, h.name as host_name, h.id as host_id,
                   v.location, v.description, v.image1, v.image2
            FROM host_venues v JOIN hosts h ON v.host_id = h.id
            ORDER BY v.id DESC
        """ if database.DATABASE_URL else """
            SELECT v.id, h.name as host_name, h.id as host_id,
                   v.location, v.description, v.image1, v.image2
            FROM host_venues v JOIN hosts h ON v.host_id = h.id
            ORDER BY v.id DESC
        """, conn)
        conn.close()

        if df_venues.empty:
            st.info("아직 등록된 호스트 숙소가 없습니다.")
        else:
            for _, v in df_venues.iterrows():
                with st.expander(f"🏠 {v['host_name']} 님의 숙소 — 📍 {v['location'] or '위치 미입력'}", expanded=False):
                    c1, c2 = st.columns(2)
                    with c1:
                        show_img(v['image1'])
                    with c2:
                        show_img(v['image2'])
                    if v['description']:
                        st.caption(v['description'])

    # ── TAB3: 입점 보내기 ──────────────────────
    with tab3:
        st.subheader("📤 호스트에게 입점 보내기")
        st.caption("비치할 제품과 수량을 선택해 원하는 숙소 호스트에게 입점을 제안하세요.")

        conn = database.get_db_connection()
        # 내 제품 목록
        q_items = ('SELECT id,item_name,stock_qty FROM brand_items WHERE brand_id=%s AND stock_qty>0'
                   if database.DATABASE_URL else
                   'SELECT id,item_name,stock_qty FROM brand_items WHERE brand_id=? AND stock_qty>0')
        my_items = pd.read_sql_query(q_items, conn, params=(host_id,))
        # 숙소 있는 호스트 목록
        host_venues = pd.read_sql_query("""
            SELECT h.id, h.name, v.location FROM hosts h
            JOIN host_venues v ON h.id = v.host_id WHERE h.role='HOST'
        """ if database.DATABASE_URL else """
            SELECT h.id, h.name, v.location FROM hosts h
            JOIN host_venues v ON h.id = v.host_id WHERE h.role='HOST'
        """, conn)
        conn.close()

        if my_items.empty:
            st.warning("입점 가능한 제품이 없습니다. 먼저 제품을 등록해 주세요.")
        elif host_venues.empty:
            st.warning("아직 숙소 정보를 등록한 호스트가 없습니다.")
        else:
            with st.form("sponsorship_form"):
                item_options = {f"[#{r['id']}] {r['item_name']} (재고 {r['stock_qty']}개)": r['id'] for _, r in my_items.iterrows()}
                host_options = {f"{r['name']} — 📍{r['location'] or '위치 미입력'}": r['id'] for _, r in host_venues.iterrows()}

                sel_item_label = st.selectbox("입점할 제품 선택", list(item_options.keys()))
                sel_host_label = st.selectbox("입점받을 호스트 선택", list(host_options.keys()))
                qty = st.number_input("입점 수량", min_value=1, step=1)
                message = st.text_area("호스트에게 전할 메시지 (선택)", height=80)
                send = st.form_submit_button("📤 입점 제안 보내기", use_container_width=True, type="primary")

            if send:
                item_id  = item_options[sel_item_label]
                h_id     = host_options[sel_host_label]
                conn = database.get_db_connection()
                cursor = conn.cursor()
                try:
                    # 재고 차감
                    q_dec = ('UPDATE brand_items SET stock_qty=stock_qty-%s WHERE id=%s'
                             if database.DATABASE_URL else
                             'UPDATE brand_items SET stock_qty=stock_qty-? WHERE id=?')
                    cursor.execute(q_dec, (qty, item_id))
                    # 입점 내역 추가
                    q_ins = ('INSERT INTO sponsorships (brand_id,host_id,brand_item_id,qty,message,status) VALUES (%s,%s,%s,%s,%s,%s)'
                             if database.DATABASE_URL else
                             'INSERT INTO sponsorships (brand_id,host_id,brand_item_id,qty,message,status) VALUES (?,?,?,?,?,?)')
                    cursor.execute(q_ins, (host_id, h_id, item_id, qty, message, 'PENDING'))
                    conn.commit()
                    st.success("✅ 입점 제안이 전송되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"오류: {e}")
                finally:
                    conn.close()

    # ── TAB4: 입점 현황 ────────────────────────
    with tab4:
        st.subheader("📊 입점 현황")
        conn = database.get_db_connection()
        q = ("""
            SELECT s.id, h.name as 호스트, bi.item_name as 제품, s.qty as 수량,
                   s.status as 상태, s.message as 메시지, s.created_at as 일시
            FROM sponsorships s
            JOIN hosts h ON s.host_id = h.id
            JOIN brand_items bi ON s.brand_item_id = bi.id
            WHERE s.brand_id = %s ORDER BY s.id DESC
        """ if database.DATABASE_URL else """
            SELECT s.id, h.name as 호스트, bi.item_name as 제품, s.qty as 수량,
                   s.status as 상태, s.message as 메시지, s.created_at as 일시
            FROM sponsorships s
            JOIN hosts h ON s.host_id = h.id
            JOIN brand_items bi ON s.brand_item_id = bi.id
            WHERE s.brand_id = ? ORDER BY s.id DESC
        """)
        df_sp = pd.read_sql_query(q, conn, params=(host_id,))
        conn.close()
        if df_sp.empty:
            st.info("아직 입점 내역이 없습니다.")
        else:
            st.dataframe(df_sp.drop(columns=['id']), use_container_width=True, hide_index=True)

    st.stop()

# ─────────────────────────────────────────
# HOST 페이지 + MASTER 공통
# ─────────────────────────────────────────
tabs_list = ["🛍️ 상품 & QR", "📦 주문 현황", "⭐ 리뷰", "💬 문의사항", "🏠 숙소 프로필", "🎁 입점 신청"]
if is_master:
    tabs_list = ["🛍️ 상품 & QR", "📦 주문 현황", "⭐ 리뷰", "💬 문의사항", "🏠 숙소 탐색", "🎁 입점 현황", "👥 사용자 관리", "💰 정산"]

tab_list = st.tabs(tabs_list)

# ═══════════════════════════════════════
# TAB 0 — 상품 관리 & QR
# ═══════════════════════════════════════
with tab_list[0]:
    render_tab_qr(host_id, is_master)

# ═══════════════════════════════════════
# TAB 1 — 주문 현황
# ═══════════════════════════════════════
with tab_list[1]:
    render_tab_orders(host_id, is_master)

# ═══════════════════════════════════════
# TAB 2 — 리뷰 관리
# ═══════════════════════════════════════
with tab_list[2]:
    st.subheader("⭐ 제품 리뷰 관리")
    conn = database.get_db_connection()
    q = ("""
        SELECT r.id, p.product_name, r.customer_name, r.rating, r.comment, r.created_at
        FROM reviews r JOIN products p ON r.product_id = p.id
        """ + ("" if is_master else " WHERE p.owner_id = %s") + " ORDER BY r.created_at DESC")
    if is_master: df_r = pd.read_sql_query(q, conn)
    else: df_r = pd.read_sql_query(q, conn, params=(host_id,))
    conn.close()
    if df_r.empty: st.info("아직 리뷰가 없습니다.")
    else: st.dataframe(df_r, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════
# TAB 3 — 문의사항 관리
# ═══════════════════════════════════════
with tab_list[3]:
    st.subheader("💬 제품 문의사항 (취소/환불/기타)")
    conn = database.get_db_connection()
    q = ("""
        SELECT q.id, p.product_name, q.customer_name, q.type, q.content, q.created_at
        FROM product_inquiries q JOIN products p ON q.product_id = p.id
        """ + ("" if is_master else " WHERE p.owner_id = %s") + " ORDER BY q.created_at DESC")
    if is_master: df_inq = pd.read_sql_query(q, conn)
    else: df_inq = pd.read_sql_query(q, conn, params=(host_id,))
    conn.close()
    if df_inq.empty: st.info("아직 문의사항이 없습니다.")
    else: st.dataframe(df_inq, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════
# TAB 4 — HOST: 숙소 프로필 / MASTER: 숙소 탐색
# ═══════════════════════════════════════
with tab_list[4]:
    if is_master:
        # 마스터: 전체 숙소 탐색
        st.subheader("🏠 전체 호스트 숙소")
        conn = database.get_db_connection()
        df_all_v = pd.read_sql_query("SELECT h.name,v.location,v.description,v.image1,v.image2 FROM host_venues v JOIN hosts h ON v.host_id=h.id", conn)
        conn.close()
        if df_all_v.empty:
            st.info("등록된 숙소가 없습니다.")
        else:
            for _, v in df_all_v.iterrows():
                with st.expander(f"🏠 {v['name']} — 📍{v['location'] or ''}"):
                    c1, c2 = st.columns(2)
                    with c1: show_img(v['image1'])
                    with c2: show_img(v['image2'])
                    if v['description']: st.caption(v['description'])
    else:
        # 호스트: 내 숙소 프로필 등록·수정
        st.subheader("🏠 내 숙소 프로필")
        st.caption("숙소 위치와 내부 사진을 등록하면 입점업체가 입점 제품을 제안할 수 있습니다.")

        # 기존 데이터 불러오기
        conn = database.get_db_connection()
        q_v = ('SELECT * FROM host_venues WHERE host_id=%s' if database.DATABASE_URL
               else 'SELECT * FROM host_venues WHERE host_id=?')
        df_v = pd.read_sql_query(q_v, conn, params=(host_id,))
        conn.close()
        existing = df_v.iloc[0] if not df_v.empty else None

        with st.form("venue_form"):
            location    = st.text_input("숙소 위치 (주소 또는 지역명)", value=existing['location'] if existing is not None else "")
            description = st.text_area("숙소 소개 (선택)", value=existing['description'] if existing is not None else "", height=80)
            st.markdown("**숙소 내부 사진 (최대 2장)**")
            cv1, cv2 = st.columns(2)
            with cv1: img1_file = st.file_uploader("사진 1", type=["jpg","jpeg","png","webp"], key="v1")
            with cv2: img2_file = st.file_uploader("사진 2", type=["jpg","jpeg","png","webp"], key="v2")
            save_venue = st.form_submit_button("💾 저장", use_container_width=True, type="primary")

        if save_venue:
            img1_b64 = database.file_to_base64(img1_file) if img1_file else (existing['image1'] if existing is not None else None)
            img2_b64 = database.file_to_base64(img2_file) if img2_file else (existing['image2'] if existing is not None else None)
            conn = database.get_db_connection()
            cursor = conn.cursor()
            try:
                if existing is not None:
                    q = ('UPDATE host_venues SET location=%s,description=%s,image1=%s,image2=%s WHERE host_id=%s'
                         if database.DATABASE_URL else
                         'UPDATE host_venues SET location=?,description=?,image1=?,image2=? WHERE host_id=?')
                    cursor.execute(q, (location, description, img1_b64, img2_b64, host_id))
                else:
                    q = ('INSERT INTO host_venues (host_id,location,description,image1,image2) VALUES (%s,%s,%s,%s,%s)'
                         if database.DATABASE_URL else
                         'INSERT INTO host_venues (host_id,location,description,image1,image2) VALUES (?,?,?,?,?)')
                    cursor.execute(q, (host_id, location, description, img1_b64, img2_b64))
                conn.commit()
                st.success("✅ 숙소 정보가 저장되었습니다!")
                st.rerun()
            except Exception as e:
                st.error(f"오류: {e}")
            finally:
                conn.close()

        # 현재 등록된 사진 미리보기
        if existing is not None:
            st.markdown("---")
            st.markdown("**현재 등록된 사진**")
            cp1, cp2 = st.columns(2)
            with cp1: show_img(existing['image1'])
            with cp2: show_img(existing['image2'])

# ═══════════════════════════════════════
# TAB 3 — HOST: 입점 신청 / MASTER: 입점 전체 현황
# ═══════════════════════════════════════
with tab_list[3]:
    if is_master:
        st.subheader("🎁 전체 입점 현황")
        conn = database.get_db_connection()
        df_all_sp = pd.read_sql_query("""
            SELECT s.id, hb.name as 업체, hh.name as 호스트,
                   bi.item_name as 제품, s.qty as 수량, s.status as 상태, s.created_at as 일시
            FROM sponsorships s
            JOIN hosts hb ON s.brand_id=hb.id
            JOIN hosts hh ON s.host_id=hh.id
            JOIN brand_items bi ON s.brand_item_id=bi.id
            ORDER BY s.id DESC
        """, conn)
        conn.close()
        if df_all_sp.empty:
            st.info("입점 내역이 없습니다.")
        else:
            st.dataframe(df_all_sp.drop(columns=['id']), use_container_width=True, hide_index=True)
    else:
        # 호스트: 입점 신청 탭
        st.subheader("🎁 입점 신청")
        st.caption("입점업체가 등록한 제품을 확인하고 입점을 신청하세요. 체험 후 게스트에게 QR 주문을 유도할 수 있습니다.")

        conn = database.get_db_connection()
        df_all_items = pd.read_sql_query("""
            SELECT bi.id, h.name as brand_name, bi.item_name, bi.description, bi.stock_qty, bi.image
            FROM brand_items bi JOIN hosts h ON bi.brand_id=h.id
            WHERE bi.stock_qty > 0 ORDER BY bi.id DESC
        """, conn)
        conn.close()

        if df_all_items.empty:
            st.info("현재 입점 신청 가능한 제품이 없습니다.")
        else:
            # 카드형 UI
            for i in range(0, len(df_all_items), 2):
                row_data = df_all_items.iloc[i:i+2]
                cols = st.columns(2)
                for j, (_, item) in enumerate(row_data.iterrows()):
                    with cols[j]:
                        with st.container():
                            show_img(item['image'], width=240)
                            st.markdown(f"**{item['item_name']}**")
                            st.caption(f"🏷️ 공급업체: {item['brand_name']}")
                            st.caption(item['description'] or "")
                            st.markdown(f"📦 잔여 입점 수량: **{item['stock_qty']}개**")

                            key_prefix = f"apply_{item['id']}"
                            qty_key = f"{key_prefix}_qty"
                            btn_key = f"{key_prefix}_btn"

                            req_qty = st.number_input("신청 수량", min_value=1, max_value=int(item['stock_qty']), step=1, key=qty_key)
                            if st.button(f"🎁 입점 신청", key=btn_key, use_container_width=True, type="primary"):
                                conn2 = database.get_db_connection()
                                cursor2 = conn2.cursor()
                                try:
                                    q_dec = ('UPDATE brand_items SET stock_qty=stock_qty-%s WHERE id=%s'
                                             if database.DATABASE_URL else
                                             'UPDATE brand_items SET stock_qty=stock_qty-? WHERE id=?')
                                    cursor2.execute(q_dec, (req_qty, item['id']))
                                    q_ins = ('INSERT INTO sponsorships (brand_id,host_id,brand_item_id,qty,status) VALUES (%s,%s,%s,%s,%s)'
                                             if database.DATABASE_URL else
                                             'INSERT INTO sponsorships (brand_id,host_id,brand_item_id,qty,status) VALUES (?,?,?,?,?)')
                                    cursor2.execute(q_ins, (None, host_id, item['id'], req_qty, 'REQUESTED'))
                                    conn2.commit()
                                    st.success(f"✅ '{item['item_name']}' {req_qty}개 입점 신청 완료!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"오류: {e}")
                                finally:
                                    conn2.close()
                        st.markdown("")

        # 내가 신청한 입점 목록
        st.markdown("---")
        st.markdown("#### 📋 내 입점 신청 현황")
        conn = database.get_db_connection()
        q = ('SELECT bi.item_name as 제품, s.qty as 수량, s.status as 상태, s.created_at as 신청일시 FROM sponsorships s JOIN brand_items bi ON s.brand_item_id=bi.id WHERE s.host_id=%s ORDER BY s.id DESC'
             if database.DATABASE_URL else
             'SELECT bi.item_name as 제품, s.qty as 수량, s.status as 상태, s.created_at as 신청일시 FROM sponsorships s JOIN brand_items bi ON s.brand_item_id=bi.id WHERE s.host_id=? ORDER BY s.id DESC')
        df_my_sp = pd.read_sql_query(q, conn, params=(host_id,))
        conn.close()
        if df_my_sp.empty:
            st.info("신청한 입점이 없습니다.")
        else:
            st.dataframe(df_my_sp, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════
# MASTER ONLY: 사용자 관리 (TAB 4)
# ═══════════════════════════════════════
if is_master and len(tab_list) > 4:
    with tab_list[4]:
        st.subheader("👥 사용자 관리")
        conn = database.get_db_connection()
        df_users = pd.read_sql_query("SELECT id,username,name,role,is_master,email,phone,created_at FROM hosts ORDER BY id", conn)
        conn.close()
        st.dataframe(df_users, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════
# MASTER ONLY: 정산 대시보드 (TAB 5)
# ═══════════════════════════════════════
if is_master and len(tab_list) > 5:
    with tab_list[5]:
        st.title("💰 정산 관리 시스템")
        st.markdown("<p style='color:#888'>수익 구조: <b>(정가 - 판매가)의 50%</b>를 호스트와 플랫폼이 각각 배분</p>", unsafe_allow_html=True)
        conn = database.get_db_connection()
        date_func = "TO_CHAR(o.created_at,'MM/DD HH24:MI')" if database.DATABASE_URL else "strftime('%m/%d %H:%M',o.created_at)"
        q = f"""
            SELECT o.id, {date_func} as "일시", h.name as "호스트",
                   p.product_name as "상품", p.original_price as "정가", o.total_amount as "판매가", o.settlement_status as "상태"
            FROM orders o JOIN products p ON o.product_id=p.id
            JOIN hosts h ON p.owner_id=h.id ORDER BY o.id DESC
        """
        df_s = pd.read_sql_query(q, conn)
        if not df_s.empty:
            def calc_settlement(row, pct=0.5):
                gap = (row["정가"] - row["판매가"]) if row["정가"] and row["정가"] > row["판매가"] else 0
                return int(gap * pct)
            
            # 쿼리에 original_price 추가 필요
            df_s["플랫폼(50%)"] = df_s.apply(lambda r: calc_settlement(r, 0.5), axis=1)
            df_s["호스트(50%)"] = df_s.apply(lambda r: calc_settlement(r, 0.5), axis=1)
            pending_sale = df_s[df_s["상태"]=="PENDING"]["판매가"].sum()
            pending_platform = df_s[df_s["상태"]=="PENDING"]["플랫폼(50%)"].sum()
            pending_host = df_s[df_s["상태"]=="PENDING"]["호스트(50%)"].sum()
            
            c1,c2,c3 = st.columns(3)
            c1.metric("정산 대기 매출", f"{pending_sale:,}원")
            c2.metric("플랫폼 예상수익 (50%)", f"{pending_platform:,}원")
            c3.metric("호스트 지급예정 (50%)", f"{pending_host:,}원")
            st.markdown("---")
            st.dataframe(df_s.drop(columns=["id"]), use_container_width=True, hide_index=True)
            st.subheader("상태 업데이트")
            tid = st.selectbox("주문 ID", df_s["id"].tolist())
            nst = st.radio("변경 상태", ["PENDING","COMPLETED"], horizontal=True)
            if st.button("상태 반영 (Supabase 동기화)", type="primary"):
                curs = conn.cursor()
                q2 = ('UPDATE orders SET settlement_status=%s WHERE id=%s'
                      if database.DATABASE_URL else
                      'UPDATE orders SET settlement_status=? WHERE id=?')
                curs.execute(q2,(nst,tid))
                conn.commit()
                database.sync_order_to_supabase(tid)
                st.success(f"주문 #{tid} → {nst}")
                time.sleep(1)
                st.rerun()
        else:
            st.info("정산 데이터 없음")
        conn.close()

# ═══════════════════════════════════════
# MASTER ONLY: 문의사항 (TAB 6)
# ═══════════════════════════════════════
if is_master and len(tab_list) > 6:
    with tab_list[6]:
        st.subheader("📩 홈페이지 파트너 신청 문의사항")
        st.caption("랜딩 페이지의 '지금 시작하기' 단계별 폼을 통해 접수된 입점/호스트 문의 내역입니다.")
        
        conn = database.get_db_connection()
        date_func = "TO_CHAR(created_at,'YYYY-MM-DD HH24:MI')" if database.DATABASE_URL else "strftime('%Y-%m-%d %H:%M',created_at)"
        
        q_inq = f"""
            SELECT id, 
                   CASE WHEN inquiry_type='host' THEN '🏠 호스트' ELSE '🛍️ 브랜드' END as "구분",
                   name as "신청인 이름",
                   COALESCE(company_name, '') as "업체명",
                   contact as "연락처",
                   email as "이메일",
                   COALESCE(location, '') || COALESCE(platform, '') as "기타 정보",
                   COALESCE(category, '') as "카테고리",
                   message as "문의 세부내용",
                   {date_func} as "접수일시"
            FROM inquiries
            ORDER BY id DESC
        """
        
        try:
            df_inq = pd.read_sql_query(q_inq, conn)
            if df_inq.empty:
                st.info("새로 접수된 문의 내역이 없습니다.")
            else:
                st.dataframe(df_inq.drop(columns=['id']), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error("테이블 조회 오류 (DB가 갱신 중일 수 있습니다.)")
        finally:
            conn.close()
