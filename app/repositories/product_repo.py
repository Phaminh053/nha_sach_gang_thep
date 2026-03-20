"""Product repository"""

from app.repositories import BaseRepository
from app.models import Product, ProductEffectivePrice, ProductRating, ProductStock, Category
from app.extensions import db
from sqlalchemy import and_, or_, func, desc, asc, text
from typing import List, Optional, Dict, Any, Tuple


class ProductRepository(BaseRepository):
    """Repository for Product operations"""
    
    def __init__(self, db_session=None):
        super().__init__(Product)
        self.db_session = db_session
    
    @property
    def session(self):
        """Get the database session to use"""
        return self.db_session if self.db_session else db.session
    
    def get_by_slug(self, slug: str) -> Optional[Product]:
        """Get product by slug"""
        return self.model.query.filter_by(slug=slug, is_active=True).first()
    
    def get_effective_price(self, product_id: int) -> Optional[ProductEffectivePrice]:
        """Get product with effective price from view"""
        import logging
        logger = logging.getLogger(__name__)
        
        result = ProductEffectivePrice.query.filter_by(id=product_id).first()
        if result:
            logger.info(f"🏪 Repository.get_effective_price(product_id={product_id})")
            logger.info(f"   Found: price={result.price}, sale_price={result.sale_price}, effective={result.effective_price}")
        else:
            logger.warning(f"🚫 Repository.get_effective_price(product_id={product_id}) -> None")
        
        return result
    
    def get_effective_price_for_update(self, product_id: int) -> Optional[float]:
        """Get effective price with row lock for order creation"""
        result = db.session.query(ProductEffectivePrice.effective_price)\
            .filter_by(id=product_id)\
            .with_for_update()\
            .first()
        return float(result[0]) if result else None
    
    def search_products(self, 
                       query: str = '', 
                       category_slug: str = None,
                       category_id: int = None,
                       price_min: float = None,
                       price_max: float = None,
                       sort: str = 'newest',
                       page: int = 1,
                       per_page: int = 24) -> Tuple[List[Dict], int]:
        """Search products with filters and pagination"""
        
        # Base query with effective price
        base_query = db.session.query(
            ProductEffectivePrice,
            ProductRating.avg_rating,
            ProductRating.review_count,
            ProductStock.qty_on_hand
        ).outerjoin(
            ProductRating, ProductEffectivePrice.id == ProductRating.product_id
        ).outerjoin(
            ProductStock, ProductEffectivePrice.id == ProductStock.product_id
        )
        
        # Text search
        if query:
            base_query = base_query.filter(
                or_(
                    ProductEffectivePrice.name.ilike(f'%{query}%'),
                    ProductEffectivePrice.short_desc.ilike(f'%{query}%')
                )
            )
        
        # Category filter
        if category_slug or category_id:
            if category_slug:
                category = Category.query.filter_by(slug=category_slug).first()
                if category:
                    category_id = category.id
            
            if category_id:
                # Join with product_categories table
                base_query = base_query.join(
                    Product, ProductEffectivePrice.id == Product.id
                ).join(
                    Product.categories
                ).filter(Category.id == category_id)
        
        # Price range filter
        if price_min is not None:
            base_query = base_query.filter(ProductEffectivePrice.effective_price >= price_min)
        if price_max is not None:
            base_query = base_query.filter(ProductEffectivePrice.effective_price <= price_max)
        
        # Sorting
        if sort == 'price_asc':
            base_query = base_query.order_by(asc(ProductEffectivePrice.effective_price))
        elif sort == 'price_desc':
            base_query = base_query.order_by(desc(ProductEffectivePrice.effective_price))
        elif sort == 'name_asc':
            base_query = base_query.order_by(asc(ProductEffectivePrice.name))
        elif sort == 'name_desc':
            base_query = base_query.order_by(desc(ProductEffectivePrice.name))
        elif sort == 'oldest':
            base_query = base_query.order_by(asc(ProductEffectivePrice.created_at))
        else:  # newest (default)
            base_query = base_query.order_by(desc(ProductEffectivePrice.created_at))
        
        # Get total count
        total = base_query.count()
        
        # Pagination
        offset = (page - 1) * per_page
        results = base_query.offset(offset).limit(per_page).all()
        
        # Format results
        products = []
        for product, avg_rating, review_count, qty_on_hand in results:
            product_dict = product.to_dict()
            product_dict['in_stock'] = (qty_on_hand or 0) > 0
            product_dict['rating'] = {
                'avg': float(avg_rating) if avg_rating else None,
                'count': review_count or 0
            }
            products.append(product_dict)
        
        return products, total
    
    def get_product_detail(self, slug: str) -> Optional[Dict]:
        """Get detailed product info by slug"""
        query = db.session.query(
            ProductEffectivePrice,
            ProductRating.avg_rating,
            ProductRating.review_count,
            ProductStock.qty_on_hand
        ).outerjoin(
            ProductRating, ProductEffectivePrice.id == ProductRating.product_id
        ).outerjoin(
            ProductStock, ProductEffectivePrice.id == ProductStock.product_id
        ).filter(
            ProductEffectivePrice.slug == slug,
            ProductEffectivePrice.is_active == True
        )
        
        # Expire cache for this specific product or all to force latest data from DB
        db.session.expire_all()
        
        result = query.first()
        
        if not result:
            return None
        
        product, avg_rating, review_count, qty_on_hand = result
        
        # Get actual Product object for images
        actual_product = Product.query.filter_by(slug=slug).first()
        
        # Format response
        product_dict = product.to_dict()
        product_dict['original_price'] = float(product.price)
        product_dict['stock'] = {
            'in_stock': (qty_on_hand or 0) > 0,
            'qty': qty_on_hand or 0
        }
        product_dict['rating'] = {
            'avg': float(avg_rating) if avg_rating else None,
            'count': review_count or 0
        }
        
        # Get additional images
        if actual_product and actual_product.images:
            product_dict['images'] = [img.image_url for img in actual_product.images]
        else:
            product_dict['images'] = [product.image_url] if product.image_url else []
        
        return product_dict
        
    def increment_view_count(self, product_id: int) -> bool:
        """Increment view count for a product"""
        try:
            # Use the repository's session instead of global db.session
            self.session.execute(
                text("UPDATE products SET view_count = view_count + 1 WHERE id = :id"),
                {'id': product_id}
            )
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            import logging
            logging.getLogger(__name__).error(f"Failed to increment view count for product {product_id}: {str(e)}")
            return False
    
    def get_admin_products(self, search: str = '', page: int = 1, per_page: int = 20):
        """Get products for admin with stock info"""
        query = self.session.query(
            Product,
            ProductStock.qty_on_hand
        ).outerjoin(
            ProductStock, Product.id == ProductStock.product_id
        )
        
        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f'%{search}%'),
                    Product.short_desc.ilike(f'%{search}%')
                )
            )
        
        query = query.order_by(desc(Product.created_at))
        
        # Expire cache to get fresh data including view_count
        self.session.expire_all()
        
        # Get total count
        total = query.count()
        
        # Pagination
        offset = (page - 1) * per_page
        results = query.offset(offset).limit(per_page).all()
        
        products = []
        for product, qty_on_hand in results:
            product_dict = product.to_dict(include_relations=True)
            
            # Fix stock data
            product_dict['stock'] = {
                'qty_on_hand': qty_on_hand or 0,
                'in_stock': (qty_on_hand or 0) > 0
            }
            
            # Fix pricing - calculate effective price
            base_price = float(product.price)
            sale_price = float(product.sale_price) if product.sale_price else None
            
            # Check if sale is active
            from datetime import datetime
            now = datetime.utcnow()
            is_sale_active = (product.sale_active and 
                            sale_price is not None and 
                            (product.sale_start is None or product.sale_start <= now) and
                            (product.sale_end is None or product.sale_end >= now))
            
            product_dict['base_price'] = base_price
            product_dict['effective_price'] = sale_price if is_sale_active else base_price
            product_dict['is_on_sale'] = is_sale_active
            
            products.append(product_dict)
        
        return products, total
    
    def get_latest_products(self, limit: int = 12) -> List[Product]:
        """Get latest products ordered by creation date"""
        return self.model.query.filter_by(is_active=True)\
            .order_by(desc(self.model.created_at))\
            .limit(limit)\
            .all()
    
    def get_products_on_sale(self, limit: int = 12) -> List[Product]:
        """Get products currently on sale"""
        return self.model.query.filter(
            and_(
                self.model.is_active == True,
                self.model.sale_active == True,
                self.model.sale_price.isnot(None)
            )
        ).order_by(desc(self.model.created_at))\
         .limit(limit)\
         .all()
    
    def get_by_category_with_filters(self, 
                                   category_id: int,
                                   search_term: str = None,
                                   price_min: float = None,
                                   price_max: float = None,
                                   sort_by: str = 'newest',
                                   page: int = 1,
                                   per_page: int = 24) -> Tuple[List[Product], int]:
        """Get products by category with filters and pagination"""
        
        # Import the association table model
        from app.models.product import ProductCategory
        
        # Base query for products in the category using proper join
        base_query = self.model.query.join(ProductCategory).filter(
            and_(
                self.model.is_active == True,
                ProductCategory.category_id == category_id
            )
        )
        
        # Text search filter
        if search_term:
            base_query = base_query.filter(
                or_(
                    self.model.name.ilike(f'%{search_term}%'),
                    self.model.short_desc.ilike(f'%{search_term}%')
                )
            )
        
        # Price range filter
        if price_min is not None:
            base_query = base_query.filter(self.model.price >= price_min)
        if price_max is not None:
            base_query = base_query.filter(self.model.price <= price_max)
        
        # Sorting
        if sort_by == 'price_asc':
            base_query = base_query.order_by(asc(self.model.price))
        elif sort_by == 'price_desc':
            base_query = base_query.order_by(desc(self.model.price))
        elif sort_by == 'name_asc':
            base_query = base_query.order_by(asc(self.model.name))
        elif sort_by == 'name_desc':
            base_query = base_query.order_by(desc(self.model.name))
        elif sort_by == 'oldest':
            base_query = base_query.order_by(asc(self.model.created_at))
        else:  # newest (default)
            base_query = base_query.order_by(desc(self.model.created_at))
        
        # Get total count
        total = base_query.count()
        
        # Pagination
        offset = (page - 1) * per_page
        products = base_query.offset(offset).limit(per_page).all()
        
        return products, total

    def get_all_with_filters(self, 
                           search_term: str = None,
                           category_id: int = None,
                           price_min: float = None,
                           price_max: float = None,
                           sort_by: str = 'newest',
                           page: int = 1,
                           per_page: int = 24) -> Tuple[List[Product], int]:
        """Get all products with filters and pagination"""
        
        # Base query for all active products
        base_query = self.model.query.filter(self.model.is_active == True)
        
        # Category filter
        if category_id:
            from app.models.product import ProductCategory
            base_query = base_query.join(ProductCategory).filter(
                ProductCategory.category_id == category_id
            )
        
        # Text search filter
        if search_term:
            base_query = base_query.filter(
                or_(
                    self.model.name.ilike(f'%{search_term}%'),
                    self.model.short_desc.ilike(f'%{search_term}%')
                )
            )
        
        # Price range filter
        if price_min is not None:
            base_query = base_query.filter(self.model.price >= price_min)
        if price_max is not None:
            base_query = base_query.filter(self.model.price <= price_max)
        
        # Sorting
        if sort_by == 'price_asc':
            base_query = base_query.order_by(asc(self.model.price))
        elif sort_by == 'price_desc':
            base_query = base_query.order_by(desc(self.model.price))
        elif sort_by == 'name_asc':
            base_query = base_query.order_by(asc(self.model.name))
        elif sort_by == 'name_desc':
            base_query = base_query.order_by(desc(self.model.name))
        elif sort_by == 'oldest':
            base_query = base_query.order_by(asc(self.model.created_at))
        else:  # newest (default)
            base_query = base_query.order_by(desc(self.model.created_at))
        
        # Get total count
        total = base_query.count()
        
        # Pagination
        offset = (page - 1) * per_page
        products = base_query.offset(offset).limit(per_page).all()
        
        return products, total

    def get_random_products(self, limit: int = 10, exclude_id: int = None) -> List[Product]:
        """Get random products, excluding specific product if provided"""
        query = self.model.query.filter(self.model.is_active == True)
        
        if exclude_id:
            query = query.filter(self.model.id != exclude_id)
        
        # Use func.random() for SQLite/PostgreSQL or func.rand() for MySQL
        return query.order_by(func.random()).limit(limit).all()

    def get_best_selling_products(self, limit: int = 12) -> List[Product]:
        """Get best selling products based on order quantities"""
        from app.models.order import OrderItem
        
        # Query to get products with highest total sales
        subquery = db.session.query(
            OrderItem.product_id,
            func.sum(OrderItem.qty).label('total_sold')
        ).group_by(OrderItem.product_id).subquery()
        
        return self.model.query.join(
            subquery, self.model.id == subquery.c.product_id
        ).filter(
            self.model.is_active == True
        ).order_by(
            desc(subquery.c.total_sold)
        ).limit(limit).all()

    def get_top_rated_products(self, limit: int = 12, min_reviews: int = 3) -> List[Product]:
        """Get products with highest average rating (minimum review count required)"""
        return self.model.query.join(ProductRating, self.model.id == ProductRating.product_id).filter(
            and_(
                self.model.is_active == True,
                ProductRating.review_count >= min_reviews
            )
        ).order_by(
            desc(ProductRating.avg_rating),
            desc(ProductRating.review_count)
        ).limit(limit).all()

    def get_featured_categories(self, limit: int = 6) -> List[Category]:
        """Get featured categories with product count"""
        from app.models.product import ProductCategory
        
        # Get categories with most products
        subquery = db.session.query(
            ProductCategory.category_id,
            func.count(ProductCategory.product_id).label('product_count')
        ).join(
            self.model, ProductCategory.product_id == self.model.id
        ).filter(
            self.model.is_active == True
        ).group_by(ProductCategory.category_id).subquery()
        
        return Category.query.join(
            subquery, Category.id == subquery.c.category_id
        ).order_by(
            desc(subquery.c.product_count)
        ).limit(limit).all()


# Global instance
product_repo = ProductRepository()