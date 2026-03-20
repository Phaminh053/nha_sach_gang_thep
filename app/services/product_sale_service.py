"""
Product sale service for handling product discounts
"""
from datetime import datetime, timedelta
from sqlalchemy import and_
from app.models import Product
from decimal import Decimal


class ProductSaleService:
    """Service for managing product sales and discounts"""
    
    def __init__(self, session):
        self.session = session
    
    def set_product_sale(self, product_id, sale_price, sale_start=None, sale_end=None):
        """Set sale price for a product"""
        product = self.session.query(Product).get(product_id)
        if not product:
            raise ValueError("Không tìm thấy sản phẩm")
        
        # Validate sale price
        if sale_price <= 0:
            raise ValueError("Giá khuyến mãi phải lớn hơn 0")
        
        if sale_price >= product.price:
            raise ValueError("Giá khuyến mãi phải nhỏ hơn giá gốc")
        
        # Set default start time if not provided
        if not sale_start:
            sale_start = datetime.utcnow()
        
        # Validate date range
        if sale_end and sale_start >= sale_end:
            raise ValueError("Ngày kết thúc phải sau ngày bắt đầu")
        
        # Update product
        product.sale_price = Decimal(str(sale_price))
        product.sale_start = sale_start
        product.sale_end = sale_end
        product.sale_active = True
        
        self.session.commit()
        return product
    
    def remove_product_sale(self, product_id):
        """Remove sale from a product"""
        product = self.session.query(Product).get(product_id)
        if not product:
            raise ValueError("Không tìm thấy sản phẩm")
        
        product.sale_price = None
        product.sale_start = None
        product.sale_end = None
        product.sale_active = False
        
        self.session.commit()
        return product
    
    def activate_product_sale(self, product_id):
        """Activate sale for a product (if sale price exists)"""
        product = self.session.query(Product).get(product_id)
        if not product:
            raise ValueError("Không tìm thấy sản phẩm")
        
        if not product.sale_price:
            raise ValueError("Sản phẩm chưa có giá khuyến mãi")
        
        product.sale_active = True
        self.session.commit()
        return product
    
    def deactivate_product_sale(self, product_id):
        """Deactivate sale for a product"""
        product = self.session.query(Product).get(product_id)
        if not product:
            raise ValueError("Không tìm thấy sản phẩm")
        
        product.sale_active = False
        self.session.commit()
        return product
    
    def bulk_remove_sales(self, product_ids):
        """Remove sales for multiple products"""
        products = self.session.query(Product).filter(Product.id.in_(product_ids)).all()
        
        for product in products:
            product.sale_price = None
            product.sale_start = None
            product.sale_end = None
            product.sale_active = False
        
        self.session.commit()
        return len(products)
    
    def bulk_activate_sales(self, product_ids):
        """Activate sales for multiple products (only those with sale_price)"""
        products = self.session.query(Product).filter(
            and_(
                Product.id.in_(product_ids),
                Product.sale_price.isnot(None),
                Product.sale_price > 0
            )
        ).all()
        
        for product in products:
            product.sale_active = True
        
        self.session.commit()
        return len(products)
    
    def bulk_deactivate_sales(self, product_ids):
        """Deactivate sales for multiple products"""
        products = self.session.query(Product).filter(Product.id.in_(product_ids)).all()
        
        for product in products:
            product.sale_active = False
        
        self.session.commit()
        return len(products)
    
    def get_products_on_sale(self, limit=None):
        """Get all products currently on sale"""
        query = self.session.query(Product).filter(
            and_(
                Product.is_active == True,
                Product.sale_active == True,
                Product.sale_price.isnot(None),
                Product.sale_price > 0
            )
        )
        
        # Check if sale period is valid (if dates are set)
        now = datetime.utcnow()
        query = query.filter(
            and_(
                Product.sale_start <= now,
                (Product.sale_end.is_(None)) | (Product.sale_end >= now)
            )
        )
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_sale_statistics(self):
        """Get statistics about product sales"""
        now = datetime.utcnow()
        
        # Total products with sale price set
        total_with_sale_price = self.session.query(Product).filter(
            and_(
                Product.is_active == True,
                Product.sale_price.isnot(None),
                Product.sale_price > 0
            )
        ).count()
        
        # Currently active sales
        active_sales = self.session.query(Product).filter(
            and_(
                Product.is_active == True,
                Product.sale_active == True,
                Product.sale_price.isnot(None),
                Product.sale_price > 0,
                Product.sale_start <= now,
                (Product.sale_end.is_(None)) | (Product.sale_end >= now)
            )
        ).count()
        
        # Scheduled sales (future start date)
        scheduled_sales = self.session.query(Product).filter(
            and_(
                Product.is_active == True,
                Product.sale_active == True,
                Product.sale_price.isnot(None),
                Product.sale_price > 0,
                Product.sale_start > now
            )
        ).count()
        
        # Expired sales
        expired_sales = self.session.query(Product).filter(
            and_(
                Product.is_active == True,
                Product.sale_price.isnot(None),
                Product.sale_price > 0,
                Product.sale_end < now
            )
        ).count()
        
        return {
            'total_with_sale_price': total_with_sale_price,
            'active_sales': active_sales,
            'scheduled_sales': scheduled_sales,
            'expired_sales': expired_sales
        }
    
    def auto_update_sale_status(self):
        """Auto update sale status based on start/end dates"""
        now = datetime.utcnow()
        updated_count = 0
        
        # Activate sales that should start now
        products_to_activate = self.session.query(Product).filter(
            and_(
                Product.is_active == True,
                Product.sale_price.isnot(None),
                Product.sale_price > 0,
                Product.sale_active == False,
                Product.sale_start <= now,
                (Product.sale_end.is_(None)) | (Product.sale_end >= now)
            )
        ).all()
        
        for product in products_to_activate:
            product.sale_active = True
            updated_count += 1
        
        # Deactivate expired sales
        products_to_deactivate = self.session.query(Product).filter(
            and_(
                Product.is_active == True,
                Product.sale_active == True,
                Product.sale_end < now
            )
        ).all()
        
        for product in products_to_deactivate:
            product.sale_active = False
            updated_count += 1
        
        if updated_count > 0:
            self.session.commit()
        
        return updated_count
    
    def calculate_discount_percentage(self, product):
        """Calculate discount percentage for a product"""
        if not product.sale_price or not product.price or product.sale_price >= product.price:
            return 0
        
        discount = (product.price - product.sale_price) / product.price * 100
        return round(discount, 1)
    
    def get_current_price(self, product):
        """Get current effective price for a product"""
        if (product.sale_active and 
            product.sale_price and 
            product.sale_price > 0 and
            self.is_sale_valid(product)):
            return product.sale_price
        return product.price
    
    def is_sale_valid(self, product):
        """Check if product's sale is currently valid"""
        if not product.sale_active or not product.sale_price:
            return False
        
        now = datetime.utcnow()
        
        # Check start date
        if product.sale_start and product.sale_start > now:
            return False
        
        # Check end date
        if product.sale_end and product.sale_end < now:
            return False
        
        return True