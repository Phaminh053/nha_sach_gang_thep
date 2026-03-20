"""Review repository"""

from app.repositories import BaseRepository
from app.models import ProductReview
from sqlalchemy import desc
from typing import List, Optional, Tuple


class ReviewRepository(BaseRepository):
    """Repository for ProductReview operations"""
    
    def __init__(self, db_session=None):
        super().__init__(ProductReview)
        self.db_session = db_session
    
    def create(self, **kwargs):
        """Create new record using the provided session"""
        instance = self.model(**kwargs)
        if self.db_session:
            self.db_session.add(instance)
            self.db_session.flush()  # To get the ID
        else:
            # Fallback to default session
            super().create(**kwargs)
        return instance
    
    def get_product_reviews(self, product_id: int, page: int = 1, per_page: int = 10) -> Tuple[List[ProductReview], int]:
        """Get reviews for a product with pagination"""
        query = self.model.query.filter_by(product_id=product_id)\
                     .order_by(desc(ProductReview.created_at))
        
        total = query.count()
        offset = (page - 1) * per_page
        reviews = query.offset(offset).limit(per_page).all()
        
        return reviews, total
    
    def create_review(self, product_id: int, user_name: str, rating: int, content: str) -> ProductReview:
        """Create a new review"""
        return self.create(
            product_id=product_id,
            user_name=user_name,
            rating=rating,
            content=content
        )
    
    def get_admin_reviews(self, product_id: int = None, page: int = 1, per_page: int = 20) -> Tuple[List[ProductReview], int]:
        """Get reviews for admin panel"""
        query = self.model.query
        
        if product_id:
            query = query.filter_by(product_id=product_id)
        
        query = query.order_by(desc(ProductReview.created_at))
        
        total = query.count()
        offset = (page - 1) * per_page
        reviews = query.offset(offset).limit(per_page).all()
        
        return reviews, total


# Global instance
review_repo = ReviewRepository()