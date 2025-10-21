from celery import Celery
from app.core.config import settings

celery_app = Celery(
    'rush',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/New_York',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1시간 타임아웃
)

# 테스트 태스크
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