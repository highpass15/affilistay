# 1. 베이스 이미지 설정 (Python 3.11 사용)
FROM python:3.11-slim

# 2. 필수 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 3. 작업 디렉토리 설정
WORKDIR /app

# 4. 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 및 정적 자산 복사
COPY . .

# 6. 실행 권한 부여
RUN chmod +x run.sh

# 7. 포트 노출 (FastAPI: 8000, Streamlit: 8501)
EXPOSE 8000
EXPOSE 8501

# 8. 실행 명령어
CMD ["./run.sh"]
