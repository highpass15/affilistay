import requests
from requests.auth import HTTPBasicAuth

# 1. 페이팔 대시보드에서 복사한 값을 아래에 정확히 붙여넣으세요.
client_id = "이곳에_Client_ID를_붙여넣으세요"
client_secret = "이곳에_Secret을_붙여넣으세요"

def main():
    print("페이팔 토큰 발급을 시도합니다...")
    
    response = requests.post(
        "https://api-m.sandbox.paypal.com/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=HTTPBasicAuth(client_id, client_secret)
    )
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        print("\n========================================================")
        print("[발급 성공! 아래의 긴 토큰을 복사해서 MCP 첫 번째 칸에 넣으세요]")
        print("========================================================")
        print(token)
        print("========================================================")
    else:
        print("\n[발급 실패] ID나 Secret을 잘못 복사하셨습니다. 다시 확인해주세요.")
        print(response.text)

if __name__ == "__main__":
    main()
