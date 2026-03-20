"""Pagination utilities"""

from typing import List, Dict, Any
from math import ceil


class PaginationHelper:
    """Helper class for pagination"""
    
    @staticmethod
    def paginate_data(data: List[Any], page: int, per_page: int, total: int) -> Dict:
        """Create paginated response structure"""
        total_pages = ceil(total / per_page) if per_page > 0 else 1
        
        return {
            'data': data,
            'meta': {
                'page': page,
                'page_size': per_page,
                'total': total,
                'pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        }
    
    @staticmethod
    def validate_pagination_params(page: int, per_page: int, max_per_page: int = 100) -> tuple:
        """Validate and normalize pagination parameters"""
        page = max(1, page)
        per_page = max(1, min(per_page, max_per_page))
        
        return page, per_page
    
    @staticmethod
    def calculate_offset(page: int, per_page: int) -> int:
        """Calculate offset for database queries"""
        return (page - 1) * per_page
    
    @staticmethod
    def add_pagination_headers(response, page: int, per_page: int, total: int):
        """Add pagination headers to Flask response"""
        response.headers['X-Total-Count'] = str(total)
        response.headers['X-Page'] = str(page)
        response.headers['X-Per-Page'] = str(per_page)
        response.headers['X-Total-Pages'] = str(ceil(total / per_page) if per_page > 0 else 1)
        
        return response