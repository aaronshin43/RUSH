from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId


class PyObjectId(str):
    """MongoDB ObjectId를 문자열로 처리"""
    
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler):
        from pydantic_core import core_schema
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),
            core_schema.chain_schema([
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(cls.validate),
            ])
        ])
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return str(v)


class Section(BaseModel):
    """섹션 구조"""
    level: str
    title: str
    
    model_config = ConfigDict(from_attributes=True)


class Document(BaseModel):
    """크롤링된 문서 모델"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    url: str = Field(..., description="Page URL")
    normalized_url: str = Field(..., description="Normalized URL")
    title: str = Field(..., description="Page title")
    category: str = Field(..., description="Page category")
    content: str = Field(..., description="Body text")
    content_hash: str = Field(..., description="Content hash (SHA256)")
    sections: List[Section] = Field(default_factory=list, description="Section structure")
    word_count: int = Field(default=0, description="Number of words")
    priority: str = Field(default="medium", description="Update Priority (high/medium/low)")
    crawled_at: datetime = Field(default_factory=datetime.now)
    last_updated: Optional[datetime] = None
    status: str = "active"  # active, inactive, error
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        from_attributes=True
    )


class DocumentRepositoryAsync:
    """MongoDB Document 저장소"""
    
    def __init__(self, db):
        self.collection = db.documents
    
    async def create(self, document: Document) -> str:
        """문서 생성"""
        doc_dict = document.model_dump(by_alias=True, exclude={"id"})
        result = await self.collection.insert_one(doc_dict)
        return str(result.inserted_id)
    
    async def find_by_url(self, url: str) -> Optional[Document]:
        """URL로 문서 찾기"""
        doc = await self.collection.find_one({"normalized_url": url})
        if doc:
            return Document(**doc)
        return None
    
    async def update_content(
        self, 
        url: str, 
        content: str, 
        content_hash: str,
        sections: List[Dict]
    ) -> bool:
        """콘텐츠 업데이트"""
        result = await self.collection.update_one(
            {"normalized_url": url},
            {
                "$set": {
                    "content": content,
                    "content_hash": content_hash,
                    "sections": sections,
                    "last_updated": datetime.now()
                }
            }
        )
        return result.modified_count > 0
    
    async def get_all_urls(self) -> List[str]:
        """모든 문서의 URL 가져오기"""
        cursor = await self.collection.find({}, {"normalized_url": 1})
        urls = []
        async for doc in cursor:
            urls.append(doc["normalized_url"])
        return urls
    
    async def get_urls_by_priority(self, priority: str) -> List[str]:
        """우선순위별 URL 목록 가져오기"""
        documents = await self.collection.find(
            {'priority': priority},
            {'url': 1, '_id': 0}
        )
        return [doc['url'] async for doc in documents]
    
    async def count(self) -> int:
        """총 문서 수"""
        return await self.collection.count_documents({})
    
    async def get_statistics(self) -> Dict:
        """통계 정보"""
        pipeline = [
            {
                "$group": {
                    "_id": "$category",
                    "count": {"$sum": 1},
                    "total_words": {"$sum": "$word_count"}
                }
            }
        ]
        
        stats = {"categories": {}}
        async for doc in self.collection.aggregate(pipeline):
            stats["categories"][doc["_id"]] = {
                "count": doc["count"],
                "total_words": doc["total_words"]
            }
        
        stats["total_documents"] = await self.count()
        return stats
    
    async def delete_by_url(self, url: str) -> bool:
        """URL로 문서 삭제"""
        result = await self.collection.delete_one({"normalized_url": url})
        return result.deleted_count > 0

class DocumentRepository:
    """MongoDB Document 저장소"""
    
    def __init__(self, db):
        self.collection = db.documents
    
    def create(self, document: Document) -> str:
        """문서 생성"""
        doc_dict = document.model_dump(by_alias=True, exclude={"id"})
        result = self.collection.insert_one(doc_dict)
        return str(result.inserted_id)
    
    def find_by_url(self, url: str) -> Optional[Document]:
        """URL로 문서 찾기"""
        doc = self.collection.find_one({"normalized_url": url})
        if doc:
            return Document(**doc)
        return None
    
    def update_content(
        self, 
        url: str, 
        content: str, 
        content_hash: str,
        sections: List[Dict]
    ) -> bool:
        """콘텐츠 업데이트"""
        result = self.collection.update_one(
            {"normalized_url": url},
            {
                "$set": {
                    "content": content,
                    "content_hash": content_hash,
                    "sections": sections,
                    "last_updated": datetime.now()
                }
            }
        )
        return result.modified_count > 0
    
    def get_all_urls(self) -> List[str]:
        """모든 문서의 URL 가져오기"""
        cursor = self.collection.find({}, {"normalized_url": 1})
        urls = []
        for doc in cursor:
            urls.append(doc["normalized_url"])
        return urls
    
    def get_urls_by_priority(self, priority: str) -> List[str]:
        """우선순위별 URL 목록 가져오기"""
        documents = self.collection.find(
            {'priority': priority},
            {'url': 1, '_id': 0}
        )
        return [doc['url'] for doc in documents]
    
    def count(self) -> int:
        """총 문서 수"""
        return self.collection.count_documents({})
    
    def get_statistics(self) -> Dict:
        """통계 정보"""
        pipeline = [
            {
                "$group": {
                    "_id": "$category",
                    "count": {"$sum": 1},
                    "total_words": {"$sum": "$word_count"}
                }
            }
        ]
        
        stats = {"categories": {}}
        for doc in self.collection.aggregate(pipeline):
            stats["categories"][doc["_id"]] = {
                "count": doc["count"],
                "total_words": doc["total_words"]
            }
        
        stats["total_documents"] = self.count()
        return stats
    
    def delete_by_url(self, url: str) -> bool:
        """URL로 문서 삭제"""
        result = self.collection.delete_one({"normalized_url": url})
        return result.deleted_count > 0