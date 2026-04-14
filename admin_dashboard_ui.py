import streamlit as st
import pandas as pd
import uuid
import qrcode
from io import BytesIO
import database
import os
from message_automator import send_email_invitation, send_sms_invitation

# --- UI & 디자인 설정 (Host-Pro Portal v5) ---
st.set_page_config(
    page_title="Host Portal | Experience Platform",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 데이터베이스 초기화
database.init_db()

# --- 보안 설정 ---
ADMIN_PASSWORD = "admin1234"

def check_auth():
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    if st.session_state['authenticated']:
        return True
    
    st.markdown("""
        <div style='text-align: center; padding-top: 100px;'>
            <h1 style='font-weight: 200; font-size: 3rem;'>파트너 보안 로그인</h1>
            <p style='color: #888; letter-spacing: 0.1em; margin-bottom: 40px;'>AUTHORIZED PERSONNEL ONLY</p>
        </div>
    """, unsafe_allow_html=True)
    
    col_l, col_m, col_r = st.columns([1, 1, 1])
    with col_m:
        pw = st.text_input("접속 암호", type="password", key="auth_pw", label_visibility="collapsed")
        if st.button("포털 입장하기", use_container_width=True):
            if pw == ADMIN_PASSWORD:
                st.session_state['authenticated'] = True
                st.rerun()
            else:
                st.error("Access Denied.")
    return False

if not check_auth():
    st.stop()

# --- 고품질 CSS (Minoan SaaS 느낌 구현) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@200;400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
        color: #1A1A1A;
    }
    
    .stApp {
        background-color: #FAF9F6;
    }
    
    /* 카드 디자인 */
    div[data-testid="stVerticalBlock"] > div.element-container:has(div.stMarkdown > div.premium-card) {
        background: white;
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.03);
        border: 1px solid #F0EFEA;
        margin-bottom: 2rem;
    }
    
    .premium-card {
        padding: 0;
    }

    /* 메인 타이틀 */
    h1 {
        font-weight: 200 !important;
        letter-spacing: -0.05em;
        font-size: 3.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 30px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent !important;
        border: none !important;
        padding: 10px 0px;
        font-weight: 400;
        font-size: 14px;
        color: #888;
    }
    .stTabs [data-baseweb="tab-highlight"] {
        background-color: #1A1A1A;
    }
    
    /* 버튼 스타일 */
    .stButton>button {
        background-color: #1A1A1A;
        color: white;
        border-radius: 50px;
        border: none;
        padding: 0.6rem 2rem;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.1em;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #000;
        transform: translateY(-2px);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 상단 유틸리티 ---
def get_public_url(port):
    filename = f'public_url_{port}.txt'
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return f"http://localhost:{port}"

CHECKOUT_URL = get_public_url(8000)
ADMIN_URL = get_public_url(8501)

# --- 사이드바 ---
with st.sidebar:
    st.markdown("<h2 style='font-weight:700; letter-spacing:-0.05em;'>PLATFORM.</h2>", unsafe_allow_html=True)
    st.caption("호스트 관리 시스템")
    
    st.markdown("---")
    
    st.subheader("📡 네트워크 상태")
    if "trycloudflare" in CHECKOUT_URL:
        st.success("외부 연결 활성화됨")
        st.caption("공개 접속 주소:")
        st.code(CHECKOUT_URL, language=None)
    else:
        st.warning("로컬 모드")
    
    st.markdown("---")
    if st.button("로그아웃", use_container_width=True):
        st.session_state['authenticated'] = False
        st.rerun()

# --- 메인 화면 ---
st.title("호스트 대시보드")
st.markdown("<p style='color:#888; font-size:1.1rem;'>환영합니다. 숙소 쇼룸 제품 관리와 게스트 주문 현황을 한눈에 확인하세요.</p>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🛍️ 제품 및 쇼룸 관리", "📦 실시간 주문 현황", "💌 호스트 영입 도구"])

