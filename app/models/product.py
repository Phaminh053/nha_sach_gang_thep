"""Product related models"""

from app.extensions import db
from app.models import BaseModel
from sqlalchemy import text


class Product(BaseModel):
    """Product model mapping to products table"""
    __tablename__ = 'products'
    
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=True)
    short_desc = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(1024), nullable=True)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    
    # Book specific fields
    isbn13 = db.Column(db.String(20), nullable=True)
    sku = db.Column(db.String(64), nullable=True)
    authors = db.Column(db.String(512), nullable=True)
    translators = db.Column(db.String(512), nullable=True)
    illustrators = db.Column(db.String(512), nullable=True)
    publisher_name = db.Column(db.String(255), nullable=True)
    publish_year = db.Column(db.Integer, nullable=True)
    pages = db.Column(db.Integer, nullable=True)
    dimensions_raw = db.Column(db.String(64), nullable=True)
    width_cm = db.Column(db.Numeric(8, 2), nullable=True)
    height_cm = db.Column(db.Numeric(8, 2), nullable=True)
    thickness_mm = db.Column(db.Numeric(8, 2), nullable=True)
    age_min = db.Column(db.Integer, nullable=True)
    age_max = db.Column(db.Integer, nullable=True)
    
    sale_price = db.Column(db.Numeric(12, 2), nullable=True)
    sale_start = db.Column(db.DateTime, nullable=True)
    sale_end = db.Column(db.DateTime, nullable=True)
    sale_active = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    view_count = db.Column(db.Integer, default=0, server_default='0')
    
    # Relationships
    categories = db.relationship('Category', secondary='product_categories', backref='products')
    images = db.relationship('ProductImage', backref='product', cascade='all, delete-orphan')
    stock = db.relationship('ProductStock', backref='product', uselist=False, cascade='all, delete-orphan')
    reviews = db.relationship('ProductReview', backref='product', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Product {self.name}>'
    
    @property
    def in_stock(self):
        """Check if product is in stock"""
        return self.stock and self.stock.qty_on_hand > 0
    
    def to_dict(self, include_relations=False):
        """Convert to dictionary"""
        result = {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'short_desc': self.short_desc,
            'image_url': self.image_url,
            'price': float(self.price) if self.price is not None else None,
            'isbn13': self.isbn13,
            'sku': self.sku,
            'authors': self.authors,
            'translators': self.translators,
            'illustrators': self.illustrators,
            'publisher_name': self.publisher_name,
            'publish_year': self.publish_year,
            'pages': self.pages,
            'dimensions_raw': self.dimensions_raw,
            'width_cm': float(self.width_cm) if self.width_cm is not None else None,
            'height_cm': float(self.height_cm) if self.height_cm is not None else None,
            'thickness_mm': float(self.thickness_mm) if self.thickness_mm is not None else None,
            'age_min': self.age_min,
            'age_max': self.age_max,
            'sale_price': float(self.sale_price) if self.sale_price is not None else None,
            'sale_start': self.sale_start.isoformat() if self.sale_start else None,
            'sale_end': self.sale_end.isoformat() if self.sale_end else None,
            'is_active': self.is_active,
            'view_count': self.view_count
        }
        
        if include_relations:
            result['categories'] = [cat.to_dict() for cat in self.categories]
            result['images'] = [img.to_dict() for img in self.images]
            if self.stock:
                result['stock'] = self.stock.to_dict()
                
        return result


class ProductCategory(db.Model):
    """Product-Category association table"""
    __tablename__ = 'product_categories'
    
    product_id = db.Column(db.BigInteger, db.ForeignKey('products.id'), primary_key=True)
    category_id = db.Column(db.BigInteger, db.ForeignKey('categories.id'), primary_key=True)


class ProductImage(db.Model):
    """Product images model"""
    __tablename__ = 'product_images'
    
    # Define columns explicitly to match database schema
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey('products.id'), nullable=False)
    image_url = db.Column(db.String(1024), nullable=False)
    alt = db.Column(db.String(255), nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)
    # Note: No updated_at column to match database schema
    
    def to_dict(self):
        return {
            'id': self.id,
            'image_url': self.image_url,
            'alt': self.alt,
            'sort_order': self.sort_order
        }


class ProductStock(db.Model):
    """Product stock model"""
    __tablename__ = 'product_stock'
    
    product_id = db.Column(db.BigInteger, db.ForeignKey('products.id'), primary_key=True)
    qty_on_hand = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), 
                          onupdate=db.func.current_timestamp())
    
    def to_dict(self):
        return {
            'product_id': self.product_id,
            'qty_on_hand': self.qty_on_hand,
            'in_stock': self.qty_on_hand > 0,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# Database Views as mapped classes
class ProductEffectivePrice(db.Model):
    """Mapped class for v_products_effective_price view"""
    __tablename__ = 'v_products_effective_price'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(255))
    slug = db.Column(db.String(255))
    short_desc = db.Column(db.Text)
    image_url = db.Column(db.String(1024))
    price = db.Column(db.Numeric(12, 2))
    sale_price = db.Column(db.Numeric(12, 2))
    sale_start = db.Column(db.DateTime)
    sale_end = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean)
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)
    view_count = db.Column(db.Integer)
    effective_price = db.Column(db.Numeric(12, 2))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'short_desc': self.short_desc,
            'image_url': self.image_url,
            'price': float(self.price) if self.price is not None else None,
            'sale_price': float(self.sale_price) if self.sale_price is not None else None,
            'effective_price': float(self.effective_price) if self.effective_price is not None else None,
            'is_active': self.is_active,
            'view_count': self.view_count
        }


class ProductRating(db.Model):
    """Mapped class for v_product_rating view"""
    __tablename__ = 'v_product_rating'
    __table_args__ = {'extend_existing': True}
    
    product_id = db.Column(db.BigInteger, primary_key=True)
    avg_rating = db.Column(db.Numeric(3, 2))
    review_count = db.Column(db.Integer)
    
    def to_dict(self):
        return {
            'product_id': self.product_id,
            'avg_rating': float(self.avg_rating) if self.avg_rating is not None else None,
            'review_count': self.review_count or 0
        }