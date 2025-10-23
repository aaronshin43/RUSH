from pymongo import MongoClient
from redis import Redis
import weaviate
from weaviate.classes.init import Auth
from app.core.config import settings
from urllib.parse import urlparse
# from weaviate.connect import ConnectionParams
# from app.core.logger import logger

# MongoDB (동기식)
mongodb_client = MongoClient(settings.MONGODB_URI)
mongodb_db = mongodb_client[settings.MONGODB_DB_NAME]

# Redis
redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

# Weaviate
# 환경 변수 설정
WEAVIATE_GRPC_PORT = settings.WEAVIATE_GRPC_PORT
parsed_url = urlparse(settings.WEAVIATE_URL)
http_host = parsed_url.hostname
http_port = parsed_url.port
http_secure = parsed_url.scheme == 'https'

# Weaviate 클라이언트 초기화
weaviate_client = None

weaviate_client = weaviate.connect_to_custom(
        http_host=http_host,
        http_port=http_port,
        http_secure=http_secure,
        grpc_host=http_host,
        grpc_port=WEAVIATE_GRPC_PORT,
        grpc_secure=False # gRPC에 SSL/TLS를 사용하지 않는 경우
    )

# 연결 시도
weaviate_client.connect()


def check_connections():
    """모든 데이터베이스 연결 확인 (동기식)"""
    status = {}
    
    # MongoDB
    try:
        mongodb_client.admin.command('ping')
        status['mongodb'] = 'connected'
    except Exception as e:
        status['mongodb'] = f'error: {str(e)}'
    
    # Redis
    try:
        redis_client.ping()
        status['redis'] = 'connected'
    except Exception as e:
        status['redis'] = f'error: {str(e)}'
    
    # Weaviate
    try:
        is_ready = weaviate_client.is_ready()
        status['weaviate'] = 'connected' if is_ready else 'not ready'
    except Exception as e:
        status['weaviate'] = f'error: {str(e)}'
    
    return status


# 애플리케이션 종료 시 연결 닫기
def close_connections():
    """데이터베이스 연결 종료"""
    try:
        mongodb_client.close()
        redis_client.close()
        weaviate_client.close()
    except:
        pass