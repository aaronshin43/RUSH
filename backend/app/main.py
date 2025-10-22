from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import check_connections, close_connections
from app.api.crawl import router as crawl_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시
    print("🚀 RUSH API Starting...")
    yield
    # 종료 시
    print("🛑 RUSH API Shutting down...")
    close_connections()


app = FastAPI(
    title="RUSH API",
    description="Dickinson College AI Assistant",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(crawl_router)


@app.get("/")
async def root():
    return {
        "message": "RUSH API is running!",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


@app.get("/health")
async def health_check():
    connections = await check_connections()
    return {
        "status": "healthy" if all(v == "connected" for v in connections.values()) else "degraded",
        **connections
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)