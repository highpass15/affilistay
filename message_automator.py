import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

def send_email_invitation(smtp_server, smtp_port, sender_email, sender_password, receiver_email, subject, body):
    """
    제휴 호스트에게 이메일 초대장을 자동 발송합니다.
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True, "이메일 발송 성공"
    except Exception as e:
        return False, f"발송 실패: {str(e)}"

def send_sms_invitation(api_key, user_id, sender_phone, receiver_phone, message):
    """
    [뼈대] 국내 통신망 API(예: Aligo) 연동을 위한 함수
    현재는 API Key가 없으므로 실제 발송은 되지 않으며 성공 로그만 찍는 구조입니다.
    """
    # 실제 Aligo API 호출 예시 (현재는 주석 처리)
    # url = "https://apis.aligo.in/send/"
    # data = {
    #     "key": api_key,
    #     "user_id": user_id,
    #     "sender": sender_phone,
    #     "receiver": receiver_phone,
    #     "msg": message
    # }
    # response = requests.post(url, data=data)
    # return response.json()
    
    # 임시 성공 모의
    return True, f"[{receiver_phone}] 가상 발송 성공 (API 연동 대기중)"
