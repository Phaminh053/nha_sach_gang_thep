"""Category model"""

from app.extensions import db
from app.models import BaseModel


class Category(BaseModel):
    """Category model mapping to categories table"""
    __tablename__ = 'categories'
    
    parent_id = db.Column(db.BigInteger, db.ForeignKey('categories.id'), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    intro = db.Column(db.Text, nullable=True)
    slug = db.Column(db.String(255), unique=True, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Relationships - loại bỏ self-referencing relationship phức tạp
    # Sẽ sử dụng query trực tiếp trong repository thay vì relationship
    
    def __repr__(self):
        return f'<Category {self.name}>'
    
    def to_dict(self, include_children=False):
        """Convert to dictionary"""
        result = {
            'id': self.id,
            'name': self.name,
            'intro': self.intro,
            'slug': self.slug,
            'parent_id': self.parent_id,
            'is_active': self.is_active
        }
        
        if include_children:
            # Sử dụng query trực tiếp thay vì relationship
            from app.repositories.category_repo import CategoryRepository
            repo = CategoryRepository()
            children = repo.get_children(self.id)
            result['children'] = [child.to_dict() for child in children]
            
        return result