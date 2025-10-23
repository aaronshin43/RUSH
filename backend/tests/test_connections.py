# backend/test_connections.py
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from redis import Redis
import weaviate
from app.core.config import settings

async def test_all():
    print("🔍 Testing database connections...\n")
    
    # Test MongoDB
    print("1️⃣ Testing MongoDB...")
    try:
        mongodb_client = AsyncIOMotorClient(settings.MONGODB_URI)
        await mongodb_client.admin.command('ping')
        print("   ✅ MongoDB: Connected")
        mongodb_client.close()
    except Exception as e:
        print(f"   ❌ MongoDB: {e}")
    
    # Test Redis
    print("\n2️⃣ Testing Redis...")
    try:
        redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        redis_client.ping()
        print("   ✅ Redis: Connected")
    except Exception as e:
        print(f"   ❌ Redis: {e}")
    
    # Test Weaviate
    print("\n3️⃣ Testing Weaviate...")
    try:
        client = weaviate.connect_to_local(host="localhost", port=8080, grpc_port=50051)
        if client.is_ready():
            print("   ✅ Weaviate: Connected")
        else:
            print("   ⚠️  Weaviate: Not ready")
        client.close()
    except Exception as e:
        print(f"   ❌ Weaviate: {e}")

if __name__ == "__main__":
    asyncio.run(test_all())