# AFFILISTAY Admin Dashboard UI - Redeploy 1
import streamlit as st
import re
import pandas as pd
import uuid
import qrcode
from datetime import timedelta
from io import BytesIO
import database
import os
import time
import httpx
import fcm_service

st.set_page_config(
    page_title="AffiliStay 파트너 센터",
    page_icon="🛋️",
    layout="wide",
    initial_sidebar_state="expanded"
)
# DB 초기화 (캐시 적용하여 서버 시작 시 1회만 실행)
@st.cache_resource
def initialize_platform():
    database.init_db()
    return True

initialize_platform()

CHECKOUT_BASE_URL = "https://affilistay-showroom.onrender.com"
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_VERIFY_SERVICE_SID = os.getenv("TWILIO_VERIFY_SERVICE_SID", "")
JUSO_API_KEY = os.getenv("JUSO_API_KEY", "")
PHONE_REGEX = re.compile(r"^01[016789]\d{7,8}$")
EMAIL_REGEX = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)
ROOM_MAP = {
    '거실': 'living_room',
    '침실': 'bedroom',
    '주방': 'kitchen',
    '화장실': 'bathroom',
}
ROOM_LABEL_MAP = {value: key for key, value in ROOM_MAP.items()}
ROOM_ICON_MAP = {
    'living_room': '🛋️',
    'bedroom': '🛏️',
    'kitchen': '🍳',
    'bathroom': '🛁',
}
PROD_CAT_OPTIONS = [
    ('🛋️ 가구', 'furniture'),
    ('🧶 패브릭', 'fabric'),
    ('📺 가전·디지털', 'appliance'),
    ('🍳 주방용품', 'kitchenware'),
    ('🥯 식품', 'food'),
    ('🪴 데코·식물', 'deco'),
    ('💡 조명', 'lighting'),
    ('📦 수납·정리', 'storage'),
    ('🛁 생활품', 'lifestyle'),
    ('🔌 헤어드라이어', 'hairdryer'),
]
PROD_CAT_MAP = dict(PROD_CAT_OPTIONS)
PROD_CAT_LABEL_MAP = {value: label for label, value in PROD_CAT_OPTIONS}
VENUE_IMAGE_KEYS = [f"image{i}" for i in range(1, 6)]

