# AFFILISTAY 플랫폼 아키텍처 명세서

## 1. 프로젝트 개요
AFFILISTAY는 숙소 호스트(Host)가 입점받은 프리미엄 제품을 객실(거실, 침실, 주방, 화장실 등)에 비치하고, 게스트(Guest)가 QR 코드를 스캔하여 제품을 체험하고 현장에서 즉시 구매할 수 있도록 돕는 **O2O(Online to Offline) 쇼룸 커머스 플랫폼**입니다.

---

## 2. 기술 스택 (Tech Stack)
*   **Backend**: Python, FastAPI (비동기 API 및 프론트엔드 서빙)
*   **Admin Dashboard**: Streamlit (관리자용 데이터 등록 및 정산 UI)
*   **Database**: PostgreSQL (배포 환경) / SQLite (로컬 테스트 환경) 호환
*   **Frontend**: HTML5, Vanilla CSS, Jinja2 Template (Minoan 스타일의 프리미엄 UI)
*   **Deployment**: Render (도커라이징 배포), GitHub

---

## 3. 핵심 디렉토리 구조
```text
qr_platform_mvp/
├── checkout_server.py       # FastAPI 백엔드 메인 서버 (쇼룸 라우팅 및 주문 처리)
├── admin_dashboard_ui.py    # Streamlit 마스터/호스트 통합 대시보드 (제품 등록, 정산)
├── database.py              # DB 연결, 스키마 정의 및 마이그레이션 모듈
├── requirements.txt         # 파이썬 의존성 패키지 목록
├── run.sh                   # Render 배포용 실행 스크립트 (FastAPI + Streamlit 동시 실행)
├── Dockerfile               # 도커 빌드 설정
└── templates/               # 쇼룸 프론트엔드 HTML 템플릿 폴더
    ├── shop.html            # 숙소 단위 쇼룸 메인 (카테고리별 제품 그리드)
    ├── product_detail.html  # 개별 제품 상세 및 구매 유도 페이지
    ├── order_form.html      # 주문 정보 입력 폼 (이름, 연락처, 배송지 등)
    └── order_complete.html  # 주문 완료 및 안내 페이지
```

---

## 4. 데이터베이스 스키마 구조
현재 애플리케이션의 핵심 데이터를 담당하는 3개의 메인 테이블입니다.

### `hosts` (숙소/호스트 정보)
*   `id`: INTEGER (PK)
*   `name`: TEXT (숙소명)
*   `uid`: TEXT (호스트 고유 로그인 ID)
*   `pw`: TEXT (비밀번호)
*   `revenue`: INTEGER (총 모객 수익)

### `products` (제품 및 QR 정보)
*   `id`: INTEGER (PK)
*   `qr_code_id`: TEXT (고유 QR 세션 ID)
*   `owner_id`: INTEGER (FK -> hosts.id)
*   `brand_name`: TEXT (브랜드명)
*   `product_name`: TEXT (제품명)
*   `price`: INTEGER (가격)
*   `room_category`: TEXT (비치된 방 카테고리: 거실, 침실, 주방, 화장실)
*   `description`: TEXT (제품 상세 설명문)
*   `image_url`: TEXT (Base64 인코딩된 썸네일 이미지)

### `orders` (주문 및 정산 현황)
*   `id`: INTEGER (PK)
*   `product_id`: INTEGER (FK -> products.id)
*   `customer_name`: TEXT (수령자 이름)
*   `phone_number`: TEXT (연락처)
*   `shipping_address`: TEXT (배송지 주소)
*   `delivery_note`: TEXT (부재시 배송 요청사항)
*   `total_amount`: INTEGER (최종 결제 금액)
*   `payment_status`: TEXT (결제 상태 - PAID 등)
*   `settlement_status`: TEXT (정산 상태 - PENDING(대기), COMPLETED(완료))
*   `created_at`: TIMESTAMP (주문 일시)

---

## 5. 핵심 사용자 플로우
1.  **호스트 세팅 (Streamlit)**: 
    *   어드민 대시보드에 로그인하여 입점받은 상품을 등록합니다. (제품명, 가격, 사진, 배치 위치 등)
    *   등록 시 숙소 전용 QR 코드가 자동으로 발급 및 다운로드됩니다.
2.  **게스트 탐색 (FastAPI)**:
    *   비치된 QR 코드를 스캔하면 `/shop/QR코드ID` 로 접속됩니다.
    *   Jinja2가 숙소(`owner_id`)에 등록된 모든 상품을 가져와 `shop.html`로 공간별(거실, 침실 등)로 분류해 보여줍니다.
3.  **게스트 주문**:
    *   상세 페이지(`product_detail.html`)에서 구매 버튼 클릭 → 배송지 입력(`order_form.html`) → 주문 완료.
4.  **브랜드 배송 및 정산**:
    *   주문 데이터가 `orders` DB에 즉시 Insert 됩니다.
    *   관리자는 어드민 대시보드에서 주문 내역과 부재시 요청사항을 실시간으로 확인하고 엑셀로 다운로드하여 제품을 직배송/정산 처리합니다.

---

## 6. 향후 AI에게 수정 지시할 때의 프롬프트 예시
문제를 겪거나 기능을 추가할 때 이 파일을 함께 업로드 후 다음과 같이 지시하세요.

> *"이 파일(ARCHITECTURE.md)은 현재 내 프로젝트의 뼈대야. `admin_dashboard_ui.py`에서 기존 `settlement_status` 필터를 조작해서 '배송 완료' 버튼을 만들어주고, 이 상태를 DB에 업데이트하도록 `database.py`도 함께 수정해줘."*
