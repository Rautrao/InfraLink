from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar("T")
class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

def paginate(items, page: int = 1, page_size: int = 20):
    page, page_size = max(page, 1), min(max(page_size, 1), 100)
    return {"items": items[(page-1)*page_size:page*page_size], "total": len(items), "page": page, "page_size": page_size}
