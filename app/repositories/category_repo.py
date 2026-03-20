"""Category repository"""

from app.repositories import BaseRepository
from app.models import Category
from typing import List, Optional


class CategoryRepository(BaseRepository):
    """Repository for Category operations"""
    
    def __init__(self, db_session=None):
        super().__init__(Category)
        self.db_session = db_session
    
    def get_by_slug(self, slug: str) -> Optional[Category]:
        """Get category by slug"""
        return self.model.query.filter_by(slug=slug).first()
    
    def get_root_categories(self) -> List[Category]:
        """Get all root categories (no parent)"""
        return self.model.query.filter_by(parent_id=None).all()
    
    def get_category_tree(self) -> List[Category]:
        """Get category tree with children"""
        root_categories = self.get_root_categories()
        return root_categories
    
    def get_children(self, category_id: int) -> List[Category]:
        """Get children of a category"""
        return self.model.query.filter_by(parent_id=category_id).all()
    
    def get_parent(self, category: Category) -> Optional[Category]:
        """Get parent of a category"""
        if category.parent_id:
            return self.model.query.get(category.parent_id)
        return None
    
    def get_by_name(self, name: str) -> Optional[Category]:
        """Get category by name"""
        return self.model.query.filter_by(name=name).first()
    
    def search(self, query: str) -> List[Category]:
        """Search categories by name"""
        return self.model.query.filter(
            Category.name.ilike(f'%{query}%')
        ).all()
    
    def get_all_active(self) -> List[Category]:
        """Get all active categories (since there's no active field, return all)"""
        return self.model.query.all()
    
    def get_all_with_hierarchy(self) -> List[Category]:
        """Get all categories with hierarchy structure"""
        return self.get_root_categories()


# Global instance
category_repo = CategoryRepository()