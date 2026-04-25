import os

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    FIREBASE_ADMIN_AVAILABLE = True
except ImportError:
    FIREBASE_ADMIN_AVAILABLE = False

# Firebase Admin SDK 초기화
# 루트 디렉토리에 serviceAccountKey.json 파일이 있어야 정상 작동합니다.
key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'serviceAccountKey.json')

if FIREBASE_ADMIN_AVAILABLE and os.path.exists(key_path):
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
        print("[FCM] Firebase Admin SDK initialized successfully.")
    except Exception as e:
        print(f"[FCM] Failed to initialize Firebase Admin SDK: {e}")
        FIREBASE_ADMIN_AVAILABLE = False
else:
    print("[FCM] 'firebase_admin' package missing or 'serviceAccountKey.json' not found. FCM will be mocked.")
    FIREBASE_ADMIN_AVAILABLE = False


def send_push_notification(token: str, title: str, body: str, data: dict = None):
    """
    주어진 FCM 토큰으로 푸시 알림을 전송합니다.
    """
    if not token:
        print("[FCM] No token provided. Skipping push notification.")
        return False

    if not FIREBASE_ADMIN_AVAILABLE:
        print(f"[FCM MOCK] Sending push to {token[:10]}... | Title: {title} | Body: {body}")
        return True

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=token,
        )
        response = messaging.send(message)
        print(f"[FCM] Successfully sent message: {response}")
        return True
    except Exception as e:
        print(f"[FCM] Error sending message: {e}")
        return False
