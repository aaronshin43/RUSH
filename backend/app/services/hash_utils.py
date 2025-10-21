import hashlib

def compute_content_hash(text: str) -> str:
    """
    텍스트의 SHA256 해시 생성
    
    Args:
        text: 해시할 텍스트
        
    Returns:
        16진수 해시 문자열
    """
    if not text:
        return ""
    
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def has_content_changed(old_hash: str, new_content: str) -> bool:
    """
    콘텐츠 변경 여부 확인
    
    Args:
        old_hash: 이전 해시값
        new_content: 새 콘텐츠
        
    Returns:
        변경 여부
    """
    new_hash = compute_content_hash(new_content)
    return old_hash != new_hash


# 테스트
if __name__ == "__main__":
    text1 = "Computer Science Major requirements aksjhfkjash vkjdsbsakfj absdjkfasbdflkj absdvkjcxjbvjksd..."
    text2 = "Computer Science Major requirements aksjhfkjash vkjdsbsakfj absdjkfasbdflkj absdvkjcxjbvjksd..."
    text3 = "Computer Science Major requirements!!! (Updated)"
    
    hash1 = compute_content_hash(text1)
    hash2 = compute_content_hash(text2)
    hash3 = compute_content_hash(text3)
    
    print(f"Hash 1: {hash1}")
    print(f"Hash 2: {hash2}")
    print(f"Same? {hash1 == hash2}")
    print(f"\nHash 3: {hash3}")
    print(f"Changed? {has_content_changed(hash1, text3)}")