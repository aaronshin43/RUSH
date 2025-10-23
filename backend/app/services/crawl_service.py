from typing import List, Optional
from datetime import datetime

from app.core.logger import logger
from app.core.database import mongodb_db, close_connections
from app.models.document import Document, DocumentRepository, Section
from app.services.crawler import DickinsonCrawler
from app.services.url_utils import URLNormalizer

"""
TODO: Unchanged 카테고리 만들기
"""

class CrawlService:
    """크롤링 및 저장 통합 서비스"""
    
    def __init__(self):
        self.repo = DocumentRepository(mongodb_db)
    
    def save_crawl_result(self, crawl_data: dict) -> Optional[str]:
        """
        크롤링 결과를 MongoDB에 저장 (동기식)
        
        Args:
            crawl_data: 크롤러가 반환한 데이터
            
        Returns:
            문서 ID 또는 None
        """
        try:
            # URL 정규화
            normalized_url = URLNormalizer.normalize(crawl_data['url'])
            if not normalized_url:
                logger.warning(f"Invalid URL: {crawl_data['url']}")
                return None
            
            # 기존 문서 확인
            existing = self.repo.find_by_url(normalized_url)
            
            if existing:
                # 콘텐츠 변경 확인
                if existing.content_hash != crawl_data['content_hash']:
                    logger.info(f"Updating existing document: {normalized_url}")
                    self.repo.update_content(
                        normalized_url,
                        crawl_data['content'],
                        crawl_data['content_hash'],
                        crawl_data['sections']
                    )
                    return str(existing.id)
                else:
                    logger.info(f"Document unchanged: {normalized_url}")
                    return str(existing.id)
            
            # 새 문서 생성
            sections = [Section(**s) for s in crawl_data['sections']]
            
            document = Document(
                url=crawl_data['url'],
                normalized_url=normalized_url,
                title=crawl_data['title'],
                category=crawl_data['category'],
                content=crawl_data['content'],
                content_hash=crawl_data['content_hash'],
                sections=sections,
                word_count=crawl_data['word_count'],
                crawled_at=crawl_data['crawled_at'],
                status="active"
            )
            
            doc_id = self.repo.create(document)
            logger.info(f"✓ Saved new document: {normalized_url} (ID: {doc_id})")
            return doc_id
            
        except Exception as e:
            logger.error(f"Failed to save document: {e}")
            return None
    
    def crawl_and_save(
        self,
        seed_url: str = "https://www.dickinson.edu",
        max_pages: int = 100,
        rate_limit_delay: float = 1.0
    ) -> dict:
        """
        크롤링 실행 및 결과 저장 (동기식)
        
        Returns:
            통계 정보
        """
        logger.info(f"Starting crawl and save: {seed_url}")
        
        # 크롤링 실행
        crawler = DickinsonCrawler(
            seed_url=seed_url,
            max_pages=max_pages,
            rate_limit_delay=rate_limit_delay
        )
        results = crawler.crawl()
        
        # 결과 저장
        saved_count = 0
        updated_count = 0
        failed_count = 0
        
        for result in results:
            doc_id = self.save_crawl_result(result)
            if doc_id:
                # 새로 저장인지 업데이트인지 확인
                existing = self.repo.find_by_url(
                    URLNormalizer.normalize(result['url'])
                )
                if existing and existing.last_updated:
                    updated_count += 1
                else:
                    saved_count += 1
            else:
                failed_count += 1
        
        # 통계
        stats = {
            "total_crawled": len(results),
            "saved": saved_count,
            "updated": updated_count,
            "failed": failed_count,
            "crawler_stats": crawler.get_statistics()
        }
        
        logger.info(f"Crawl and save completed: {stats}")
        return stats
    
    def get_statistics(self) -> dict:
        """저장된 문서 통계 (동기식)"""
        print(self.repo.get_all_urls())
        return self.repo.get_statistics()


# 테스트 코드
if __name__ == "__main__":
    service = CrawlService()
    
    # 소규모 크롤링 테스트 (5 페이지)
    stats = service.crawl_and_save(
        seed_url="https://www.dickinson.edu/homepage/57/computer_science",
        max_pages=5,
        rate_limit_delay=1.0
    )
    
    print(f"\n{'='*60}")
    print("Crawl and Save Statistics:")
    print(f"  Total Crawled: {stats['total_crawled']}")
    print(f"  Saved: {stats['saved']}")
    print(f"  Updated: {stats['updated']}")
    print(f"  Failed: {stats['failed']}")
    
    # MongoDB 통계
    db_stats = service.get_statistics()
    print(f"\nDatabase Statistics:")
    print(f"  Total Documents: {db_stats['total_documents']}")
    print(f"  Categories:")
    for cat, info in db_stats['categories'].items():
        print(f"    {cat}: {info['count']} docs, {info['total_words']:,} words")
    
    close_connections()