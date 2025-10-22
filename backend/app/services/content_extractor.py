from typing import Dict, List, Optional
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from trafilatura import extract
from trafilatura.settings import use_config

from app.core.logger import logger
from app.services.hash_utils import compute_content_hash

"""
TODO: Extract dynamic contents
"""


class ContentExtractor:
    """웹페이지 콘텐츠 추출기"""
    
    def __init__(self):
        # Requests 세션 (Retry 전략 포함)
        self.session = self._create_session()
        
        # Trafilatura 설정
        self.traf_config = use_config()
        self.traf_config.set("DEFAULT", "MIN_EXTRACTED_SIZE", "500")
        self.traf_config.set("DEFAULT", "MIN_OUTPUT_SIZE", "300")
    
    def _create_session(self) -> requests.Session:
        """Retry 전략이 포함된 세션 생성"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,  # 1초, 2초, 4초
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def fetch_html(self, url: str) -> Optional[str]:
        """
        URL에서 HTML 가져오기
        
        Args:
            url: 크롤링할 URL
            
        Returns:
            HTML 문자열 또는 None (실패 시)
        """
        try:
            headers = {
                'User-Agent': 'RUSH-Bot/1.0 (Dickinson College Student Project; +https://github.com/aaronshin43)'
            }
            
            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            return response.text
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def extract_content(self, html: str, url: str) -> Dict:
        """
        HTML에서 콘텐츠 추출
        
        Args:
            html: HTML 문자열
            url: 원본 URL
            
        Returns:
            추출된 콘텐츠 딕셔너리
        """
        # 1. Trafilatura로 본문 추출
        main_content = extract(
            html,
            config=self.traf_config,
            include_comments=False,
            include_tables=True,
            include_links=False,
            no_fallback=False
        )
        
        # 2. Trafilatura 실패 시 BeautifulSoup 폴백
        if not main_content or len(main_content) < 100:
            logger.warning(f"Trafilatura failed for {url}, using BeautifulSoup fallback")
            main_content = self._extract_with_bs4(html)
        
        # 3. BeautifulSoup으로 메타데이터 추출
        soup = BeautifulSoup(html, 'html.parser')
        
        # 제목
        title = self._extract_title(soup)
        
        # 섹션 구조
        sections = self._extract_sections(soup)
        
        # 카테고리 추측 (URL 기반)
        category = self._guess_category(url)
        
        # 결과 반환
        return {
            'url': url,
            'title': title,
            'content': main_content,
            'content_hash': compute_content_hash(main_content),
            'sections': sections,
            'category': category,
            'word_count': len(main_content.split()),
            'crawled_at': datetime.now()
        }
    
    def _extract_with_bs4(self, html: str) -> str:
        """BeautifulSoup으로 본문 추출 (폴백)"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # <main>, <article> 태그 우선 탐색
        main = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
        
        if main:
            # 불필요한 태그 제거
            for tag in main.find_all(['nav', 'aside', 'footer', 'script', 'style']):
                tag.decompose()
            
            return main.get_text(separator='\n', strip=True)
        
        # 최후의 수단: body 전체
        body = soup.find('body')
        if body:
            return body.get_text(separator='\n', strip=True)
        
        return ""
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """제목 추출"""
        # <title> 태그
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # "Page Name | Dickinson College" → "Page Name"
            title = title.split('|')[0].strip()
            return title
        
        # <h1> 태그
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        
        return "Untitled"
    
    def _extract_sections(self, soup: BeautifulSoup) -> List[Dict]:
        """섹션 구조 추출 (헤더 기반)"""
        sections = []
        
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            section_title = heading.get_text(strip=True)
            
            # 다음 헤딩까지의 콘텐츠 수집
            content_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h1', 'h2', 'h3']:
                    break
                if sibling.name in ['p', 'ul', 'ol', 'div']:
                    text = sibling.get_text(strip=True)
                    if text:
                        content_parts.append(text)
            
            if content_parts:
                sections.append({
                    'level': heading.name,
                    'title': section_title,
                    'content': '\n'.join(content_parts)
                })
        
        return sections
    
    def _guess_category(self, url: str) -> str:
        """URL에서 카테고리 추측"""
        url_lower = url.lower()
        
        if '/academics' in url_lower:
            return 'academics'
        elif '/admissions' in url_lower:
            return 'admissions'
        elif '/campus-life' in url_lower or '/student-life' in url_lower:
            return 'campus_life'
        elif '/about' in url_lower:
            return 'about'
        elif '/news' in url_lower:
            return 'news'
        elif '/events' in url_lower:
            return 'events'
        elif '/athletics' in url_lower or '/sports' in url_lower:
            return 'athletics'
        else:
            return 'general'
    
    def crawl_page(self, url: str) -> Optional[Dict]:
        """
        단일 페이지 크롤링 (fetch + extract)
        
        Args:
            url: 크롤링할 URL
            
        Returns:
            추출된 콘텐츠 또는 None
        """
        logger.info(f"Crawling: {url}")
        
        # HTML 가져오기
        html = self.fetch_html(url)
        if not html:
            return None
        
        # 콘텐츠 추출
        try:
            content_data = self.extract_content(html, url)
            logger.info(f"✓ Extracted {content_data['word_count']} words from {url}")
            return content_data
        except Exception as e:
            logger.error(f"✗ Extraction failed for {url}: {e}")
            return None


# 테스트 코드
if __name__ == "__main__":
    extractor = ContentExtractor()
    
    # 테스트 URL
    test_url = "https://www.dickinson.edu/info/20103/computer_science/4051/computer_science_department_hours"
    
    result = extractor.crawl_page(test_url)
    
    if result:
        print(f"\n{'='*60}")
        print(f"URL: {result['url']}")
        print(f"Title: {result['title']}")
        print(f"Category: {result['category']}")
        print(f"Word Count: {result['word_count']}")
        print(f"Content Hash: {result['content_hash'][:16]}...")
        print(f"Sections: {len(result['sections'])}")
        print(f"\nContent:")
        print(result['content'])
        print(f"\nSections:")
        for i, section in enumerate(result['sections'][:3], 1):
            print(f"  {i}. [{section['level']}] {section['title']}")
    else:
        print("Crawling failed!")