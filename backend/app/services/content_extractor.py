from typing import Dict, List, Optional
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from trafilatura import extract
from trafilatura.settings import use_config
from urllib.parse import urlparse, parse_qs
import re
import base64

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

        # 우선순위 추측 (URL 기반)
        priority = self._determine_priority(url, category)
        
        # 결과 반환
        return {
            'url': url,
            'title': title,
            'content': main_content,
            'content_hash': compute_content_hash(main_content),
            'sections': sections,
            'category': category,
            'word_count': len(main_content.split()),
            'priority': priority,
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
        """
        섹션 구조 추출 (헤더 기반 - 메타데이터만)
        
        Note: 섹션 내용은 main_content에 이미 포함되므로 중복 저장 방지
              메타데이터만 추출하여 청킹 시 활용
        """
        sections = []
        
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            section_title = heading.get_text(strip=True)
            
            # 빈 제목 무시
            if section_title:
                sections.append({
                    'level': heading.name,
                    'title': section_title
                })
        
        return sections
    
    def _guess_category(self, url: str) -> str:
        """
        URL에서 카테고리 추측
        
        기본 카테고리를 먼저 확인하고, 
        'general'로 분류될 경우에만 대분류 레벨로 그룹화
        """
        
        # ==================== 0단계: URL 파싱 ====================
        try:
            parsed_url = urlparse(url)
            host = parsed_url.netloc.lower()
            path = parsed_url.path.lower()
        except Exception:
            return 'general'
        
        # ==================== 1단계: 기본 카테고리 체크 (경로 기반) ====================
        if '/academics' in path:
            return 'academics'
        elif '/admissions' in path:
            return 'admissions'
        elif '/campus-life' in path or '/student-life' in path:
            return 'campus_life'
        elif '/about' in path:
            return 'about'
        elif '/news' in path:
            return 'news'
        elif '/events' in path:
            return 'events'
        elif '/athletics' in path or '/sports' in path:
            return 'athletics'
        
        # ==================== 2단계: general 대분류 그룹화 ====================
        
        # 서브도메인 체크 (간소화)
        if 'admissions.' in host:
            return 'admissions'
        
        if 'athletics.' in host:
            return 'athletics'
            
        if 'jobs.' in host:
            return 'general_careers'

        if 'campusstore.' in host:
            return 'general_campus_store'

        # 경로 분석
        path_parts = [p for p in path.split('/') if p]
        if not path_parts:
            return 'general'

        # ID 기반 경로에서 키워드 추출 후 매핑
        # 패턴 1: /homepage/{id}/{keyword}
        match_homepage = re.search(r'/homepage/(\d+)/([\w-]+)', path)
        if match_homepage:
            keyword = match_homepage.group(2).replace('-', '_')
            return self._map_to_major_category(keyword)

        # 패턴 2: /info/{id}/{category}/...
        match_info = re.search(r'/info/(\d+)/([\w_-]+)', path)
        if match_info:
            keyword = match_info.group(2).replace('-', '_')
            return self._map_to_major_category(keyword)

        # 첫 번째 경로 세그먼트 기반
        main_segment = path_parts[0].replace('-', '_')
        return self._map_to_major_category(main_segment)

    def _map_to_major_category(self, keyword: str) -> str:
        """
        키워드를 주요 대분류 카테고리로 매핑
        노이즈 단어를 제거하고 핵심 의미만 추출
        """
        
        # ==================== 노이즈 단어 제거 ====================
        noise_words = [
            # 조직 관련
            'office', 'offices', 'department', 'departments', 'division',
            'unit', 'bureau', 'agency',
            
            # 서비스/프로그램 관련
            'services', 'service', 'program', 'programs', 'initiative', 'initiatives',
            
            # 장소 관련
            'center', 'centers', 'centre', 'centres'
            
            # 일반 단어
            'of', 'the', 'and', 'for', 'page', 'site', 'website',
            'information', 'info', 'resources', 'resource',
            
            # 학교 관련
            'college', 'university', 'dickinson',
            
            # 설명 단어
            'overview', 'about', 'welcome', 'home', 'homepage',
            'main', 'general', 'quick', 'facts', 'fact'
        ]
        
        # 키워드 정규화: 소문자 변환 및 노이즈 제거
        keyword_cleaned = keyword.lower()
        
        # 정확한 단어 경계로 제거 (부분 매칭 방지)
        for noise in noise_words:
            # 단어 경계에서만 제거
            keyword_cleaned = re.sub(rf'\b{noise}\b', '', keyword_cleaned)
        
        # 중복 언더스코어 제거 및 정리
        keyword_cleaned = re.sub(r'_+', '_', keyword_cleaned).strip('_')
        
        # 빈 문자열이면 general
        if not keyword_cleaned:
            return 'general'
        
        # ==================== 카테고리 매핑 ====================
        
        # 이벤트/캘린더 관련
        if any(kw in keyword_cleaned for kw in [
            'event', 'calendar', 'schedule', 'commencement', 'graduation',
            'ceremony', 'celebration', 'festival', 'conference'
        ]):
            return 'events'
        
        # 뉴스/미디어/커뮤니케이션 관련
        if any(kw in keyword_cleaned for kw in [
            'news', 'article', 'magazine', 'publication', 'announcement',
            'media', 'press', 'release', 'story', 'communication',
            'wdcvfm', 'radio', 'limestone', 'broadcast', 'dickinsonmag'
        ]):
            return 'news'

        # 학업 관련
        if any(kw in keyword_cleaned for kw in [
            'academic', 'faculty', 'research', 'registrar', 'advising', 'advisor',
            'education', 'abroad', 'global', 'international', 'writing', 'seminar',
            'bulletin', 'learning', 'teaching', 'curriculum', 'course',
            'research', 'institute', 'lab', 'laboratory', 'study', 'studies'
        ]):
            return 'academics'
        
        # 입학 관련
        if any(kw in keyword_cleaned for kw in [
            'admission', 'apply', 'application', 'applicant', 'prospective',
            'visit', 'tour', 'guide', 'transfer', 'deadline', 'admitted',
            'decision', 'early', 'regular', 'requirement', 'checklist'
        ]):
            return 'admissions'
        
        # 학생 생활 관련
        if any(kw in keyword_cleaned for kw in [
            'student', 'campus', 'living', 'housing', 'residential', 'residence',
            'dining', 'meal', 'wellness', 'health', 'counseling', 'counselor',
            'disability', 'lgbtq', 'religious', 'religion', 'senate',
            'leadership', 'leader', 'intramural', 'recreation', 'rec',
            'tradition', 'orientation', 'dean', 'greek', 'fraternity', 'sorority',
            'building', 'hall', 'life_at_dickinson', 'daily_menus', 'policies', 'asbell_center'
        ]):
            return 'campus_life'
        
        # 재정 지원 관련
        if any(kw in keyword_cleaned for kw in [
            'financial', 'aid', 'scholarship', 'grant', 'tuition', 'fee',
            'cost', 'cashier', 'payment', 'billing', 'account', 'bursar'
        ]):
            return 'general_financial'
        
        # 커리어/동문 관련
        if any(kw in keyword_cleaned for kw in [
            'career', 'alumni', 'alumnus', 'alumnae', 'job', 'employment',
            'internship', 'extern', 'homecoming', 'reunion', 'network',
            'notable', 'graduate'
        ]):
            return 'general_alumni_careers'

        # 시설/서비스/안전 관련
        if any(kw in keyword_cleaned for kw in [
            'facilities', 'facility', 'library', 'libraries', 'technology', 'tech',
            'it', 'mail', 'postal', 'print', 'printing', 'safety', 'security',
            'parking', 'transportation', 'public', 'police', 'emergency'
        ]):
            return 'general_facilities'
        
        # 기부/지원/발전 관련
        if any(kw in keyword_cleaned for kw in [
            'give', 'giving', 'donate', 'donation', 'donor', 'gift',
            'fund', 'endowment', 'advancement', 'development', 'annual',
            'matching', 'match', 'volunteer', 'philanthropy', 'support',
            'ira', 'planned', 'estate', 'legacy', 'corporate', 'foundation',
            'rog', 'thank_you', 'change'
        ]):
            return 'general_giving'
        
        # 커뮤니티/다양성/참여 관련
        if any(kw in keyword_cleaned for kw in [
            'community', 'civic', 'sustainability', 'sustainable', 'environment',
            'allarm', 'conflict', 'resolution', 'prevention', 'respect',
            'diversity', 'diverse', 'inclusion', 'inclusive', 'equity', 'equitable',
            'engagement', 'engage', 'multicultural', 'intercultural'
        ]):
            return 'general_community'
        
        # 학부모/가족 관련
        if any(kw in keyword_cleaned for kw in [
            'parent', 'parents', 'family', 'families', 'guardian'
        ]):
            return 'general_parents'
        
        # 예술/문화 관련
        if any(kw in keyword_cleaned for kw in [
            'art', 'arts', 'gallery', 'museum', 'exhibit', 'exhibition',
            'theater', 'theatre', 'music', 'musical', 'performance',
            'performing', 'dance', 'drama', 'visual', 'coa'
        ]):
            return 'general_arts'
        
        # 행정/운영 관련
        if any(kw in keyword_cleaned for kw in [
            'administrative', 'administration', 'hr', 'human', 'payroll',
            'business', 'operations', 'operational', 'management', 'policy'
        ]):
            return 'general_administrative'
        
        # 캠퍼스 스토어 관련
        if any(kw in keyword_cleaned for kw in [
            'store', 'shop', 'bookstore', 'merchandise', 'apparel', 'gear'
        ]):
            return 'general_campus_store'
        
        # 최종 fallback
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
    
    def _determine_priority(self, url: str, category: str) -> str:
        """
        URL 기반 우선순위 결정 (3단계: high/low/static)
        
        priority.txt 기준:
        - High: 매일 업데이트 (뉴스, 이벤트, 공지)
        - Low: 매주 업데이트 (기본값)
        - Static: 분기별/수동 (아카이브, 개별 기사, 프로필)
        
        Returns:
            'high' | 'low' | 'static'
        """
        from urllib.parse import urlparse
        import re
        
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.strip('/')
        url_lower = url.lower()
        
        segments = [s for s in path.split('/') if s]
        depth = len(segments)
        
        # ==================== 외부 도메인 처리 ====================
        
        if "dickinson.edu" not in domain:
            # nutrislice (식당 메뉴) - 매일 변경
            if 'nutrislice.com' in domain:
                return 'high'
            # campuslabs (동아리 정보) - 매주 업데이트
            elif 'campuslabs.com' in domain:
                return 'low'
            # 기타 외부 도메인은 Low
            else:
                return 'low'
        
        # ==================== 서브도메인 처리 ====================
        
        if domain != "www.dickinson.edu":
            # archives 서브도메인
            if 'archives' in domain:
                return 'static'
            # 기타 서브도메인
            else:
                return 'low'
        
        # ==================== High Priority (매일) ====================
        
        # 1. 루트 레벨 중요 페이지 (depth 0-1)
        if depth <= 1:
            if any(seg in segments for seg in ['news', 'announcements', 'events']):
                return 'high'
        
        # 2. 뉴스/이벤트 메인 및 카테고리 페이지
        if depth >= 1 and segments[0] in ['news', 'events', 'announcements']:
            if depth == 1:
                # /news/, /events/ (메인 페이지)
                return 'high'
            if depth == 2 and segments[1] not in ['article', 'event', 'story', 'archive']:
                # /news/category/, /events/upcoming/ (카테고리 페이지)
                return 'high'
        
        # 3. 입학 중요 페이지
        if depth >= 2 and segments[0] == 'admissions':
            if segments[1] in ['apply', 'deadlines', 'visit']:
                return 'high'
        
        # ==================== Static Priority (분기별/수동) ====================
        
        # 1. 개별 아티클 (depth 3+)
        if depth >= 3:
            if segments[0] in ['news', 'events']:
                if segments[1] in ['article', 'event', 'story']:
                    return 'static'
        
        # 2. 키워드 기반 (세그먼트 매칭)
        if any(keyword in segments for keyword in ['stories', 'archive', 'newsletter']):
            return 'static'
        
        # 3. 특정 페이지 (URL 전체 매칭)
        if '/dc_faculty_profile' in url_lower or '/campusphotogallery' in url_lower:
            return 'static'
        
        # 4. 과거 년도 콘텐츠 (ID 패턴 제외)
        # /info/ID 또는 /homepage/ID 패턴이 아닌 경우만 체크
        is_id_pattern = False
        if depth >= 2:
            if segments[0] in ['info', 'homepage'] and segments[1].isdigit():
                is_id_pattern = True
        
        if not is_id_pattern:
            # 4자리 년도 찾기 (1900-2024)
            year_match = re.search(r'/(\d{4})/', f'/{path}/')
            if year_match:
                year = int(year_match.group(1))
                current_year = datetime.now().year
                
                # 1900-2024년 사이이고 현재 년도 이전
                if 1900 <= year <= 2024 and year < current_year:
                    return 'static'
        
        # ==================== Low Priority (매주 - 기본값) ====================
        
        # 나머지 모든 페이지:
        # - 학과/프로그램 (/academics, /courses, /majors)
        # - 학생 생활 (/campus-life, /housing, /dining, /clubs)
        # - 도서관/리소스 (/library, /resources)
        # - 입학 정보 일반 (/admissions/*, /financial-aid, /scholarships)
        # - 시설/교통 (/facilities, /parking, /transportation)
        # - 연구/인턴십 (/research, /internships, /study-abroad)
        # - About/정책 (/about, /mission, /contact, /policies, /faq)
        
        return 'low'

# 테스트 코드
if __name__ == "__main__":
    extractor = ContentExtractor()
    
    # # 테스트 URL
    # test_url = "https://www.dickinson.edu/info/20103/computer_science/4051/computer_science_department_hours"
    
    # result = extractor.crawl_page(test_url)
    
    # if result:
    #     print(f"\n{'='*60}")
    #     print(f"URL: {result['url']}")
    #     print(f"Title: {result['title']}")
    #     print(f"Category: {result['category']}")
    #     print(f"Word Count: {result['word_count']}")
    #     print(f"Content Hash: {result['content_hash'][:16]}...")
    #     print(f"Sections: {len(result['sections'])}")
    #     print(f"\nContent:")
    #     print(result['content'])
    #     print(f"\nSections:")
    #     for i, section in enumerate(result['sections'][:3], 1):
    #         print(f"  {i}. [{section['level']}] {section['title']}")
    # else:
    #     print("Crawling failed!")

    # 테스트 케이스
    test_cases = [
        # High Priority
        ("https://www.dickinson.edu/news/20052/", "high"),
        ("https://www.dickinson.edu/news", "high"),
        ("https://www.dickinson.edu/announcements/", "high"),
        ("https://www.dickinson.edu/events/", "high"),
        ("https://www.dickinson.edu/admissions/apply", "high"),
        ("https://www.dickinson.edu/admissions/deadlines", "high"),
        ("https://dickinson.nutrislice.com/menu", "high"),
        
        # Static Priority
        ("https://www.dickinson.edu/news/article/6260/riding_together_through_teamwork_competition_and_community", "static"),
        ("https://www.dickinson.edu/events/event/456/homecoming", "static"),
        ("https://www.dickinson.edu/stories/alumni-success", "static"),
        ("https://www.dickinson.edu/news/archive", "static"),
        ("https://www.dickinson.edu/newsletter/2023-fall", "static"),
        ("https://www.dickinson.edu/dc_faculty_profile/john-smith", "static"),
        ("https://www.dickinson.edu/campusphotogallery", "static"),
        ("https://www.dickinson.edu/news/2022/article/123", "static"),
        ("https://www.dickinson.edu/events/event/30643/cookies_for_kids_cancer", "static"),
        ("https://archives.dickinson.edu/collections", "static"),
        
        # Low Priority
        ("https://www.dickinson.edu/homepage/536/dickinson_in_the_news", "low"),
        ("https://www.dickinson.edu/academics/programs/computer-science", "low"),
        ("https://www.dickinson.edu/campus-life/", "low"),
        ("https://www.dickinson.edu/admissions/", "low"),
        ("https://www.dickinson.edu/admissions/financial-aid", "low"),
        ("https://www.dickinson.edu/about/", "low"),
        ("https://www.dickinson.edu/contact", "low"),
        ("https://dickinson.campuslabs.com/engage/organizations", "low"),
        
        # Edge Cases (ID 패턴 - Low)
        ("https://www.dickinson.edu/info/20032/mathematics/1426", "low"),
        ("https://www.dickinson.edu/homepage/1984/computer_science", "low"),
        ("https://www.dickinson.edu/homepage/402/curriculum", "low"),
        
        # Edge Cases (오탐지 방지)
        ("https://www.dickinson.edu/fake-news/", "low"),  # 'news' 포함하지만 세그먼트 아님
        ("https://www.dickinson.edu/student-histories", "low"),  # 'stories' 포함하지만 세그먼트 아님
        ("https://www.dickinson.edu/monthly-newsletter", "low"),  # 'newsletter' 포함하지만 세그먼트 아님
        ("https://www.dickinson.edu/events-archive/", "low"),  # 'archive' 포함하지만 세그먼트 아님
    ]
    
    print("\n" + "="*80)
    print("Priority Determination Tests (priority.txt 기준)")
    print("="*80)
    
    passed = 0
    failed = 0
    
    for url, expected in test_cases:
        category = extractor._guess_category(url)
        priority = extractor._determine_priority(url, category)
        
        status = "✅" if priority == expected else "❌"
        if priority == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} {priority:8} (expected: {expected:8}) | {url}")
    
    print("\n" + "="*80)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*80)