from motor.motor_asyncio import AsyncIOMotorClient
from redis import Redis
import weaviate
from app.core.config import settings

# MongoDB
mongodb_client = AsyncIOMotorClient(settings.MONGODB_URI)
mongodb_db = mongodb_client[settings.MONGODB_DB_NAME]

# Redis
redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

# Weaviate
weaviate_client = weaviate.Client(url=settings.WEAVIATE_URL)

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
        weaviate_client.is_ready()
        status['weaviate'] = 'connected'
    except Exception as e:
        status['weaviate'] = f'error: {str(e)}'
    
    return status