import subprocess
import time
import os
import re

# 포트 설정
SHOP_PORT = 8000
ADMIN_PORT = 8501

# 원하는 서브도메인 (영구적으로 사용할 이름 - 더욱 고유하게 변경)
SUBDOMAIN_PREFIX = "affilistay-official"
SHOP_SUBDOMAIN = f"{SUBDOMAIN_PREFIX}-showroom"
ADMIN_SUBDOMAIN = f"{SUBDOMAIN_PREFIX}-portal"

def start_ssh_tunnel():
    print(f"[TUNNEL] '어필리스테이' 영구 주소 연결을 시작합니다...")
    
    # SSH 명령: serveo.net을 사용하여 8000번과 8501번 포트를 동시에 외부로 노출
    # -o StrictHostKeyChecking=no: 지문 확인 자동 생략
    ssh_command = [
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=30",
        "-R", f"{SHOP_SUBDOMAIN}:80:localhost:{SHOP_PORT}",
        "-R", f"{ADMIN_SUBDOMAIN}:80:localhost:{ADMIN_PORT}",
        "serveo.net"
    ]
    
    try:
        # 백그라운드에서 실행
        process = subprocess.Popen(
            ssh_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 주소 저장용 파일 업데이트
        shop_url = f"https://{SHOP_SUBDOMAIN}.serveo.net"
        admin_url = f"https://{ADMIN_SUBDOMAIN}.serveo.net"
        
        with open("public_url_8000.txt", "w", encoding="utf-8") as f:
            f.write(shop_url)
        with open("public_url_8501.txt", "w", encoding="utf-8") as f:
            f.write(admin_url)
            
        print(f"[SUCCESS] 쇼룸 주소: {shop_url}")
        print(f"[SUCCESS] 어드민 주소: {admin_url}")
        print("[INFO] 이 창을 닫으면 연결이 끊깁니다. 연결을 유지해 주세요.")
        
        # 프로세스가 살아있는 동안 대기
        while True:
            if process.poll() is not None:
                print("[WARN] 연결이 끊겼습니다. 5초 후 재시도를 시작합니다...")
                break
            time.sleep(10)
            
    except Exception as e:
        print(f"[ERROR] 터널 실행 중 오류 발생: {e}")

if __name__ == "__main__":
    while True:
        start_ssh_tunnel()
        time.sleep(5)