st.markdown(
    """
    <style>
    div[data-testid="stTabs"] button[role="tab"] {
        border-radius: 999px;
        padding: 0.6rem 0.95rem;
        font-weight: 700;
    }
    .host-hero {
        background: linear-gradient(135deg, rgba(255,88,88,0.92), rgba(255,154,84,0.92));
        border-radius: 28px;
        color: white;
        padding: 1.4rem 1.5rem;
        box-shadow: 0 20px 40px rgba(255, 100, 88, 0.18);
        margin-bottom: 1rem;
    }
    .host-hero-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.9rem;
        margin-top: 1rem;
    }
    .host-chip {
        border: 1px solid rgba(255,255,255,0.24);
        background: rgba(255,255,255,0.12);
        border-radius: 18px;
        padding: 0.95rem 1rem;
    }
    .host-chip-label {
        font-size: 0.8rem;
        opacity: 0.84;
        margin-bottom: 0.2rem;
    }
    .host-chip-value {
        font-size: 1.7rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }
    .section-card {
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 24px;
        padding: 1rem;
        background: rgba(255,255,255,0.02);
    }
    .section-title {
        font-size: 1rem;
        font-weight: 800;
        margin-bottom: 0.25rem;
    }
    .section-copy {
        color: rgba(250,250,250,0.65);
        font-size: 0.92rem;
        margin-bottom: 0.85rem;
    }
    .guide-card {
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 24px;
        padding: 1rem 1.05rem;
        background: rgba(255,255,255,0.025);
        margin-bottom: 0.9rem;
    }
    .guide-kicker {
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: rgba(255,255,255,0.62);
        margin-bottom: 0.45rem;
    }
    .guide-title {
        font-size: 1.08rem;
        font-weight: 800;
        margin-bottom: 0.35rem;
    }
    .guide-copy {
        font-size: 0.92rem;
        color: rgba(250,250,250,0.72);
        line-height: 1.6;
    }
    .guide-list {
        display: grid;
        gap: 0.55rem;
        margin-top: 0.8rem;
    }
    .guide-step {
        border-radius: 18px;
        padding: 0.8rem 0.9rem;
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.07);
    }
    .guide-step strong {
        display: block;
        font-size: 0.92rem;
        margin-bottom: 0.2rem;
    }
    .guide-step span {
        display: block;
        font-size: 0.84rem;
        line-height: 1.55;
        color: rgba(250,250,250,0.72);
    }
    @media (max-width: 900px) {
        .host-hero-grid {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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


def build_options_text(option_rows):
    return "\n".join(f"{name}: {values}" for name, values in option_rows)


def parse_option_lines(options_raw):
    option_lines = []
    for raw_line in options_raw.splitlines():
        if ":" not in raw_line:
            continue
        name, values = [piece.strip() for piece in raw_line.split(":", 1)]
        if name and values:
            option_lines.append((name, values))
    return option_lines


def replace_product_media(cursor, product_id, uploaded_files):
    if database.DATABASE_URL:
        cursor.execute("DELETE FROM product_images WHERE product_id=%s", (product_id,))
        insert_query = "INSERT INTO product_images (product_id, image_data, sort_order) VALUES (%s,%s,%s)"
    else:
        cursor.execute("DELETE FROM product_images WHERE product_id=?", (product_id,))
        insert_query = "INSERT INTO product_images (product_id, image_data, sort_order) VALUES (?,?,?)"

    for index, img_file in enumerate(uploaded_files):
        cursor.execute(insert_query, (product_id, database.file_to_base64(img_file), index))


def replace_product_options(cursor, product_id, options_raw):
    if database.DATABASE_URL:
        cursor.execute("DELETE FROM product_options WHERE product_id=%s", (product_id,))
        insert_query = 'INSERT INTO product_options (product_id, name, "values") VALUES (%s,%s,%s)'
    else:
        cursor.execute("DELETE FROM product_options WHERE product_id=?", (product_id,))
        insert_query = 'INSERT INTO product_options (product_id, name, "values") VALUES (?,?,?)'

    for name, values in parse_option_lines(options_raw):
        cursor.execute(insert_query, (product_id, name, values))


def calc_host_share(row):
    original_price = row.get('original_price') or row.get('price') or 0
    sale_price = row.get('price') or 0
    gap = max(int(original_price) - int(sale_price), 0)
    return int(gap * 0.5)


def load_host_income_snapshot(host_id):
    conn = database.get_db_connection()
    query = (
        """
        SELECT o.id, o.total_amount, o.created_at, o.payment_status, o.settlement_status,
               p.price, p.original_price
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE p.owner_id = %s
        ORDER BY o.created_at DESC
        """
        if database.DATABASE_URL else
        """
        SELECT o.id, o.total_amount, o.created_at, o.payment_status, o.settlement_status,
               p.price, p.original_price
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE p.owner_id = ?
        ORDER BY o.created_at DESC
        """
    )
    orders = pd.read_sql_query(query, conn, params=(host_id,))

    count_query = (
        "SELECT COUNT(*) AS count FROM products WHERE owner_id=%s"
        if database.DATABASE_URL else
        "SELECT COUNT(*) AS count FROM products WHERE owner_id=?"
    )
    live_products = int(pd.read_sql_query(count_query, conn, params=(host_id,)).iloc[0]["count"])
    conn.close()

    if orders.empty:
        return {
            "week_income": 0,
            "month_income": 0,
            "week_sales": 0,
            "month_sales": 0,
            "live_products": live_products,
            "order_count": 0,
        }

    orders["created_at"] = pd.to_datetime(orders["created_at"], errors="coerce")
    orders["host_share"] = orders.apply(calc_host_share, axis=1)

    now = pd.Timestamp.now(tz=None)
    week_cutoff = now - pd.Timedelta(days=7)
    month_cutoff = now - pd.Timedelta(days=30)
    weekly = orders[orders["created_at"] >= week_cutoff]
    monthly = orders[orders["created_at"] >= month_cutoff]

    return {
        "week_income": int(weekly["host_share"].sum()),
        "month_income": int(monthly["host_share"].sum()),
        "week_sales": int(weekly["total_amount"].sum()),
        "month_sales": int(monthly["total_amount"].sum()),
        "live_products": live_products,
        "order_count": int(len(orders)),
    }


def render_host_income_billboard(snapshot):
    st.markdown(
        f"""
        <div class="host-hero">
            <div style="font-size:0.82rem;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;opacity:0.88;">Host Momentum Board</div>
            <div style="font-size:1.95rem;font-weight:800;line-height:1.15;margin-top:0.45rem;">이번 주와 이번 달 수입 흐름을 한눈에 보세요.</div>
            <div style="opacity:0.9;margin-top:0.55rem;font-size:0.96rem;">숙소 운영 성과를 바로 확인하고, 인기 제품과 쇼룸 업데이트에 더 빠르게 반응할 수 있어요.</div>
            <div class="host-hero-grid">
                <div class="host-chip">
                    <div class="host-chip-label">주간 예상 수입</div>
                    <div class="host-chip-value">{snapshot['week_income']:,}원</div>
                    <div style="font-size:0.84rem;opacity:0.82;margin-top:0.3rem;">주간 판매 {snapshot['week_sales']:,}원</div>
                </div>
                <div class="host-chip">
                    <div class="host-chip-label">월간 예상 수입</div>
                    <div class="host-chip-value">{snapshot['month_income']:,}원</div>
                    <div style="font-size:0.84rem;opacity:0.82;margin-top:0.3rem;">월간 판매 {snapshot['month_sales']:,}원</div>
                </div>
                <div class="host-chip">
                    <div class="host-chip-label">운영 중인 상품 / 누적 주문</div>
                    <div class="host-chip-value">{snapshot['live_products']} / {snapshot['order_count']}</div>
                    <div style="font-size:0.84rem;opacity:0.82;margin-top:0.3rem;">상품을 손보면 쇼룸 전환도 더 좋아집니다.</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_b64_gallery(images, columns_count=5):
    images = [img for img in images if img]
    if not images:
        st.caption("아직 등록된 이미지가 없습니다.")
        return
    for start in range(0, len(images), columns_count):
        cols = st.columns(columns_count)
        for col, image in zip(cols, images[start:start + columns_count]):
            with col:
                show_img(image, width=120)


def render_host_upload_guide(mode):
    if mode == "create":
        st.markdown(
            """
            <div class="guide-card">
                <div class="guide-kicker">Upload flow</div>
                <div class="guide-title">오늘의집처럼 단계별로 올리면 덜 헷갈려요.</div>
                <div class="guide-copy">이미지, 기본 정보, 가격과 공간, 상세 설명 순서로 채우면 쇼룸 완성도가 가장 빠르게 올라갑니다.</div>
                <div class="guide-list">
                    <div class="guide-step">
                        <strong>1. 대표 이미지부터 고르기</strong>
                        <span>첫 이미지는 고객 화면의 대표 카드로 바로 노출됩니다. 밝고 용도가 잘 보이는 컷이 좋아요.</span>
                    </div>
                    <div class="guide-step">
                        <strong>2. 공간과 카테고리 맞추기</strong>
                        <span>거실·침실 같은 배치 공간과 품목 카테고리를 함께 맞춰 두면 카탈로그에서 바로 찾기 쉬워집니다.</span>
                    </div>
                    <div class="guide-step">
                        <strong>3. 상세 설명은 짧고 분명하게</strong>
                        <span>소재, 사용감, 추천 포인트를 고객 언어로 정리해 두면 전환이 좋아집니다.</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="guide-card">
                <div class="guide-kicker">Editing flow</div>
                <div class="guide-title">변경 즉시 쇼룸이 새 정보를 감지합니다.</div>
                <div class="guide-copy">제품명, 대표 이미지, 한줄 설명, 상세 설명을 손보면 고객 페이지가 자동으로 새 정보를 불러옵니다.</div>
                <div class="guide-list">
                    <div class="guide-step">
                        <strong>대표 이미지 교체</strong>
                        <span>새 갤러리를 올리면 기존 이미지가 한 번에 교체됩니다. 첫 이미지가 대표로 사용됩니다.</span>
                    </div>
                    <div class="guide-step">
                        <strong>가격과 옵션 정리</strong>
                        <span>정가와 판매가를 함께 맞춰 두고, 옵션은 줄바꿈으로 정리하면 고객이 선택하기 쉬워져요.</span>
                    </div>
                    <div class="guide-step">
                        <strong>쇼룸 반영 확인</strong>
                        <span>저장 후 퍼블릭 페이지에서 새로고침 버튼 없이도 몇 초 안에 변경사항이 반영됩니다.</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_product_summary_metrics(df_products, gallery_map):
    total_products = int(len(df_products))
    detailed_ready = 0
    gallery_ready = 0
    room_mix = set()
    for _, product in df_products.iterrows():
        if (product.get("detailed_description") or "").strip():
            detailed_ready += 1
        if len(gallery_map.get(int(product["id"]), [])) >= 2:
            gallery_ready += 1
        if product.get("room_category"):
            room_mix.add(product.get("room_category"))

    c1, c2, c3 = st.columns(3)
    c1.metric("등록 상품", f"{total_products}개")
    c2.metric("상세 설명 완성", f"{detailed_ready}개")
    c3.metric("다중 이미지 적용", f"{gallery_ready}개")
    st.caption(f"현재 {len(room_mix)}개 공간 카테고리에 제품이 배치되어 있어요.")


def normalize_phone(raw_phone):
    digits = re.sub(r"\D", "", raw_phone or "")
    if not PHONE_REGEX.fullmatch(digits):
        return None
    return digits


def format_phone_display(raw_phone):
    digits = normalize_phone(raw_phone)
    if not digits:
        return raw_phone
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"


def to_e164_kr(raw_phone):
    digits = normalize_phone(raw_phone)
    if not digits:
        return None
    return f"+82{digits[1:]}"


def is_valid_email(email):
    return bool(EMAIL_REGEX.fullmatch((email or "").strip()))


def signup_address_label(role):
    if role == "HOST":
        return "숙소 주소"
    if role == "BRAND":
        return "판매시설 주소"
    return "주소"


def send_phone_verification(phone_e164):
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_VERIFY_SERVICE_SID):
        return False, "휴대폰 인증을 사용하려면 Twilio Verify 환경변수를 먼저 설정해 주세요."

    try:
        response = httpx.post(
            f"https://verify.twilio.com/v2/Services/{TWILIO_VERIFY_SERVICE_SID}/Verifications",
            data={"To": phone_e164, "Channel": "sms"},
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=12.0,
        )
        data = response.json()
        if response.is_success:
            return True, "인증번호를 전송했습니다. 문자로 받은 코드를 입력해 주세요."
        return False, data.get("message", "인증번호 전송에 실패했습니다.")
    except Exception as exc:
        return False, f"인증번호 전송 중 오류가 발생했습니다: {exc}"


def verify_phone_code(phone_e164, code):
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_VERIFY_SERVICE_SID):
        return False, "휴대폰 인증 환경변수가 설정되지 않았습니다."

    try:
        response = httpx.post(
            f"https://verify.twilio.com/v2/Services/{TWILIO_VERIFY_SERVICE_SID}/VerificationCheck",
            data={"To": phone_e164, "Code": (code or "").strip()},
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=12.0,
        )
        data = response.json()
        if response.is_success and data.get("status") == "approved":
            return True, "휴대폰 인증이 완료되었습니다."
        return False, data.get("message", "인증번호가 올바르지 않습니다.")
    except Exception as exc:
        return False, f"인증 확인 중 오류가 발생했습니다: {exc}"


def search_road_addresses(keyword):
    if not JUSO_API_KEY:
        return [], "도로명 주소 검색을 사용하려면 JUSO_API_KEY 환경변수를 설정해 주세요."

    try:
        response = httpx.get(
            "https://business.juso.go.kr/addrlink/addrLinkApi.do",
            params={
                "confmKey": JUSO_API_KEY,
                "currentPage": 1,
                "countPerPage": 7,
                "keyword": keyword,
                "resultType": "json",
            },
            timeout=12.0,
        )
        data = response.json()
        common = data.get("results", {}).get("common", {})
        if common.get("errorCode") not in (None, "0"):
            return [], common.get("errorMessage", "주소 검색 결과를 불러오지 못했습니다.")
        results = data.get("results", {}).get("juso", [])
        return results, ""
    except Exception as exc:
        return [], f"주소 검색 중 오류가 발생했습니다: {exc}"


def format_address_option(address_row):
    road = address_row.get("roadAddrPart1") or address_row.get("roadAddr") or ""
    detail_hint = address_row.get("bdNm") or address_row.get("detBdNmList") or ""
    zip_code = address_row.get("zipNo") or ""
    suffix = f" · {detail_hint}" if detail_hint else ""
    return f"[{zip_code}] {road}{suffix}"


def sync_signup_address_selection(results, selected_index):
    if results and 0 <= selected_index < len(results):
        selected = results[selected_index]
        st.session_state["signup_address_road"] = selected.get("roadAddrPart1") or selected.get("roadAddr") or ""
        st.session_state["signup_postal_code"] = selected.get("zipNo") or ""


def reset_signup_phone_verification():
    st.session_state["signup_phone_verified"] = False
    st.session_state["signup_verified_phone"] = ""
    st.session_state["signup_verification_sent"] = False
    st.session_state["signup_verification_target"] = ""
    st.session_state["signup_verification_code"] = ""

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
            signup_defaults = {
                "signup_phone_verified": False,
                "signup_verified_phone": "",
                "signup_verification_sent": False,
                "signup_verification_target": "",
                "signup_verification_code": "",
                "signup_address_results": [],
                "signup_address_choice": 0,
                "signup_address_road": "",
                "signup_address_detail": "",
                "signup_postal_code": "",
            }
            for key, default in signup_defaults.items():
                if key not in st.session_state:
                    st.session_state[key] = default

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
            phone = st.text_input("휴대폰 번호", placeholder="010-1234-5678")
            st.caption("회원가입은 휴대폰 인증 완료 후 진행됩니다.")
            if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_VERIFY_SERVICE_SID):
                st.info("운영 환경에서 Twilio Verify 키를 설정하면 문자 인증이 바로 활성화됩니다.")
            normalized_phone = normalize_phone(phone)
            verified_phone = st.session_state.get("signup_verified_phone")
            verification_target = st.session_state.get("signup_verification_target")
            if verified_phone and normalized_phone != verified_phone:
                reset_signup_phone_verification()
            elif st.session_state.get("signup_verification_sent") and verification_target and normalized_phone != verification_target:
                reset_signup_phone_verification()

            send_col, verify_col = st.columns([1, 1])
            with send_col:
                if st.button("인증번호 보내기", use_container_width=True):
                    if not normalized_phone:
                        st.error("휴대폰 번호는 010-1234-5678 형식으로 입력해 주세요.")
                    else:
                        sent, message = send_phone_verification(to_e164_kr(phone))
                        if sent:
                            st.session_state["signup_verification_sent"] = True
                            st.session_state["signup_verification_target"] = normalized_phone
                            st.success(message)
                        else:
                            st.error(message)

            if st.session_state.get("signup_verification_sent") and st.session_state.get("signup_verification_target") == normalized_phone:
                verification_code = st.text_input("인증번호", key="signup_verification_code", placeholder="문자로 받은 6자리 인증번호")
                with verify_col:
                    if st.button("인증 확인", use_container_width=True):
                        if not verification_code.strip():
                            st.error("인증번호를 입력해 주세요.")
                        else:
                            verified, message = verify_phone_code(to_e164_kr(phone), verification_code)
                            if verified:
                                st.session_state["signup_phone_verified"] = True
                                st.session_state["signup_verified_phone"] = normalized_phone
                                st.success(message)
                            else:
                                st.error(message)

            if st.session_state.get("signup_phone_verified") and st.session_state.get("signup_verified_phone") == normalized_phone:
                st.success(f"휴대폰 인증 완료: {format_phone_display(phone)}")

            email = st.text_input("이메일", placeholder="name@example.com")
            if email and not is_valid_email(email):
                st.caption("이메일은 name@example.com 형식으로 입력해 주세요.")

            if actual_role in {"HOST", "BRAND"}:
                st.markdown("##### 주소 입력")
                if not JUSO_API_KEY:
                    st.info("JUSO_API_KEY를 설정하면 도로명 주소 검색 결과를 바로 선택할 수 있습니다. 지금도 직접 입력은 가능합니다.")
                address_keyword = st.text_input("도로명 주소 검색", placeholder="예: 마포구 양화로 45")
                if st.button("주소 검색", use_container_width=True):
                    if not address_keyword.strip():
                        st.error("검색할 도로명 주소를 입력해 주세요.")
                    else:
                        results, message = search_road_addresses(address_keyword.strip())
                        st.session_state["signup_address_results"] = results
                        st.session_state["signup_address_choice"] = 0
                        if results:
                            sync_signup_address_selection(results, 0)
                            st.success("검색 결과를 불러왔습니다. 아래에서 정확한 주소를 선택해 주세요.")
                        else:
                            st.warning(message or "검색 결과가 없습니다. 도로명, 건물명으로 다시 검색해 주세요.")

                address_results = st.session_state.get("signup_address_results", [])
                if address_results:
                    selected_index = st.selectbox(
                        "검색 결과",
                        options=list(range(len(address_results))),
                        format_func=lambda idx: format_address_option(address_results[idx]),
                        key="signup_address_choice",
                    )
                    sync_signup_address_selection(address_results, selected_index)

                st.text_input(
                    signup_address_label(actual_role),
                    key="signup_address_road",
                    placeholder="검색 결과를 선택하거나 도로명 주소를 직접 입력해 주세요.",
                )
                st.text_input("상세 주소", key="signup_address_detail", placeholder="동/호수, 층수 등을 입력해 주세요.")
                st.text_input("우편번호", key="signup_postal_code", placeholder="주소 검색 시 자동 입력됩니다.")

            signup_path = st.selectbox("가입 경로", ["SNS", "지인소개", "검색", "광고", "기타"])
            new_username = st.text_input("사용할 아이디")
            new_password = st.text_input("비밀번호", type="password")

            if st.button("가입 신청", use_container_width=True, type="primary"):
                if not full_name.strip():
                    st.error("이름 또는 업체명을 입력해 주세요.")
                elif not normalized_phone:
                    st.error("휴대폰 번호 형식을 다시 확인해 주세요.")
                elif not (st.session_state.get("signup_phone_verified") and st.session_state.get("signup_verified_phone") == normalized_phone):
                    st.error("회원가입 전에 휴대폰 인증을 완료해 주세요.")
                elif not is_valid_email(email):
                    st.error("이메일 형식을 올바르게 입력해 주세요.")
                elif actual_role in {"HOST", "BRAND"} and not st.session_state.get("signup_address_road", "").strip():
                    st.error(f"{signup_address_label(actual_role)}를 입력해 주세요.")
                elif not new_username.strip() or not new_password.strip():
                    st.error("아이디와 비밀번호를 모두 입력해 주세요.")
                else:
                    conn = database.get_db_connection()
                    cursor = conn.cursor()
                    verified_at = pd.Timestamp.now(tz=None).strftime("%Y-%m-%d %H:%M:%S")
                    formatted_phone = format_phone_display(phone)
                    address_road = st.session_state.get("signup_address_road", "").strip()
                    address_detail = st.session_state.get("signup_address_detail", "").strip()
                    postal_code = st.session_state.get("signup_postal_code", "").strip()
                    try:
                        q = (
                            'INSERT INTO hosts (username,password,name,phone,email,address_road,address_detail,postal_code,phone_verified,phone_verified_at,signup_path,role,is_master) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id'
                            if database.DATABASE_URL else
                            'INSERT INTO hosts (username,password,name,phone,email,address_road,address_detail,postal_code,phone_verified,phone_verified_at,signup_path,role,is_master) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)'
                        )
                        cursor.execute(
                            q,
                            (
                                new_username.strip(),
                                new_password,
                                full_name.strip(),
                                formatted_phone,
                                email.strip().lower(),
                                address_road or None,
                                address_detail or None,
                                postal_code or None,
                                True,
                                verified_at,
                                signup_path,
                                actual_role,
                                False,
                            ),
                        )
                        new_host_id = cursor.fetchone()[0] if database.DATABASE_URL else cursor.lastrowid

                        if actual_role == "HOST" and address_road:
                            venue_location = " ".join(piece for piece in [address_road, address_detail] if piece).strip()
                            venue_query = (
                                "INSERT INTO host_venues (host_id, location, description) VALUES (%s,%s,%s) ON CONFLICT (host_id) DO NOTHING"
                                if database.DATABASE_URL else
                                "INSERT OR IGNORE INTO host_venues (host_id, location, description) VALUES (?,?,?)"
                            )
                            cursor.execute(venue_query, (new_host_id, venue_location, None))

                        conn.commit()
                        reset_signup_phone_verification()
                        st.session_state["signup_address_results"] = []
                        st.session_state["signup_address_road"] = ""
                        st.session_state["signup_address_detail"] = ""
                        st.session_state["signup_postal_code"] = ""
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
    current_role = st.session_state.get('role')
    if current_role == 'HOST' and not is_master:
        render_host_income_billboard(load_host_income_snapshot(host_id))
    conn = database.get_db_connection()
    if is_master:
        product_query = """
            SELECT p.*, h.name as owner
            FROM products p
            LEFT JOIN hosts h ON p.owner_id = h.id
            ORDER BY p.id DESC
        """
        df_p = pd.read_sql_query(product_query, conn)
    else:
        product_query = (
            """
            SELECT p.*
            FROM products p
            WHERE p.owner_id=%s
            ORDER BY p.id DESC
            """
            if database.DATABASE_URL else
            """
            SELECT p.*
            FROM products p
            WHERE p.owner_id=?
            ORDER BY p.id DESC
            """
        )
        df_p = pd.read_sql_query(product_query, conn, params=(host_id,))

    gallery_map = {}
    option_map = {}
    for product_id in df_p['id'].tolist() if not df_p.empty else []:
        gallery_images = []
        for image in [df_p[df_p['id'] == product_id].iloc[0].get('image_url')] + database.fetch_product_images(conn, product_id):
            if image and image not in gallery_images:
                gallery_images.append(image)
        gallery_map[product_id] = gallery_images
        option_map[product_id] = build_options_text(database.fetch_product_options(conn, product_id))
    conn.close()
    workspace_mode = st.radio(
        "상품 작업 모드",
        ["신규 상품 등록", "기존 상품 수정"],
        horizontal=True,
        key=f"product_workspace_{host_id}_{'master' if is_master else 'host'}",
        label_visibility="collapsed",
    )

    if workspace_mode == "신규 상품 등록":
        left, right = st.columns([1.45, 0.85], gap="large")
        with left:
            with st.container(border=True):
                st.markdown("#### 🛍️ 새 쇼룸 상품 등록")
                st.caption("이미지부터 상세 소개까지 한 화면에서 정리하고 저장 즉시 쇼룸에 반영하세요.")
                with st.form(f"product_register_form_{host_id}", clear_on_submit=True):
                    st.markdown("##### 1. 대표 이미지와 갤러리")
                    prod_images = st.file_uploader(
                        "제품 이미지 업로드",
                        type=["jpg", "jpeg", "png", "webp"],
                        accept_multiple_files=True,
                        help="첫 이미지가 대표 이미지로 노출됩니다.",
                    )
                    st.caption("대표 이미지는 밝고 제품 전체가 잘 보이는 컷이 가장 좋아요.")

                    st.markdown("##### 2. 기본 정보")
                    info_left, info_right = st.columns(2)
                    with info_left:
                        brand_name = st.text_input("브랜드명 *")
                        product_name = st.text_input("제품명 *")
                        prod_description = st.text_input("리스트 한줄 설명", placeholder="예: 체크인 직후 눈길을 끄는 무드등")
                    with info_right:
                        room_label = st.selectbox("배치 공간 *", list(ROOM_MAP.keys()))
                        prod_cat_label = st.selectbox("품목 카테고리 *", list(PROD_CAT_MAP.keys()))
                        original_price = st.number_input("정가 *", min_value=0, step=1000, format="%d")

                    st.markdown("##### 3. 가격과 쇼룸 배치")
                    price_cols = st.columns([1, 1])
                    with price_cols[0]:
                        price = st.number_input("판매가 *", min_value=0, step=1000, format="%d")
                    with price_cols[1]:
                        st.markdown("**현재 배치 기준**")
                        st.caption("위에서 선택한 공간과 카테고리가 바로 카탈로그 필터에 반영됩니다.")

                    st.markdown("##### 4. 상세 소개와 옵션")
                    detailed_description = st.text_area(
                        "상세 설명",
                        placeholder="소재, 사용감, 추천 포인트를 고객이 읽기 쉽게 적어주세요.",
                        height=160,
                    )
                    options_raw = st.text_area(
                        "옵션",
                        placeholder="예: 색상: 화이트, 블랙\n사이즈: S, M, L",
                        height=100,
                    )
                    submitted = st.form_submit_button("🎯 상품 저장하고 QR 만들기", use_container_width=True, type="primary")

            if submitted:
                if not brand_name or not product_name or price <= 0 or not prod_images:
                    st.error("브랜드명, 제품명, 판매가, 대표 이미지는 꼭 입력해 주세요.")
                else:
                    qr_id = str(uuid.uuid4())[:12]
                    url = f"{CHECKOUT_BASE_URL}/shop/{qr_id}"
                    main_img_b64 = database.file_to_base64(prod_images[0])
                    conn_save = database.get_db_connection()
                    try:
                        cursor = conn_save.cursor()
                        insert_query = (
                            'INSERT INTO products (brand_name,product_name,price,original_price,qr_code_id,owner_id,room_category,product_category,description,detailed_description,image_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id'
                            if database.DATABASE_URL else
                            'INSERT INTO products (brand_name,product_name,price,original_price,qr_code_id,owner_id,room_category,product_category,description,detailed_description,image_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)'
                        )
                        cursor.execute(
                            insert_query,
                            (
                                brand_name,
                                product_name,
                                price,
                                original_price or price,
                                qr_id,
                                host_id,
                                ROOM_MAP[room_label],
                                PROD_CAT_MAP[prod_cat_label],
                                prod_description or None,
                                detailed_description or None,
                                main_img_b64,
                            ),
                        )
                        new_product_id = cursor.fetchone()[0] if database.DATABASE_URL else cursor.lastrowid
                        replace_product_media(cursor, new_product_id, prod_images)
                        replace_product_options(cursor, new_product_id, options_raw)
                        database.bump_public_content_version(conn_save)
                        conn_save.commit()
                        st.success(f"✅ '{product_name}' 등록이 완료됐어요. 쇼룸도 자동 반영을 시작합니다.")
                        qr_buffer = make_qr(url)
                        q1, q2 = st.columns([1, 2])
                        with q1:
                            st.image(qr_buffer, width=180)
                            qr_buffer.seek(0)
                            st.download_button("📥 QR 다운로드", qr_buffer, f"QR_{product_name}.png", "image/png", use_container_width=True)
                        with q2:
                            st.code(url, language=None)
                    except Exception as e:
                        st.error(f"오류: {e}")
                    finally:
                        conn_save.close()

        with right:
            render_host_upload_guide("create")
            with st.container(border=True):
                st.markdown("#### 바로 반영되는 항목")
                st.caption("저장 직후 고객 페이지가 새 정보를 감지하는 핵심 항목입니다.")
                st.markdown("- 대표 이미지\n- 제품명과 한줄 설명\n- 공간 배치와 카테고리\n- 상세 설명과 옵션")
    else:
        st.subheader("🛠️ 등록된 상품 관리")
        if df_p.empty:
            st.info("등록된 제품이 없습니다. 먼저 신규 상품을 올려 주세요.")
            return

        render_product_summary_metrics(df_p, gallery_map)
        search_col, room_col = st.columns([1.9, 1])
        search_query = search_col.text_input(
            "상품 검색",
            placeholder="제품명 또는 브랜드명을 입력해 빠르게 찾으세요.",
            key=f"product_search_{host_id}_{'master' if is_master else 'host'}",
        )
        room_filter = room_col.selectbox(
            "공간 필터",
            ["전체"] + list(ROOM_MAP.keys()),
            key=f"product_room_filter_{host_id}_{'master' if is_master else 'host'}",
        )
        filtered_df = df_p.copy()
        if search_query:
            mask = (
                filtered_df["product_name"].fillna("").str.contains(search_query, case=False) |
                filtered_df["brand_name"].fillna("").str.contains(search_query, case=False)
            )
            filtered_df = filtered_df[mask]
        if room_filter != "전체":
            filtered_df = filtered_df[filtered_df["room_category"] == ROOM_MAP[room_filter]]

        guide_left, guide_right = st.columns([1.4, 0.9], gap="large")
        with guide_right:
            render_host_upload_guide("edit")
        with guide_left:
            if filtered_df.empty:
                st.info("조건에 맞는 상품이 아직 없습니다. 검색어나 공간 필터를 바꿔 보세요.")
            else:
                for index, (_, product) in enumerate(filtered_df.iterrows()):
                    product_id = int(product['id'])
                    room_value = product.get('room_category') or 'living_room'
                    category_value = product.get('product_category') or 'lifestyle'
                    gallery_images = gallery_map.get(product_id, [])
                    option_text = option_map.get(product_id, "")
                    badge_text = f"{ROOM_ICON_MAP.get(room_value, '🏠')} {ROOM_LABEL_MAP.get(room_value, room_value)} · {PROD_CAT_LABEL_MAP.get(category_value, category_value)}"

                    with st.expander(f"{product['product_name']}  ·  {badge_text}", expanded=index == 0):
                        top_left, top_right = st.columns([0.95, 1.55], gap="large")
                        with top_left:
                            show_img(gallery_images[0] if gallery_images else product.get('image_url'), width=240)
                            st.caption("현재 등록된 갤러리")
                            render_b64_gallery(gallery_images[:5], columns_count=min(5, max(len(gallery_images[:5]), 1)))
                            qr_url = f"{CHECKOUT_BASE_URL}/shop/{product['qr_code_id']}"
                            qr_buffer = make_qr(qr_url)
                            st.code(qr_url, language=None)
                            qr_buffer.seek(0)
                            st.download_button(
                                "📥 이 상품 QR 다운로드",
                                qr_buffer,
                                f"QR_{product['product_name']}.png",
                                "image/png",
                                key=f"product_qr_{product_id}",
                                use_container_width=True,
                            )

                        with top_right:
                            st.markdown(f"**상품 ID #{product_id}**")
                            meta1, meta2, meta3 = st.columns(3)
                            meta1.metric("판매가", f"{int(product['price']):,}원")
                            meta2.metric("정가", f"{int((product['original_price'] or product['price'])):,}원")
                            meta3.metric("할인율", f"{int(max((product['original_price'] or product['price']) - product['price'], 0) / max((product['original_price'] or product['price']), 1) * 100)}%")

                            with st.form(f"product_edit_form_{product_id}"):
                                st.markdown("##### 쇼룸에 보이는 기본 정보")
                                e1, e2 = st.columns(2)
                                with e1:
                                    edit_brand = st.text_input("브랜드명", value=product['brand_name'], key=f"brand_{product_id}")
                                    edit_name = st.text_input("제품명", value=product['product_name'], key=f"name_{product_id}")
                                    edit_description = st.text_input("리스트 한줄 설명", value=product.get('description') or "", key=f"desc_{product_id}")
                                with e2:
                                    edit_room = st.selectbox(
                                        "배치 공간",
                                        list(ROOM_MAP.keys()),
                                        index=list(ROOM_MAP.values()).index(room_value) if room_value in ROOM_MAP.values() else 0,
                                        key=f"room_{product_id}",
                                    )
                                    edit_category = st.selectbox(
                                        "품목 카테고리",
                                        list(PROD_CAT_MAP.keys()),
                                        index=list(PROD_CAT_MAP.values()).index(category_value) if category_value in PROD_CAT_MAP.values() else 0,
                                        key=f"category_{product_id}",
                                    )
                                    replacement_images = st.file_uploader(
                                        "새 갤러리 이미지 (업로드 시 기존 이미지 전체 교체)",
                                        type=["jpg", "jpeg", "png", "webp"],
                                        accept_multiple_files=True,
                                        key=f"gallery_{product_id}",
                                    )

                                st.markdown("##### 가격과 상세 소개")
                                price_left, price_right = st.columns(2)
                                with price_left:
                                    edit_original_price = st.number_input(
                                        "정가",
                                        min_value=0,
                                        step=1000,
                                        format="%d",
                                        value=int(product['original_price'] or product['price']),
                                        key=f"origin_{product_id}",
                                    )
                                with price_right:
                                    edit_price = st.number_input(
                                        "판매가",
                                        min_value=0,
                                        step=1000,
                                        format="%d",
                                        value=int(product['price']),
                                        key=f"price_{product_id}",
                                    )

                                edit_detailed_description = st.text_area(
                                    "상세 설명",
                                    value=product.get('detailed_description') or "",
                                    height=160,
                                    key=f"detail_{product_id}",
                                )
                                edit_options_raw = st.text_area(
                                    "옵션",
                                    value=option_text,
                                    height=100,
                                    key=f"options_{product_id}",
                                )
                                save_product = st.form_submit_button("💾 변경 저장하고 쇼룸 반영", use_container_width=True, type="primary")

                            if save_product:
                                if not edit_brand or not edit_name or edit_price <= 0:
                                    st.error("브랜드명, 제품명, 판매가는 비워둘 수 없습니다.")
                                else:
                                    conn_edit = database.get_db_connection()
                                    cursor = conn_edit.cursor()
                                    try:
                                        next_main_image = product.get('image_url')
                                        if replacement_images:
                                            next_main_image = database.file_to_base64(replacement_images[0])

                                        update_query = (
                                            """
                                            UPDATE products
                                            SET brand_name=%s, product_name=%s, price=%s, original_price=%s,
                                                room_category=%s, product_category=%s, description=%s,
                                                detailed_description=%s, image_url=%s
                                            WHERE id=%s
                                            """
                                            if database.DATABASE_URL else
                                            """
                                            UPDATE products
                                            SET brand_name=?, product_name=?, price=?, original_price=?,
                                                room_category=?, product_category=?, description=?,
                                                detailed_description=?, image_url=?
                                            WHERE id=?
                                            """
                                        )
                                        cursor.execute(
                                            update_query,
                                            (
                                                edit_brand,
                                                edit_name,
                                                edit_price,
                                                edit_original_price or edit_price,
                                                ROOM_MAP[edit_room],
                                                PROD_CAT_MAP[edit_category],
                                                edit_description or None,
                                                edit_detailed_description or None,
                                                next_main_image,
                                                product_id,
                                            ),
                                        )
                                        if replacement_images:
                                            replace_product_media(cursor, product_id, replacement_images)
                                        replace_product_options(cursor, product_id, edit_options_raw)
                                        database.bump_public_content_version(conn_edit)
                                        conn_edit.commit()
                                        st.success(f"✅ '{edit_name}' 정보가 저장되었습니다. 고객 페이지도 자동 업데이트를 감지합니다.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"오류: {e}")
                                    finally:
                                        conn_edit.close()

def render_tab_orders(host_id, is_master):
    st.subheader("📦 주문 현황")
    conn = database.get_db_connection()
    if is_master:
        df_o = pd.read_sql_query("""
            SELECT o.id, o.customer_name, o.phone_number, o.shipping_address, o.delivery_note, 
                   p.product_name, p.brand_name, o.total_amount, o.currency, o.exchange_rate,
                   o.paypal_order_id, o.payment_status, o.settlement_status, o.shipping_status, o.fcm_token, o.created_at 
            FROM orders o JOIN products p ON o.product_id = p.id 
            ORDER BY o.id DESC
        """, conn)
    else:
        q = ('''
            SELECT o.id, o.customer_name, o.phone_number, o.shipping_address, o.delivery_note, 
                   p.product_name, o.total_amount, o.currency, o.exchange_rate,
                   o.paypal_order_id, o.payment_status, o.settlement_status, o.shipping_status, o.fcm_token, o.created_at 
            FROM orders o JOIN products p ON o.product_id = p.id 
            WHERE p.owner_id = %s ORDER BY o.id DESC
        ''' if database.DATABASE_URL else '''
            SELECT o.id, o.customer_name, o.phone_number, o.shipping_address, o.delivery_note, 
                   p.product_name, o.total_amount, o.currency, o.exchange_rate,
                   o.paypal_order_id, o.payment_status, o.settlement_status, o.shipping_status, o.fcm_token, o.created_at 
            FROM orders o JOIN products p ON o.product_id = p.id 
            WHERE p.owner_id = ? ORDER BY o.id DESC
        ''')
        df_o = pd.read_sql_query(q, conn, params=(host_id,))
    conn.close()
    if df_o.empty:
        st.info("아직 고객 주문이 없습니다.")
    else:
        # 가독성 개선
        df_o['total_amount'] = df_o.apply(lambda x: f"{x['total_amount']:,}원 ({x['currency']})", axis=1)
        st.dataframe(df_o.drop(columns=['fcm_token']), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("#### 🚚 배송 상태 업데이트 및 알림톡(푸시) 발송")
        
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            selected_order_id = st.selectbox("주문 선택", df_o['id'].tolist(), 
                                             format_func=lambda x: f"주문 #{x} - {df_o[df_o['id']==x]['customer_name'].values[0]}")
        with c2:
            current_status = df_o[df_o['id']==selected_order_id]['shipping_status'].values[0]
            new_status = st.selectbox("상태 변경", ["PREPARING", "SHIPPED", "DELIVERED"], 
                                      index=["PREPARING", "SHIPPED", "DELIVERED"].index(current_status) if current_status in ["PREPARING", "SHIPPED", "DELIVERED"] else 0)
        with c3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("상태 업데이트 및 알림 전송", use_container_width=True, type="primary"):
                conn2 = database.get_db_connection()
                curs = conn2.cursor()
                q_up = ('UPDATE orders SET shipping_status=%s WHERE id=%s'
                        if database.DATABASE_URL else
                        'UPDATE orders SET shipping_status=? WHERE id=?')
                curs.execute(q_up, (new_status, selected_order_id))
                conn2.commit()
                conn2.close()
                
                # 푸시 알림 전송 (SHIPPED 로 변경 시)
                if new_status == "SHIPPED" and current_status != "SHIPPED":
                    fcm_token = df_o[df_o['id']==selected_order_id]['fcm_token'].values[0]
                    if fcm_token:
                        success = fcm_service.send_push_notification(
                            token=fcm_token,
                            title="배송 시작 안내",
                            body=f"고객님의 주문(#{selected_order_id}) 상품이 배송을 시작했습니다. 곧 도착할 예정입니다!",
                            data={"order_id": str(selected_order_id), "type": "shipping_started"}
                        )
                        if success:
                            st.success(f"주문 #{selected_order_id} 배송 상태 업데이트 및 푸시 알림 전송 완료!")
                        else:
                            st.warning(f"주문 #{selected_order_id} 배송 상태는 업데이트되었으나 푸시 알림 전송에 실패했습니다.")
                    else:
                        st.success(f"주문 #{selected_order_id} 배송 상태 업데이트 완료 (푸시 알림 토큰이 없어 발송되지 않음).")
                else:
                    st.success(f"주문 #{selected_order_id} 배송 상태가 {new_status}로 업데이트되었습니다.")
                
                time.sleep(1.5)
                st.rerun()


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
        df_all_v = pd.read_sql_query("SELECT h.name,v.location,v.description,v.image1,v.image2,v.image3,v.image4,v.image5 FROM host_venues v JOIN hosts h ON v.host_id=h.id", conn)
        conn.close()
        if df_all_v.empty:
            st.info("등록된 숙소가 없습니다.")
        else:
            for _, v in df_all_v.iterrows():
                with st.expander(f"🏠 {v['name']} — 📍{v['location'] or ''}"):
                    render_b64_gallery([v.get(key) for key in VENUE_IMAGE_KEYS], columns_count=5)
                    if v['description']: st.caption(v['description'])
    else:
        render_host_income_billboard(load_host_income_snapshot(host_id))
        st.subheader("🏠 내 숙소 프로필")
        st.caption("숙소 위치와 내부 사진을 정리해 두면 쇼룸 완성도가 올라가고, 제휴 제안도 더 매끄럽게 받을 수 있어요.")

        conn = database.get_db_connection()
        q_v = ('SELECT * FROM host_venues WHERE host_id=%s' if database.DATABASE_URL
               else 'SELECT * FROM host_venues WHERE host_id=?')
        df_v = pd.read_sql_query(q_v, conn, params=(host_id,))
        conn.close()
        existing = df_v.iloc[0] if not df_v.empty else None

        current_images = [existing.get(key) if existing is not None else None for key in VENUE_IMAGE_KEYS]

        with st.container(border=True):
            st.markdown("#### 쇼룸 공간 정보")
            st.caption("사진은 최대 5장까지 등록할 수 있어요. 빈 칸은 그대로 두면 기존 이미지가 유지됩니다.")
            with st.form("venue_form"):
                location = st.text_input("숙소 위치 (주소 또는 지역명)", value=existing['location'] if existing is not None else "")
                description = st.text_area("숙소 소개", value=existing['description'] if existing is not None else "", height=120)
                st.markdown("**숙소 내부 사진 (최대 5장)**")

                uploaded_slots = {}
                clear_slots = {}
                for start in range(0, len(VENUE_IMAGE_KEYS), 3):
                    cols = st.columns(min(3, len(VENUE_IMAGE_KEYS) - start))
                    for col, image_key in zip(cols, VENUE_IMAGE_KEYS[start:start + 3]):
                        slot_index = VENUE_IMAGE_KEYS.index(image_key) + 1
                        with col:
                            st.markdown(f"**사진 {slot_index}**")
                            show_img(current_images[slot_index - 1], width=180)
                            uploaded_slots[image_key] = st.file_uploader(
                                f"사진 {slot_index} 업로드",
                                type=["jpg", "jpeg", "png", "webp"],
                                key=f"venue_{slot_index}",
                            )
                            clear_slots[image_key] = st.checkbox("이 슬롯 비우기", value=False, key=f"venue_clear_{slot_index}")

                save_venue = st.form_submit_button("💾 숙소 정보 저장", use_container_width=True, type="primary")

        if save_venue:
            next_images = []
            for image_key in VENUE_IMAGE_KEYS:
                current_value = existing.get(image_key) if existing is not None else None
                if clear_slots[image_key]:
                    next_images.append(None)
                elif uploaded_slots[image_key]:
                    next_images.append(database.file_to_base64(uploaded_slots[image_key]))
                else:
                    next_images.append(current_value)

            conn = database.get_db_connection()
            cursor = conn.cursor()
            try:
                if existing is not None:
                    q = ('UPDATE host_venues SET location=%s,description=%s,image1=%s,image2=%s,image3=%s,image4=%s,image5=%s WHERE host_id=%s'
                         if database.DATABASE_URL else
                         'UPDATE host_venues SET location=?,description=?,image1=?,image2=?,image3=?,image4=?,image5=? WHERE host_id=?')
                    cursor.execute(q, (location, description, *next_images, host_id))
                else:
                    q = ('INSERT INTO host_venues (host_id,location,description,image1,image2,image3,image4,image5) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)'
                         if database.DATABASE_URL else
                         'INSERT INTO host_venues (host_id,location,description,image1,image2,image3,image4,image5) VALUES (?,?,?,?,?,?,?,?)')
                    cursor.execute(q, (host_id, location, description, *next_images))
                database.bump_public_content_version(conn)
                conn.commit()
                st.success("✅ 숙소 정보가 저장되었습니다!")
                st.rerun()
            except Exception as e:
                st.error(f"오류: {e}")
            finally:
                conn.close()

        if existing is not None:
            st.markdown("---")
            st.markdown("**현재 등록된 쇼룸 갤러리**")
            render_b64_gallery([existing.get(key) for key in VENUE_IMAGE_KEYS], columns_count=5)

# ═══════════════════════════════════════
# TAB 5 — HOST: 입점 신청 / MASTER: 입점 전체 현황
# ═══════════════════════════════════════
with tab_list[5]:
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
