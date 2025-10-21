from typing import Set, List, Optional
from collections import deque
from urllib.parse import urljoin
import time
from bs4 import BeautifulSoup

from app.core.logger import logger
from app.services.url_utils import URLNormalizer
from app.services.content_extractor import ContentExtractor


class DickinsonCrawler:
    """Dickinson College 웹사이트 BFS 크롤러"""
    
    def __init__(
        self,
        seed_url: str = "https://www.dickinson.edu",
        max_pages: int = 100,
        rate_limit_delay: float = 1.0
    ):
        """
        Args:
            seed_url: 시작 URL
            max_pages: 최대 크롤링 페이지 수
            rate_limit_delay: 요청 간 대기 시간 (초)
        """
        self.seed_url = seed_url
        self.max_pages = max_pages
        self.rate_limit_delay = rate_limit_delay
        
        self.extractor = ContentExtractor()
        self.visited: Set[str] = set()
        self.queue: deque = deque([seed_url])
        self.results: List[dict] = []
        
        logger.info(f"Crawler initialized: max_pages={max_pages}, delay={rate_limit_delay}s")
    
    def extract_links(self, html: str, base_url: str) -> List[str]:
        """
        HTML에서 내부 링크 추출
        
        Args:
            html: HTML 문자열
            base_url: 기준 URL
            
        Returns:
            정규화된 URL 리스트
        """
        links = []
        soup = BeautifulSoup(html, 'html.parser')
        
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            
            # 절대 URL로 변환
            absolute_url = urljoin(base_url, href)
            
            # 정규화
            normalized = URLNormalizer.normalize(absolute_url)
            
            if normalized and normalized not in self.visited:
                links.append(normalized)
        
        return links
    
    def crawl(self) -> List[dict]:
        """
        BFS 크롤링 실행
        
        Returns:
            크롤링된 페이지 데이터 리스트
        """
        logger.info(f"Starting crawl from {self.seed_url}")
        start_time = time.time()
        
        while self.queue and len(self.visited) < self.max_pages:
            url = self.queue.popleft()
            
            # 이미 방문한 URL 스킵
            if url in self.visited:
                continue
            
            # 크롤링
            try:
                # HTML 가져오기
                html = self.extractor.fetch_html(url)
                if not html:
                    logger.warning(f"Skipping {url} (fetch failed)")
                    continue
                
                # 콘텐츠 추출
                content_data = self.extractor.extract_content(html, url)
                if not content_data or content_data['word_count'] < 50:
                    logger.warning(f"Skipping {url} (insufficient content)")
                    continue
                
                # 결과 저장
                self.results.append(content_data)
                self.visited.add(url)
                
                # 진행 상황 로깅
                progress = len(self.visited)
                logger.info(f"[{progress}/{self.max_pages}] ✓ {url}")
                
                # 내부 링크 추출 및 큐에 추가
                links = self.extract_links(html, url)
                for link in links:
                    if link not in self.visited:
                        self.queue.append(link)
                
                logger.info(f"  → Found {len(links)} new links, queue size: {len(self.queue)}")
                
                # Rate limiting
                time.sleep(self.rate_limit_delay)
                
            except Exception as e:
                logger.error(f"Error crawling {url}: {e}")
                continue
        
        elapsed = time.time() - start_time
        logger.info(f"\nCrawl completed!")
        logger.info(f"  Pages crawled: {len(self.results)}")
        logger.info(f"  Time elapsed: {elapsed:.2f}s")
        logger.info(f"  Avg time per page: {elapsed/len(self.results):.2f}s")
        
        return self.results
    
    def get_statistics(self) -> dict:
        """크롤링 통계"""
        if not self.results:
            return {}
        
        total_words = sum(r['word_count'] for r in self.results)
        categories = {}
        for result in self.results:
            cat = result['category']
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            'total_pages': len(self.results),
            'total_words': total_words,
            'avg_words_per_page': total_words // len(self.results),
            'categories': categories
        }


# 테스트 코드
if __name__ == "__main__":
    # 소규모 테스트 (10 페이지만)
    crawler = DickinsonCrawler(
        seed_url="https://www.dickinson.edu/homepage/285/academics",
        max_pages=10,
        rate_limit_delay=1.0
    )
    
    results = crawler.crawl()
    
    # 통계 출력
    stats = crawler.get_statistics()
    print(f"\n{'='*60}")
    print("Crawl Statistics:")
    print(f"  Total Pages: {stats['total_pages']}")
    print(f"  Total Words: {stats['total_words']:,}")
    print(f"  Avg Words/Page: {stats['avg_words_per_page']}")
    print(f"\nCategories:")
    for cat, count in stats['categories'].items():
        print(f"  {cat}: {count}")
    
    # 크롤링된 URL 리스트
    print(f"\nCrawled URLs:")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result['url']}")
        print(f"     └─ {result['title']} ({result['word_count']} words)")