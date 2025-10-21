from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Optional
import re

class URLNormalizer:
    """URL 정규화 및 검증"""
    
    ALLOWED_DOMAIN = "dickinson.edu"
    
    # 블랙리스트 패턴
    BLACKLIST_PATTERNS = [
        r'/login',
        r'/signin',
        r'/gateway_directory',
        r'/search\?',
        r'\.pdf$',
        r'\.doc[x]?$',
        r'\.xls[x]?$',
        r'\.zip$',
        r'\.jpg$',
        r'\.jpeg$',
        r'\.png$',
        r'\.gif$',
        r'\.svg$',
        r'\.mp4$',
        r'\.mp3$',
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
            
            # 4. www 유지
            netloc = parsed.netloc
            
            # 5. 도메인 검증
            if cls.ALLOWED_DOMAIN not in netloc:
                return None
            
            # 6. Path 정규화 (trailing slash 제거)
            path = parsed.path.rstrip('/')
            if not path:
                path = '/'
            
            # 7. 쿼리 파라미터 필터링
            query_dict = parse_qs(parsed.query)
            filtered_query = {
                k: v for k, v in query_dict.items()
                if k not in cls.REMOVE_PARAMS
            }
            query = urlencode(filtered_query, doseq=True)
            
            # 8. Fragment 제거
            fragment = ''
            
            # 9. 정규화된 URL 생성
            normalized = urlunparse((
                scheme, netloc, path, '', query, fragment
            ))
            
            # 10. 블랙리스트 체크
            if cls.is_blacklisted(normalized):
                return None
            
            return normalized
            
        except Exception as e:
            print(f"URL normalization error for {url}: {e}")
            return None
    
    @classmethod
    def is_blacklisted(cls, url: str) -> bool:
        """블랙리스트 체크"""
        for pattern in cls.BLACKLIST_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def is_valid_dickinson_url(cls, url: str) -> bool:
        """Dickinson URL인지 확인"""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.replace('www.', '')
            return cls.ALLOWED_DOMAIN in netloc
        except:
            return False


# 테스트 코드
if __name__ == "__main__":
    test_urls = [
        "https://www.dickinson.edu/academics/",
        "https://dickinson.edu/ACADEMICS",
        "https://dickinson.edu/academics#section",
        "https://dickinson.edu/academics?utm_source=google",
        "https://dickinson.edu/login",
        "https://www.dickinson.edu/download/downloads/id/16666/student_handbook_2025-26.pdf",
        "https://harvard.edu/page",
        "https://www.dickinson.edu/homepage/1062/gateway_directory#/form/departments",
        "https://www.dickinson.edu/homepage/285/academics",
        "https://www.dickinson.edu/info/20211/career_center/514/alumni_-_career_services",
        "https://www.dickinson.edu/info/20158/writing_program/800/writing_program_staff"

    ]
    
    print("URL Normalization Tests:")
    for url in test_urls:
        normalized = URLNormalizer.normalize(url)
        print(f"  {url}")
        print(f"  → {normalized}\n")