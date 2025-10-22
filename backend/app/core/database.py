from motor.motor_asyncio import AsyncIOMotorClient
from redis import Redis
import weaviate
from weaviate.classes.init import Auth
from app.core.config import settings

# MongoDB
mongodb_client = AsyncIOMotorClient(settings.MONGODB_URI)
mongodb_db = mongodb_client[settings.MONGODB_DB_NAME]

# Redis
redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

# Weaviate V4 Client
weaviate_client = weaviate.connect_to_local(
    host="localhost",  # Weaviate 호스트
    port=8080,         # Weaviate 포트
    grpc_port=50051,   # gRPC 포트
)

async def check_connections():
    """모든 데이터베이스 연결 확인"""
    status = {}
    
    # MongoDB
    try:
        await mongodb_client.admin.command('ping')
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