from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Optional
import re

class URLNormalizer:
    """URL 정규화 및 검증"""
    
    ALLOWED_DOMAIN = "dickinson.edu"

    # 화이트리스트 외부 도메인
    WHITELIST_DOMAINS = [
        'dickinson.campuslabs.com',    # 동아리 정보
        'dickinson.nutrislice.com',    # 식당 메뉴
    ]
    
    # 블랙리스트 패턴
    BLACKLIST_PATTERNS = [
        # 시스템 페이지
        r'/login',
        r'/signin',
        r'/404',
        r'/error',
        
        # 검색/동적 페이지
        r'/site/scripts/google_results\.php',
        r'/search\?',
        r'\?query=',
        r'#gsc\.tab=',
        r'#gsc\.q=',
        
        # 파일 다운로드
        r'\.pdf$',
        r'\.docx?$',
        r'\.xlsx?$',
        r'\.pptx?$',
        r'\.zip$',
        r'\.rar$',
        
        # 미디어 파일
        r'\.jpg$',
        r'\.jpeg$',
        r'\.png$',
        r'\.gif$',
        r'\.svg$',
        r'\.mp4$',
        r'\.mp3$',
        r'\.mov$',
        r'\.avi$',
        
        # 기타
        r'/gateway'
    ]
    
    # 제거할 쿼리 파라미터 (추적 파라미터)
    REMOVE_PARAMS = [
        'utm_source', 'utm_medium', 'utm_campaign', 
        'utm_term', 'utm_content',
        'gclid', 'fbclid', 'msclkid',
        'ref', 'referrer'
    ]
    
    @classmethod
    def normalize(cls, url: str) -> Optional[str]:
        """
        URL 정규화
        
        Returns:
            정규화된 URL 또는 None (유효하지 않은 경우)
        """
        try:
            # 1. 소문자 변환
            url = url.lower().strip()
            
            # 2. URL 파싱
            parsed = urlparse(url)
            
            # 3. 스킴 확인 (https 강제)
            scheme = 'https'
            
            # 4. Path 정규화 (trailing slash 제거)
            path = parsed.path.rstrip('/')
            if not path:
                path = '/'
            
            # 5. 쿼리 파라미터 필터링
            query_dict = parse_qs(parsed.query)
            filtered_query = {
                k: v for k, v in query_dict.items()
                if k not in cls.REMOVE_PARAMS
            }
            query = urlencode(filtered_query, doseq=True)
            
            # 6. Fragment 제거
            fragment = ''
            
            # 7. 정규화된 URL 생성
            normalized = urlunparse((
                scheme, parsed.netloc, path, '', query, fragment
            ))
            
            # 8. 도메인 및 블랙리스트 검증
            if not cls.is_valid_dickinson_url(normalized):
                return None
            
            return normalized
            
        except Exception as e:
            print(f"URL normalization error for {url}: {e}")
            return None
    
    @classmethod
    def is_whitelisted_domain(cls, netloc: str) -> bool:
        """화이트리스트 도메인 체크"""
        return any(domain in netloc for domain in cls.WHITELIST_DOMAINS)

    @classmethod
    def is_blacklisted(cls, url: str) -> bool:
        """블랙리스트 체크"""
        for pattern in cls.BLACKLIST_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def is_valid_dickinson_url(cls, url: str) -> bool:
        """
        Dickinson 또는 화이트리스트 URL인지 확인 (블랙리스트 포함)
        
        Returns:
            True: 유효한 URL
            False: 차단할 URL
        """
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.replace('www.', '')
            
            # 1. 도메인 검증
            is_whitelisted = cls.is_whitelisted_domain(netloc)
            is_dickinson = cls.ALLOWED_DOMAIN in netloc
            
            if not (is_whitelisted or is_dickinson):
                return False
            
            # 2. 블랙리스트 검증
            if cls.is_blacklisted(url):
                return False
            
            return True
            
        except:
            return False
        
    @classmethod
    def get_domain_type(cls, url: str) -> str:
        """
        도메인 타입 반환
        
        Returns:
            'dickinson' | 'whitelist' | 'external'
        """
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.replace('www.', '')
            
            if cls.is_whitelisted_domain(netloc):
                return 'whitelist'
            elif cls.ALLOWED_DOMAIN in netloc:
                return 'dickinson'
            else:
                return 'external'
        except:
            return 'external'


# 테스트 코드
if __name__ == "__main__":
    test_urls = [
        # 허용 - Dickinson
        "https://www.dickinson.edu/academics/",
        "https://dickinson.edu/ACADEMICS",
        "https://dickinson.edu/academics#section",
        "https://dickinson.edu/academics?utm_source=google",
        
        # 허용 - 화이트리스트
        "https://dickinson.campuslabs.com/engage/organizations",
        "https://dickinson.nutrislice.com/menu",
        
        # 차단 - 블랙리스트 패턴
        "https://dickinson.edu/login",
        "https://www.dickinson.edu/download/downloads/id/16666/student_handbook_2025-26.pdf",
        
        # 차단 - 외부 도메인 (자동)
        "https://harvard.edu/page",
        "https://zoom.us/meeting/123",
        "https://google.com/search",
        
        # 허용 - 일반 페이지
        "https://www.dickinson.edu/homepage/1062/gateway_directory#/form/departments",
        "https://www.dickinson.edu/homepage/285/academics",
        "https://www.dickinson.edu/info/20211/career_center/514/alumni_-_career_services",
    ]
    
    print("=" * 80)
    print("URL Normalization Tests")
    print("=" * 80)
    
    for url in test_urls:
        normalized = URLNormalizer.normalize(url)
        domain_type = URLNormalizer.get_domain_type(url)
        
        print(f"\n원본: {url}")
        print(f"타입: {domain_type}")
        print(f"결과: {normalized if normalized else '❌ BLOCKED'}")