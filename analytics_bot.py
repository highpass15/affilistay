import os
import sys
import getpass
from datetime import datetime
from database import get_db_connection, _is_pg, _fetch_all

try:
    import anthropic
except ImportError:
    print("anthropic 패키지가 설치되지 않았습니다. 터미널에서 'pip install anthropic'을 실행해주세요.")
    sys.exit(1)

def fetch_analytics_data():
    conn = get_db_connection()
    
    # 1. 공간별/제품별 트래픽 및 체류시간 (룸 카테고리, 가격 포함)
    # [제안/대안 반영] 이상치 방지: 최대 체류 시간 360초(6분) 캡핑 적용
    q_dwell = """
    SELECT 
        h.name as host_name,
        p.id as product_id, 
        p.product_name,
        p.room_category,
        p.price,
        p.image_url,
        COUNT(pv.id) as total_views, 
        AVG(CASE WHEN pv.duration_seconds > 360 THEN 360 ELSE pv.duration_seconds END) as avg_dwell_seconds
    FROM page_views pv
    JOIN products p ON pv.product_id = p.id
    JOIN hosts h ON pv.host_id = h.id
    WHERE pv.duration_seconds > 2
    GROUP BY h.name, p.id, p.product_name, p.room_category, p.price, p.image_url
    """
    
    # 2. 호스트(공간)별 구매 전환율 (룸 카테고리 포함)
    q_conversion = """
    SELECT 
        h.id as host_id, 
        h.name as host_name,
        p.product_name,
        p.room_category,
        COUNT(DISTINCT pv.session_id) as unique_visitors,
        COUNT(DISTINCT o.id) as total_orders
    FROM hosts h
    JOIN products p ON h.id = p.owner_id
    LEFT JOIN page_views pv ON pv.host_id = h.id AND pv.product_id = p.id
    LEFT JOIN orders o ON o.product_id = p.id AND o.session_id = pv.session_id
    GROUP BY h.id, h.name, p.product_name, p.room_category
    """
    
    # 3. 시간대 및 요일 트래픽용 로우 데이터
    q_traffic = "SELECT enter_time FROM page_views"
    
    dwell_data = _fetch_all(conn, q_dwell, q_dwell)
    conv_data = _fetch_all(conn, q_conversion, q_conversion)
    traffic_data = _fetch_all(conn, q_traffic, q_traffic)
    
    conn.close()
    return dwell_data, conv_data, traffic_data

