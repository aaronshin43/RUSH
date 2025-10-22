from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl
from typing import Optional

from celery_app import crawl_single_url, full_site_crawl, incremental_update, celery_app
from app.core.logger import logger

router = APIRouter(prefix="/api/crawl", tags=["crawl"])


# ==================== Request Models ====================

class CrawlURLRequest(BaseModel):
    url: HttpUrl


class FullCrawlRequest(BaseModel):
    seed_url: HttpUrl = "https://www.dickinson.edu"
    max_pages: int = 100


class IncrementalUpdateRequest(BaseModel):
    priority: str = "high"  # high, medium, low


# ==================== Endpoints ====================

@router.post("/single")
async def crawl_single(request: CrawlURLRequest):
    """단일 URL 크롤링 (백그라운드)"""
    try:
        task = crawl_single_url.delay(str(request.url))
        
        return {
            "status": "started",
            "task_id": task.id,
            "url": str(request.url),
            "message": "Crawling task started in background"
        }
    
    except Exception as e:
        logger.error(f"Failed to start crawl task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/full")
async def start_full_crawl(request: FullCrawlRequest):
    """전체 사이트 크롤링 시작"""
    try:
        task = full_site_crawl.delay(
            seed_url=str(request.seed_url),
            max_pages=request.max_pages
        )
        
        return {
            "status": "started",
            "task_id": task.id,
            "seed_url": str(request.seed_url),
            "max_pages": request.max_pages,
            "message": "Full site crawl started. This may take 2-3 hours."
        }
    
    except Exception as e:
        logger.error(f"Failed to start full crawl: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update")
async def start_incremental_update(request: IncrementalUpdateRequest):
    """증분 업데이트 시작"""
    try:
        task = incremental_update.delay(priority=request.priority)
        
        return {
            "status": "started",
            "task_id": task.id,
            "priority": request.priority,
            "message": "Incremental update started"
        }
    
    except Exception as e:
        logger.error(f"Failed to start incremental update: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Celery Task 상태 확인"""
    try:
        task = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": task.state,
            "result": None
        }
        
        if task.state == 'PENDING':
            response["message"] = "Task is waiting to start"
        
        elif task.state == 'PROGRESS':
            response["progress"] = task.info
        
        elif task.state == 'SUCCESS':
            response["result"] = task.result
        
        elif task.state == 'FAILURE':
            response["error"] = str(task.info)
        
        return response
    
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Task not found: {e}")