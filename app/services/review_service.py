"""Review service for managing product reviews"""

from app.repositories.review_repo import review_repo
from app.repositories.product_repo import product_repo
from app.extensions import db
from typing import Dict, List, Tuple


class ReviewService:
    """Service for review management"""
    
    def create_review(self, product_id: int, user_name: str, rating: int, content: str) -> Dict:
        """Create a new product review"""
        # Validate rating
        if not (1 <= rating <= 5):
            raise ValueError("Rating must be between 1 and 5")
        
        # Create review
        review = review_repo.create_review(
            product_id=product_id,
            user_name=user_name,
            rating=rating,
            content=content
        )
        
        db.session.commit()
        return review.to_dict()
    
    def get_product_reviews(self, product_slug: str, page: int = 1, per_page: int = 10) -> Tuple[List[Dict], int]:
        """Get reviews for a product"""
        # Get product by slug
        product = product_repo.get_by_slug(product_slug)
        if not product:
            raise ValueError(f"Product with slug '{product_slug}' not found")
        
        reviews, total = review_repo.get_product_reviews(product.id, page, per_page)
        
        return [review.to_dict() for review in reviews], total
    
    def get_admin_reviews(self, product_id: int = None, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """Get reviews for admin panel"""
        reviews, total = review_repo.get_admin_reviews(product_id, page, per_page)
        
        # Include product info in admin view
        review_dicts = []
        for review in reviews:
            review_dict = review.to_dict()
            # Add product name for admin convenience
            if hasattr(review, 'product'):
                review_dict['product_name'] = review.product.name
            review_dicts.append(review_dict)
        
        return review_dicts, total
    
    def delete_review(self, review_id: int) -> bool:
        """Delete a review (admin only)"""
        review = review_repo.get_by_id(review_id)
        if not review:
            return False
        
        review_repo.delete(review)
        db.session.commit()
        return True
    
    def validate_review_content(self, content: str) -> bool:
        """Validate review content"""
        if not content or len(content.strip()) < 5:
            return False
        
        # Add more validation rules here if needed
        # e.g., profanity filter, spam detection
        
        return True


# Global instance
review_service = ReviewService()