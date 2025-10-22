from celery import Celery
from celery.schedules import crontab
import asyncio

from app.core.config import settings
from app.core.logger import logger

celery_app = Celery(
    'rush',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['celery_app']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/New_York',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=7200,  # 2시간 타임아웃
    task_soft_time_limit=6600,  # 1.5시간 소프트 타임아웃
)


# ==================== 크롤링 Tasks ====================

@celery_app.task(bind=True)
def crawl_single_url(self, url: str):
    """단일 URL 크롤링"""
    from app.services.content_extractor import ContentExtractor
    from app.services.crawl_service import CrawlService
    logger.info(f"Task: Crawling single URL: {url}")

    try:
        # 콘텐츠 추출
        extractor = ContentExtractor()
        result = extractor.crawl_page(url)
        
        if not result:
            logger.warning(f"Failed to extract content from {url}")
            return None
        
        # MongoDB 저장
        service = CrawlService()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # 'RuntimeError: There is no current event loop...'
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        doc_id = loop.run_until_complete(service.save_crawl_result(result))
        
        return {
            "status": "success",
            "url": url,
            "doc_id": doc_id
        }
    
    except Exception as e:
        logger.error(f"Task failed for {url}: {e}")
        return {"status": "error", "url": url, "error": str(e)}


@celery_app.task(bind=True)
def full_site_crawl(self, seed_url: str = "https://www.dickinson.edu", max_pages: int = 100):
    """전체 사이트 크롤링"""
    from app.services.crawl_service import CrawlService
    
    logger.info(f"Task: Full site crawl starting (max_pages={max_pages})")
    
    try:
        service = CrawlService()
        
        # 진행률 업데이트를 위한 콜백
        total = max_pages
        
        for i in range(0, total, 10):
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': min(i + 10, total),
                    'total': total,
                    'status': f'Crawling pages {i}-{i+10}...'
                }
            )
            
            # 10페이지씩 크롤링
            stats = asyncio.run(service.crawl_and_save(
                seed_url=seed_url,
                max_pages=10,
                rate_limit_delay=1.0
            ))
        
        # 최종 통계
        final_stats = asyncio.run(service.get_statistics())
        
        return {
            "status": "completed",
            "stats": final_stats
        }
    
    except Exception as e:
        logger.error(f"Full site crawl failed: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise


@celery_app.task(bind=True)
def incremental_update(self, priority: str = "high"):
    """증분 업데이트 (변경된 페이지만 재크롤링)"""
    from app.services.crawl_service import CrawlService
    from app.services.content_extractor import ContentExtractor
    from app.services.hash_utils import has_content_changed
    
    logger.info(f"Task: Incremental update (priority={priority})")
    
    try:
        service = CrawlService()
        extractor = ContentExtractor()
        
        # 모든 URL 가져오기
        all_urls = asyncio.run(service.repo.get_all_urls())
        
        # TODO: 우선순위 필터링 구현
        # 지금은 모든 URL 체크
        
        updated_count = 0
        unchanged_count = 0
        failed_count = 0
        
        total = len(all_urls)
        
        for i, url in enumerate(all_urls):
            # 진행률 업데이트
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': i + 1,
                    'total': total,
                    'updated': updated_count,
                    'unchanged': unchanged_count
                }
            )
            
            # 기존 문서 가져오기
            existing = asyncio.run(service.repo.find_by_url(url))
            if not existing:
                continue
            
            # 새 콘텐츠 크롤링
            new_data = extractor.crawl_page(url)
            if not new_data:
                failed_count += 1
                continue
            
            # 변경 감지
            if has_content_changed(existing.content_hash, new_data['content']):
                asyncio.run(service.save_crawl_result(new_data))
                updated_count += 1
                logger.info(f"Updated: {url}")
            else:
                unchanged_count += 1
        
        return {
            "status": "completed",
            "total_checked": total,
            "updated": updated_count,
            "unchanged": unchanged_count,
            "failed": failed_count
        }
    
    except Exception as e:
        logger.error(f"Incremental update failed: {e}")
        raise


# ==================== 스케줄링 ====================

celery_app.conf.beat_schedule = {
    # 매일 밤 3시: High priority 페이지 업데이트
    'daily-high-priority-update': {
        'task': 'celery_app.incremental_update',
        'schedule': crontab(hour=3, minute=0),
        'args': ('high',)
    },
    # 매주 일요일 3시: Medium priority 페이지 업데이트
    'weekly-medium-priority-update': {
        'task': 'celery_app.incremental_update',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),
        'args': ('medium',)
    },
    # 매월 1일 3시: Low priority 페이지 업데이트
    'monthly-low-priority-update': {
        'task': 'celery_app.incremental_update',
        'schedule': crontab(hour=3, minute=0, day_of_month=1),
        'args': ('low',)
    },
}


# ==================== 테스트 Task ====================

@celery_app.task(bind=True)
def test_task(self, message: str):
    """테스트용 Celery 태스크"""
    import time
    
    for i in range(5):
        self.update_state(
            state='PROGRESS',
            meta={'current': i + 1, 'total': 5}
        )
        time.sleep(1)
    
    return f"Completed: {message}"


if __name__ == '__main__':
    celery_app.start()