# ================================
# 탭 1: EXPERIENCES (상품 & QR)
# ================================
with tab1:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    col_input, col_list = st.columns([1.5, 2.5])
    
    with col_input:
        st.subheader("새 쇼룸 제품 등록")
        brand = st.text_input("브랜드명", placeholder="예: 이솝 (Aesop)")
        pname = st.text_input("제품명", placeholder="예: 레저렉션 핸드 워시")
        price = st.number_input("특별 공급가 (원)", min_value=0, step=1000, value=35000)
        
        if st.button("QR 쇼룸 생성하기", type="primary", use_container_width=True):
            if pname and price > 0:
                conn = database.get_db_connection()
                short_code = str(uuid.uuid4())[:6].upper()
                conn.execute(
                    'INSERT INTO products (brand_name, product_name, price, qr_code_id) VALUES (?, ?, ?, ?)',
                    (brand, pname, price, short_code)
                )
                conn.commit()
                conn.close()
                st.toast("Experience created successfully.")
            else:
                st.error("Please provide all product details.")
    
    with col_list:
        st.subheader("등록된 쇼룸 아이템")
        conn = database.get_db_connection()
        df_prod = pd.read_sql_query('''
            SELECT p.qr_code_id AS "코드", p.brand_name AS "브랜드", p.product_name AS "상품명", p.price AS "가격", COUNT(o.id) AS "누적판매"
            FROM products p LEFT JOIN orders o ON p.id = o.product_id
            GROUP BY p.id ORDER BY p.id DESC
        ''', conn)
        conn.close()
        
        st.dataframe(df_prod, use_container_width=True, hide_index=True)
        
        if not df_prod.empty:
            sel_code = st.selectbox("QR 코드를 확인할 아이템 선택", df_prod["코드"].tolist())
            qr_target = f"{CHECKOUT_URL}/buy/{sel_code}"
            
            qc1, qc2 = st.columns([1, 2])
            with qc1:
                qr = qrcode.QRCode(box_size=10, border=4)
                qr.add_data(qr_target)
                qr.make(fit=True)
                img = qr.make_image(fill_color="#1A1A1A", back_color="white")
                buf = BytesIO()
                img.save(buf, format="PNG")
                st.image(buf.getvalue(), width=150)
            with qc2:
                st.caption("QR 연결 주소")
                st.code(qr_target, language=None)
                st.download_button("QR 이미지 다운로드 (PNG)", buf.getvalue(), f"QR_{sel_code}.png", "image/png", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ================================
# 탭 2: ORDERS (주문 관리)
# ================================
with tab2:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.subheader("전체 주문 내역")
    conn = database.get_db_connection()
    df_orders = pd.read_sql_query('''
        SELECT strftime('%m/%d', o.created_at) AS "주문일", p.brand_name AS "브랜드", p.product_name AS "상품명", o.total_amount AS "결제액", o.customer_name AS "구매자", o.shipping_address AS "배송지"
        FROM orders o JOIN products p ON o.product_id = p.id ORDER BY o.id DESC
    ''', conn)
    conn.close()
    
    if df_orders.empty:
        st.info("아직 인입된 주문이 없습니다.")
    else:
        st.dataframe(df_orders, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ================================
# 탭 3: OUTREACH (영업 도구)
# ================================
with tab3:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.subheader("Host Partnership Outreach")
    st.caption("AI-optimized messaging for new host recruitment.")
    
    temp = st.selectbox("CHOOSE TEMPLATE", ["Curated Amenities Package", "Revenue Share Micro-bar"])
    msg = st.text_area("MESSAGE CONTENT", height=150, value="Hello Host. Upgrade your space for free with our curated amenities. Your guests experience them, you share the revenue.")
    
    r_col, l_col = st.columns([1, 1])
    with r_col:
        st.text_input("RECIPIENT", placeholder="email@address.com")
        if st.button("SEND PROPOSAL", use_container_width=True):
            st.toast("Proposal sent.")
    st.markdown("</div>", unsafe_allow_html=True)