def generate_insights(dwell_data, conv_data, traffic_data, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    
    ROOM_MAP = {'living_room': '거실', 'bedroom': '침실', 'kitchen': '주방', 'bathroom': '화장실'}
    
    # --- 데이터 텍스트 파싱 ---
    dwell_text = ""
    for row in dwell_data:
        avg_dwell = row['avg_dwell_seconds'] or 0
        room_kr = ROOM_MAP.get(row['room_category'], '기타')
        price = row['price'] or 0
        dwell_text += f"- [{row['host_name']}] 숙소의 [{room_kr}] 공간: '{row['product_name']}' (가격: {price:,}원) | 유효 조회 {row['total_views']}회, 유효 평균 체류시간 {avg_dwell:.1f}초\n"
        
    conv_text = ""
    for row in conv_data:
        visitors = row['unique_visitors'] or 0
        orders = row['total_orders'] or 0
        rate = (orders / visitors * 100) if visitors > 0 else 0
        room_kr = ROOM_MAP.get(row['room_category'], '기타')
        conv_text += f"- [{row['host_name']}] 숙소 [{room_kr}] 공간의 '{row['product_name']}': 방문자 {visitors}명, 주문 {orders}건 (전환율: {rate:.1f}%)\n"
        
    # --- 시간대 및 요일 파싱 ---
    morning = afternoon = evening = night = 0
    weekend = weekday = 0
    
    for row in traffic_data:
        try:
            dt = row['enter_time']
            if isinstance(dt, str):
                try: dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
                except: dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S.%f')
            
            hour = dt.hour
            if 6 <= hour < 12: morning += 1
            elif 12 <= hour < 18: afternoon += 1
            elif 18 <= hour < 24: evening += 1
            else: night += 1
            
            if dt.weekday() >= 5: weekend += 1
            else: weekday += 1
        except:
            pass
            
    traffic_text = f"- 아침(06-12시): {morning}회, 오후(12-18시): {afternoon}회, 저녁(18-24시): {evening}회, 심야(00-06시): {night}회\n"
    traffic_text += f"- 평일 조회: {weekday}회, 주말 조회: {weekend}회\n"
    
    # --- 프롬프트 구성 ---
    prompt = f"""
당신은 프리미엄 제품을 감성 숙소에 입점시켜 판매하는 B2B2C O2O 커머스 플랫폼 '어필리스테이'의 수석 데이터 분석가입니다.
우리의 핵심 차별화 포인트는 '고객이 실제 숙소 공간(거실, 침실 등)에서 제품을 충분히 경험해보고 구매한다'는 점입니다.

다음은 현재 데이터베이스에서 실시간으로 추출한 주요 통계입니다.
(단, 체류시간은 2초 이하 이탈 제외 및 최대 6분 캡핑이 적용된 '유효 체류 시간'입니다.)

[1. 공간(룸 타입) 및 가격 대비 체류시간 통계]
{dwell_text if dwell_text else "데이터가 충분하지 않습니다."}

[2. 공간(룸 타입) 페어링별 구매 전환율]
{conv_text if conv_text else "데이터가 충분하지 않습니다."}

[3. 시간대 및 요일별 트래픽 (언제 클릭률이 높은가?)]
{traffic_text}

위 데이터를 바탕으로 대표님(사용자)에게 다음 내용을 포함한 마케팅 심층 분석 리포트를 작성해 주세요. (가독성 좋은 마크다운 포맷)
1. 공간(거실/주방/침실/화장실) 맵핑 분석: 어떤 공간에 제품을 두었을 때 체류시간이나 클릭/전환율이 더 좋은지, 그 이유는 무엇일지 추론
2. 시각적 무드 & 주변 환경 분석: (첨부된 이미지가 있다면) 이미지의 톤, 무드, 함께 연출된 사물이 제품 체류시간/전환율에 미치는 긍정적 효과 분석
3. 가격 대비 체류시간 상관관계: 프리미엄(고가) 제품군일수록 고객이 숙소에서 오랫동안 경험(체류)하는 경향이 있는지 파악
4. 시간대/요일 트래픽 인사이트: 어느 시간대(또는 주말/평일)에 트래픽/관심도가 높은지 분석하고, 이를 활용한 푸시 알림이나 마케팅 전략 제안
5. 파트너로서 추가 제안: 어필리스테이의 차별점을 살려 브랜드를 설득할 수 있는 새로운 B2B 세일즈/마케팅 아이디어 제안
"""

    messages_content = [{"type": "text", "text": prompt}]

    # --- Vision API용 최고 성과 이미지 샘플링 ---
    sorted_dwell = sorted([d for d in dwell_data if d['image_url']], key=lambda x: (x['avg_dwell_seconds'] or 0), reverse=True)
    if sorted_dwell:
        top_product = sorted_dwell[0]
        # Base64 헤더 제거 (data:image/png;base64, 부분)
        img_data = top_product['image_url']
        if img_data.startswith("data:image"):
            img_data = img_data.split(",")[1]
            
        messages_content.append({
            "type": "text", 
            "text": f"📸 [Vision 분석용 이미지]: 다음은 가장 성과(체류시간)가 좋은 제품('{top_product['product_name']}')의 실제 이미지입니다. 이 이미지의 시각적 요소(톤/무드/배치)가 고객 경험에 미친 영향을 분석에 포함해 주세요."
        })
        messages_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": img_data
            }
        })

    print("\n💡 [Claude AI] 다차원 데이터 및 비전(이미지) 분석 중... 잠시만 기다려주세요...\n")
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=2500,
            temperature=0.7,
            messages=[{"role": "user", "content": messages_content}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Claude API 호출 중 오류가 발생했습니다: {e}"

if __name__ == "__main__":
    print("="*60)
    print(" 🤖 AffiliStay AI Analytics Bot (Powered by Claude) ")
    print("="*60)
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = getpass.getpass("🔑 Anthropic API Key를 입력하세요 (입력 시 화면에 보이지 않습니다): ")
        
    try:
        dwell, conv, traffic = fetch_analytics_data()
        
        has_data = len(dwell) > 0 or len(conv) > 0
        if not has_data:
            print("\n⚠️ 현재 수집된 데이터가 거의 없습니다. 홈페이지에서 몇 분간 머무르거나 주문을 발생시킨 뒤 다시 실행해 주세요.")
            
        report = generate_insights(dwell, conv, traffic, api_key)
        
        print("\n" + "="*60)
        print(" 📊 심층 마케팅 분석 리포트")
        print("="*60)
        print(report)
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"\n❌ 오류가 발생했습니다: {e}")
