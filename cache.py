# cache.py
from redis import Redis

# Redis 연결 풀 생성
# (실제 환경에서는 host, port, db 등을 .env에서 읽어오세요)
redis_client = Redis(host='localhost', port=6379, db=0, decode_responses=True)

def get_redis_client():
    """FastAPI Depends로 주입하기 위한 함수"""
    try:
        yield redis_client
    finally:
        # (애플리케이션 종료 시 연결을 닫는 로직이 필요할 수 있으나,
        #  보통 풀을 사용하면 유지합니다.)
        pass