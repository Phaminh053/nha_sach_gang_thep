"""
Backend Dispatch API for Chatbot
Handles database queries based on AI requests
"""

import logging
import re
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import and_, or_, text, case
from app.extensions import db
from app.models.product import Product
from app.models.category import Category  
from app.models.order import Order
from app.repositories.product_repo import ProductRepository
from app.utils.slugs import slugify

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

backend_bp = Blueprint('backend', __name__, url_prefix='/api/backend')

class BackendDispatcher:
    """Handles database queries for chatbot requests"""
    
    def __init__(self):
        self.product_repo = ProductRepository()

    @staticmethod
    def _clean_product_reference(value):
        """Normalize noisy title references before database lookup."""
        if not value:
            return ''

        cleaned = str(value).strip()
        cleaned = re.sub(r'^[\s"\'“”‘’]+|[\s"\'“”‘’?!.,:;]+$', '', cleaned)

        noisy_prefixes = [
            r'^(?:quyển|cuốn|bộ|tựa|tên)\s+sách\s+',
            r'^(?:quyển|cuốn|bộ|tựa|tên)\s+',
            r'^sách\s+',
            r'^(?:thông\s+tin|chi\s+tiết|giá|review|đánh\s+giá|mô\s+tả)\s+(?:về\s+)?',
            r'^(?:tìm|kiếm|cho\s+tôi|xem|hỏi|check)\s+(?:giúp\s+tôi\s+)?',
            r'^(?:về|của)\s+',
        ]

        changed = True
        while changed and cleaned:
            changed = False
            for pattern in noisy_prefixes:
                updated = re.sub(pattern, '', cleaned, flags=re.IGNORECASE).strip()
                if updated != cleaned:
                    cleaned = updated
                    changed = True

        return cleaned or str(value).strip()

    def _build_product_reference_candidates(self, params):
        """Collect and normalize possible product titles from chatbot params."""
        raw_candidates = []
        for key in ('name', 'product_name', 'title', 'book_title', 'query_text', 'query'):
            value = params.get(key)
            if isinstance(value, str) and value.strip():
                raw_candidates.append(value.strip())

        candidates = []
        for value in raw_candidates:
            for candidate in (value, self._clean_product_reference(value)):
                candidate = candidate.strip()
                if candidate and candidate not in candidates:
                    candidates.append(candidate)
        return candidates

    def _find_product_by_reference(self, params):
        """Match a single book title robustly, including slug-based fallback."""
        if 'product_id' in params and params['product_id']:
            return Product.query.filter_by(id=params['product_id'], is_active=True).first()

        candidates = self._build_product_reference_candidates(params)
        if not candidates:
            return None

        slug_candidates = []
        for candidate in candidates:
            candidate_slug = slugify(candidate, max_length=255)
            if candidate_slug and candidate_slug not in slug_candidates:
                slug_candidates.append(candidate_slug)

        conditions = []
        for candidate in candidates:
            conditions.extend([
                Product.name.ilike(f"%{candidate}%"),
                Product.short_desc.ilike(f"%{candidate}%"),
                Product.authors.ilike(f"%{candidate}%"),
                Product.publisher_name.ilike(f"%{candidate}%"),
            ])
        if slug_candidates:
            conditions.append(Product.slug.in_(slug_candidates))

        query = Product.query.filter(Product.is_active == True)
        if conditions:
            query = query.filter(or_(*conditions))

        ranking = []
        for candidate in candidates:
            ranking.extend([
                (Product.name == candidate, 0),
                (Product.name.ilike(candidate), 1),
                (Product.name.ilike(f"{candidate}%"), 2),
            ])
        for candidate_slug in slug_candidates:
            ranking.extend([
                (Product.slug == candidate_slug, 0),
                (Product.slug.ilike(f"{candidate_slug}%"), 2),
                (Product.slug.ilike(f"%{candidate_slug}%"), 3),
            ])

        if ranking:
            query = query.order_by(case(*ranking, else_=4), Product.name.asc())
        else:
            query = query.order_by(Product.name.asc())

        product = query.first()
        if product:
            logger.info("Resolved product reference %s -> %s", candidates, product.name)
        else:
            logger.info("No product matched candidates: %s", candidates)
        return product
    
    def search_products(self, params):
        """Search products based on parameters"""
        try:
            query = Product.query.filter(Product.is_active == True)
            
            # Text search filter
            if 'query_text' in params and params['query_text']:
                search_text = params['query_text']
                # Handle special cases for price sorting
                if 'giá cao nhất' in search_text.lower() or 'đắt nhất' in search_text.lower():
                    query = query.order_by(Product.price.desc())
                elif 'giá thấp nhất' in search_text.lower() or 'rẻ nhất' in search_text.lower():
                    query = query.order_by(Product.price.asc())
                else:
                    # General text search
                    query = query.filter(
                        or_(
                            Product.name.ilike(f"%{search_text}%"),
                            Product.short_desc.ilike(f"%{search_text}%"),
                            Product.authors.ilike(f"%{search_text}%"),
                            Product.publisher_name.ilike(f"%{search_text}%")
                        )
                    )
            
            # Age filter
            if 'age_min' in params and params['age_min'] is not None:
                query = query.filter(Product.age_min <= params['age_min'])
            if 'age_max' in params and params['age_max'] is not None:
                query = query.filter(Product.age_max >= params['age_max'])
            
            # Category filter
            if 'category' in params and params['category']:
                query = query.join(Product.categories).filter(
                    Category.name.ilike(f"%{params['category']}%")
                )
            
            # Topic/keyword filter
            if 'topic' in params and params['topic']:
                topic = params['topic']
                query = query.filter(
                    or_(
                        Product.name.ilike(f"%{topic}%"),
                        Product.short_desc.ilike(f"%{topic}%"),
                        Product.authors.ilike(f"%{topic}%")
                    )
                )
            
            # Price filter
            if 'price_min' in params and params['price_min'] is not None:
                query = query.filter(Product.price >= params['price_min'])
            if 'price_max' in params and params['price_max'] is not None:
                query = query.filter(Product.price <= params['price_max'])
            
            # Sorting
            if 'sort_by' in params and params['sort_by'] == 'price':
                if params.get('sort_order', 'asc') == 'desc':
                    # Sort by price descending (highest first)
                    query = query.order_by(Product.price.desc())
                else:
                    # Sort by price ascending (lowest first)
                    query = query.order_by(Product.price.asc())
            elif 'query_text' not in params or not params.get('query_text'):
                # Default sorting by name if no text search
                query = query.order_by(Product.name.asc())
            
            # Limit results
            limit = params.get('limit', 10)
            offset = params.get('offset', 0)
            products = query.offset(offset).limit(limit).all()
            
            # Format response
            result = []
            for product in products:
                # Get current price (sale or regular)
                current_price = product.sale_price if product.sale_active and product.sale_price else product.price
                stock_status = "Còn hàng" if product.in_stock else "Hết hàng"
                
                result.append({
                    'id': product.id,
                    'name': product.name,
                    'price': float(current_price) if current_price else 0,
                    'sale_price': float(product.sale_price) if product.sale_price else None,
                    'sale_active': product.sale_active,
                    'authors': product.authors,
                    'short_desc': product.short_desc,
                    'age_range': f"{product.age_min}-{product.age_max}" if product.age_min and product.age_max else None,
                    'stock_status': stock_status,
                    'categories': [cat.name for cat in product.categories] if product.categories else []
                })
            
            return {
                'status': 'success',
                'data': result,
                'total': len(result)
            }
            
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi tìm kiếm sản phẩm'
            }
    
    def get_product_detail(self, params):
        """Get detailed product information"""
        try:
            product = self._find_product_by_reference(params)
            
            if not product:
                return {
                    'status': 'not_found',
                    'message': 'Không tìm thấy sản phẩm'
                }
            
            # Get current price
            current_price = product.sale_price if product.sale_active and product.sale_price else product.price
            stock_status = "Còn hàng" if product.in_stock else "Hết hàng"
            
            result = {
                'id': product.id,
                'name': product.name,
                'price': float(current_price) if current_price else 0,
                'original_price': float(product.price) if product.price else 0,
                'sale_price': float(product.sale_price) if product.sale_price else None,
                'sale_active': product.sale_active,
                'authors': product.authors,
                'publisher': product.publisher_name,
                'publish_year': product.publish_year,
                'pages': product.pages,
                'isbn13': product.isbn13,
                'short_desc': product.short_desc,
                'age_range': f"{product.age_min}-{product.age_max}" if product.age_min and product.age_max else None,
                'stock_status': stock_status,
                'categories': [cat.name for cat in product.categories] if product.categories else [],
                'dimensions': {
                    'width': float(product.width_cm) if product.width_cm else None,
                    'height': float(product.height_cm) if product.height_cm else None,
                    'thickness': float(product.thickness_mm) if product.thickness_mm else None
                }
            }
            
            return {
                'status': 'success',
                'data': result
            }
            
        except Exception as e:
            logger.error(f"Error getting product detail: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi lấy thông tin sản phẩm'
            }
    
    def search_by_price_range(self, params):
        """Search products by price range"""
        try:
            query = Product.query.filter(Product.is_active == True)
            
            # Price range filter
            if 'price_min' in params and params['price_min'] is not None:
                query = query.filter(Product.price >= params['price_min'])
            if 'price_max' in params and params['price_max'] is not None:
                query = query.filter(Product.price <= params['price_max'])
            
            # Sort by price ascending
            query = query.order_by(Product.price.asc())
            
            # Limit results
            limit = params.get('limit', 10)
            offset = params.get('offset', 0)
            products = query.offset(offset).limit(limit).all()
            
            # Format response
            result = []
            for product in products:
                # Get current price (sale or regular)
                current_price = product.sale_price if product.sale_active and product.sale_price else product.price
                stock_status = "Còn hàng" if product.in_stock else "Hết hàng"
                
                result.append({
                    'id': product.id,
                    'name': product.name,
                    'price': float(current_price) if current_price else 0,
                    'sale_price': float(product.sale_price) if product.sale_price else None,
                    'sale_active': product.sale_active,
                    'authors': product.authors,
                    'short_desc': product.short_desc,
                    'age_range': f"{product.age_min}-{product.age_max}" if product.age_min and product.age_max else None,
                    'stock_status': stock_status,
                    'categories': [cat.name for cat in product.categories] if product.categories else []
                })
            
            return {
                'status': 'success',
                'data': result,
                'total': len(result)
            }
            
        except Exception as e:
            logger.error(f"Error searching by price range: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi tìm kiếm sản phẩm theo giá'
            }
    
    def search_discounted_products(self, params):
        """Search for products that are currently on sale"""
        try:
            # Only get products that are currently on sale
            query = Product.query.filter(
                Product.is_active == True,
                Product.sale_active == True,
                Product.sale_price.isnot(None),
                Product.sale_price < Product.price  # Ensure sale price is actually lower
            )
            
            # Sort by discount percentage (highest discount first)
            if params.get('sort_by_discount', False):
                # Calculate discount percentage and sort by it
                query = query.order_by(
                    ((Product.price - Product.sale_price) / Product.price * 100).desc()
                )
            else:
                # Default sort by sale price ascending
                query = query.order_by(Product.sale_price.asc())
            
            # Limit results
            limit = params.get('limit', 10)
            offset = params.get('offset', 0)
            products = query.offset(offset).limit(limit).all()
            
            # Format response
            result = []
            for product in products:
                # Calculate discount percentage
                discount_percentage = 0
                if product.price and product.sale_price:
                    discount_percentage = round(((product.price - product.sale_price) / product.price) * 100, 1)
                
                stock_status = "Còn hàng" if product.in_stock else "Hết hàng"
                
                result.append({
                    'id': product.id,
                    'name': product.name,
                    'price': float(product.price) if product.price else 0,
                    'sale_price': float(product.sale_price) if product.sale_price else None,
                    'sale_active': product.sale_active,
                    'discount_percentage': discount_percentage,
                    'authors': product.authors,
                    'short_desc': product.short_desc,
                    'age_range': f"{product.age_min}-{product.age_max}" if product.age_min and product.age_max else None,
                    'stock_status': stock_status,
                    'categories': [cat.name for cat in product.categories] if product.categories else []
                })
            
            return {
                'status': 'success',
                'data': result,
                'total': len(result)
            }
            
        except Exception as e:
            logger.error(f"Error searching discounted products: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi tìm kiếm sản phẩm giảm giá'
            }
    
    def get_record_product(self, params):
        """Get product with extreme values (max/min pages, price, year, etc.)"""
        try:
            record_type = params.get('record_type')
            order = params.get('order', 'max')
            
            query = Product.query.filter(Product.is_active == True)
            
            if record_type == 'pages':
                if order == 'max':
                    query = query.filter(Product.pages.isnot(None)).order_by(Product.pages.desc())
                else:
                    query = query.filter(Product.pages.isnot(None)).order_by(Product.pages.asc())
                    
            elif record_type == 'price':
                if order == 'max':
                    query = query.order_by(Product.price.desc())
                else:
                    query = query.order_by(Product.price.asc())
                    
            elif record_type == 'year':
                if order == 'max':
                    query = query.filter(Product.publish_year.isnot(None)).order_by(Product.publish_year.desc())
                else:
                    query = query.filter(Product.publish_year.isnot(None)).order_by(Product.publish_year.asc())
                    
            elif record_type == 'age':
                if order == 'max':
                    query = query.filter(Product.age_max.isnot(None)).order_by(Product.age_max.desc())
                else:
                    query = query.filter(Product.age_min.isnot(None)).order_by(Product.age_min.asc())
                    
            elif record_type == 'size':
                # Calculate area: width_cm * height_cm
                if order == 'max':
                    query = query.filter(
                        Product.width_cm.isnot(None),
                        Product.height_cm.isnot(None)
                    ).order_by((Product.width_cm * Product.height_cm).desc())
                else:
                    query = query.filter(
                        Product.width_cm.isnot(None),
                        Product.height_cm.isnot(None)
                    ).order_by((Product.width_cm * Product.height_cm).asc())
                    
            elif record_type == 'thickness':
                if order == 'max':
                    query = query.filter(Product.thickness_mm.isnot(None)).order_by(Product.thickness_mm.desc())
                else:
                    query = query.filter(Product.thickness_mm.isnot(None)).order_by(Product.thickness_mm.asc())
                    
            elif record_type == 'combo':
                query = query.filter(Product.name.ilike('%combo%'))
                if order == 'max':
                    query = query.order_by(Product.price.desc())
                else:
                    query = query.order_by(Product.price.asc())
                    
            elif record_type == 'discount':
                query = query.filter(
                    Product.sale_active == True,
                    Product.sale_price.isnot(None),
                    Product.sale_price < Product.price
                ).order_by(((Product.price - Product.sale_price) / Product.price * 100).desc())
            
            product = query.first()
            
            if not product:
                return {
                    'status': 'not_found',
                    'message': 'Không tìm thấy sản phẩm phù hợp'
                }
            
            # Format response
            current_price = product.sale_price if product.sale_active and product.sale_price else product.price
            stock_status = "Còn hàng" if product.in_stock else "Hết hàng"
            
            result = {
                'id': product.id,
                'name': product.name,
                'slug': product.slug,
                'price': float(current_price) if current_price else 0,
                'original_price': float(product.price) if product.price else 0,
                'sale_price': float(product.sale_price) if product.sale_price else None,
                'sale_active': product.sale_active,
                'authors': product.authors,
                'publisher': product.publisher_name,
                'publish_year': product.publish_year,
                'pages': product.pages,
                'age_range': f"{product.age_min}-{product.age_max}" if product.age_min and product.age_max else None,
                'dimensions': {
                    'width': float(product.width_cm) if product.width_cm else None,
                    'height': float(product.height_cm) if product.height_cm else None,
                    'thickness': float(product.thickness_mm) if product.thickness_mm else None
                },
                'stock_status': stock_status,
                'categories': [cat.name for cat in product.categories] if product.categories else []
            }
            
            return {
                'status': 'success',
                'data': result
            }
            
        except Exception as e:
            logger.error(f"Error getting record product: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi lấy thông tin sản phẩm cực đại'
            }
    
    def search_by_criteria(self, params):
        """Search products by specific criteria"""
        try:
            query = Product.query.filter(Product.is_active == True)
            
            # Age filter
            if 'age' in params and params['age'] is not None:
                age = params['age']
                query = query.filter(
                    or_(
                        Product.age_min.is_(None),
                        Product.age_min <= age
                    ),
                    or_(
                        Product.age_max.is_(None),
                        Product.age_max >= age
                    )
                )
            
            if 'age_min' in params and params['age_min'] is not None:
                query = query.filter(Product.age_min <= params['age_min'])
            if 'age_max' in params and params['age_max'] is not None:
                query = query.filter(Product.age_max >= params['age_max'])
            
            # Year filter
            if 'year' in params and params['year'] is not None:
                query = query.filter(Product.publish_year == params['year'])
            
            # Author filter
            if 'author' in params and params['author']:
                query = query.filter(Product.authors.ilike(f"%{params['author']}%"))
            
            # Translator filter
            if 'translator' in params and params['translator']:
                query = query.filter(Product.translators.ilike(f"%{params['translator']}%"))
            
            # Publisher filter
            if 'publisher' in params and params['publisher']:
                query = query.filter(Product.publisher_name.ilike(f"%{params['publisher']}%"))
            
            # Size filter (with tolerance ±0.5cm)
            if 'size_width' in params and params['size_width'] is not None:
                width = params['size_width']
                query = query.filter(
                    Product.width_cm.isnot(None),
                    text("ABS(width_cm - :width) <= 0.5").params(width=width)
                )
            if 'size_height' in params and params['size_height'] is not None:
                height = params['size_height']
                query = query.filter(
                    Product.height_cm.isnot(None),
                    text("ABS(height_cm - :height) <= 0.5").params(height=height)
                )
            
            # Sale filter
            if 'on_sale' in params and params['on_sale']:
                query = query.filter(
                    Product.sale_active == True,
                    Product.sale_price.isnot(None)
                )
            
            # Price filter
            if 'price_max' in params and params['price_max'] is not None:
                query = query.filter(Product.price <= params['price_max'])
            
            # Default sorting
            query = query.order_by(Product.name.asc())
            
            # Limit results
            limit = params.get('limit', 10)
            offset = params.get('offset', 0)
            products = query.offset(offset).limit(limit).all()
            
            # Format response
            result = []
            for product in products:
                current_price = product.sale_price if product.sale_active and product.sale_price else product.price
                stock_status = "Còn hàng" if product.in_stock else "Hết hàng"
                
                result.append({
                    'id': product.id,
                    'name': product.name,
                    'slug': product.slug,
                    'price': float(current_price) if current_price else 0,
                    'sale_price': float(product.sale_price) if product.sale_price else None,
                    'sale_active': product.sale_active,
                    'authors': product.authors,
                    'short_desc': product.short_desc,
                    'age_range': f"{product.age_min}-{product.age_max}" if product.age_min and product.age_max else None,
                    'stock_status': stock_status,
                    'categories': [cat.name for cat in product.categories] if product.categories else []
                })
            
            return {
                'status': 'success',
                'data': result,
                'total': len(result)
            }
            
        except Exception as e:
            logger.error(f"Error searching by criteria: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi tìm kiếm sản phẩm theo tiêu chí'
            }
    
    def search_by_category_criteria(self, params):
        """Search products by category with specific criteria"""
        try:
            query = Product.query.filter(Product.is_active == True)
            
            # Category filter
            if 'category_slug' in params and params['category_slug']:
                query = query.join(Product.categories).filter(
                    Category.slug == params['category_slug']
                )
            elif 'category_id' in params and params['category_id']:
                query = query.join(Product.categories).filter(
                    Category.id == params['category_id']
                )
            
            # Record type filter
            record_type = params.get('record_type')
            order = params.get('order', 'max')
            
            if record_type == 'pages':
                if order == 'max':
                    query = query.filter(Product.pages.isnot(None)).order_by(Product.pages.desc())
                else:
                    query = query.filter(Product.pages.isnot(None)).order_by(Product.pages.asc())
            elif record_type == 'price':
                if order == 'max':
                    query = query.order_by(Product.price.desc())
                else:
                    query = query.order_by(Product.price.asc())
            elif record_type == 'year':
                if order == 'max':
                    query = query.filter(Product.publish_year.isnot(None)).order_by(Product.publish_year.desc())
                else:
                    query = query.filter(Product.publish_year.isnot(None)).order_by(Product.publish_year.asc())
            
            # Limit results
            limit = params.get('limit', 10)
            offset = params.get('offset', 0)
            products = query.offset(offset).limit(limit).all()
            
            # Format response
            result = []
            for product in products:
                current_price = product.sale_price if product.sale_active and product.sale_price else product.price
                stock_status = "Còn hàng" if product.in_stock else "Hết hàng"
                
                result.append({
                    'id': product.id,
                    'name': product.name,
                    'slug': product.slug,
                    'price': float(current_price) if current_price else 0,
                    'sale_price': float(product.sale_price) if product.sale_price else None,
                    'sale_active': product.sale_active,
                    'authors': product.authors,
                    'short_desc': product.short_desc,
                    'age_range': f"{product.age_min}-{product.age_max}" if product.age_min and product.age_max else None,
                    'stock_status': stock_status,
                    'categories': [cat.name for cat in product.categories] if product.categories else []
                })
            
            return {
                'status': 'success',
                'data': result,
                'total': len(result)
            }
            
        except Exception as e:
            logger.error(f"Error searching by category criteria: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi tìm kiếm sản phẩm theo danh mục'
            }
    
    def get_statistics(self, params):
        """Get statistics about products"""
        try:
            stat_type = params.get('stat_type')
            group_by = params.get('group_by')
            
            if stat_type == 'count':
                # Simple count
                total_products = Product.query.filter(Product.is_active == True).count()
                total_categories = Category.query.count()
                
                return {
                    'status': 'success',
                    'data': {
                        'total_products': total_products,
                        'total_categories': total_categories
                    }
                }
            
            elif stat_type == 'price_ranges':
                # Price range statistics
                ranges = [
                    ('< 50k', Product.price < 50000),
                    ('50k - 100k', and_(Product.price >= 50000, Product.price < 100000)),
                    ('100k - 200k', and_(Product.price >= 100000, Product.price < 200000)),
                    ('200k - 500k', and_(Product.price >= 200000, Product.price < 500000)),
                    ('> 500k', Product.price >= 500000)
                ]
                
                result = []
                for range_name, condition in ranges:
                    count = Product.query.filter(
                        Product.is_active == True,
                        condition
                    ).count()
                    result.append({'range': range_name, 'count': count})
                
                return {
                    'status': 'success',
                    'data': result
                }
            
            elif stat_type == 'publishers':
                # Publisher statistics
                from sqlalchemy import func
                publishers = db.session.query(
                    Product.publisher_name,
                    func.count(Product.id).label('count')
                ).filter(
                    Product.is_active == True,
                    Product.publisher_name.isnot(None)
                ).group_by(Product.publisher_name).order_by(func.count(Product.id).desc()).all()
                
                result = [{'publisher': p[0], 'count': p[1]} for p in publishers]
                
                return {
                    'status': 'success',
                    'data': result
                }
            
            elif stat_type == 'years':
                # Publication year statistics
                from sqlalchemy import func
                years = db.session.query(
                    Product.publish_year,
                    func.count(Product.id).label('count')
                ).filter(
                    Product.is_active == True,
                    Product.publish_year.isnot(None)
                ).group_by(Product.publish_year).order_by(Product.publish_year.desc()).all()
                
                result = [{'year': y[0], 'count': y[1]} for y in years]
                
                return {
                    'status': 'success',
                    'data': result
                }
            
            else:
                return {
                    'status': 'error',
                    'message': 'Loại thống kê không được hỗ trợ'
                }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi lấy thống kê'
            }
    
    def get_product_rating(self, params):
        """Get product rating information"""
        try:
            from app.models.review import ProductReview
            from sqlalchemy import func
            
            product = None
            
            if 'product_id' in params and params['product_id']:
                product = Product.query.filter_by(id=params['product_id'], is_active=True).first()
            elif 'product_name' in params and params['product_name']:
                product = Product.query.filter(
                    Product.name.ilike(f"%{params['product_name']}%"),
                    Product.is_active == True
                ).first()
            
            if not product:
                return {
                    'status': 'not_found',
                    'message': 'Không tìm thấy sản phẩm'
                }
            
            # Get rating statistics
            rating_stats = db.session.query(
                func.avg(ProductReview.rating).label('average_rating'),
                func.count(ProductReview.id).label('total_reviews'),
                func.max(ProductReview.rating).label('max_rating'),
                func.min(ProductReview.rating).label('min_rating')
            ).filter(ProductReview.product_id == product.id).first()
            
            average_rating = float(rating_stats.average_rating) if rating_stats.average_rating else 0
            total_reviews = rating_stats.total_reviews or 0
            
            return {
                'status': 'success',
                'data': {
                    'product_id': product.id,
                    'product_name': product.name,
                    'average_rating': round(average_rating, 1),
                    'total_reviews': total_reviews,
                    'max_rating': rating_stats.max_rating,
                    'min_rating': rating_stats.min_rating,
                    'rating_stars': '★' * int(average_rating) + '☆' * (5 - int(average_rating))
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting product rating: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi lấy điểm đánh giá sản phẩm'
            }
    
    def get_product_reviews(self, params):
        """Get product reviews"""
        try:
            from app.models.review import ProductReview
            
            product = None
            
            if 'product_id' in params and params['product_id']:
                product = Product.query.filter_by(id=params['product_id'], is_active=True).first()
            elif 'product_name' in params and params['product_name']:
                product = Product.query.filter(
                    Product.name.ilike(f"%{params['product_name']}%"),
                    Product.is_active == True
                ).first()
            
            if not product:
                return {
                    'status': 'not_found',
                    'message': 'Không tìm thấy sản phẩm'
                }
            
            # Get reviews
            query = ProductReview.query.filter(ProductReview.product_id == product.id)
            
            if params.get('latest', False):
                query = query.order_by(ProductReview.created_at.desc())
            else:
                query = query.order_by(ProductReview.created_at.desc())
            
            limit = params.get('limit', 10)
            reviews = query.limit(limit).all()
            
            result = []
            for review in reviews:
                result.append({
                    'id': review.id,
                    'user_name': review.user_name,
                    'rating': review.rating,
                    'content': review.content,
                    'created_at': review.created_at.isoformat() if review.created_at else None,
                    'rating_stars': '★' * review.rating + '☆' * (5 - review.rating)
                })
            
            return {
                'status': 'success',
                'data': {
                    'product_id': product.id,
                    'product_name': product.name,
                    'reviews': result,
                    'total_reviews': len(result)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting product reviews: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi lấy đánh giá sản phẩm'
            }
    
    def search_by_rating(self, params):
        """Search products by rating"""
        try:
            from app.models.review import ProductReview
            from sqlalchemy import func
            
            query = Product.query.filter(Product.is_active == True)
            
            # Join with reviews to filter by rating
            query = query.join(ProductReview, Product.id == ProductReview.product_id)
            
            # Rating filters
            if 'min_rating' in params and params['min_rating'] is not None:
                query = query.filter(ProductReview.rating >= params['min_rating'])
            if 'max_rating' in params and params['max_rating'] is not None:
                query = query.filter(ProductReview.rating <= params['max_rating'])
            
            # Category filter
            if 'category_slug' in params and params['category_slug']:
                query = query.join(Product.categories).filter(
                    Category.slug == params['category_slug']
                )
            
            # Group by product and calculate average rating
            query = query.group_by(Product.id).having(
                func.avg(ProductReview.rating) >= (params.get('min_rating', 0) or 0)
            )
            
            if params.get('sort_by_rating', False):
                query = query.order_by(func.avg(ProductReview.rating).desc())
            else:
                query = query.order_by(Product.name.asc())
            
            # Limit results
            limit = params.get('limit', 10)
            offset = params.get('offset', 0)
            products = query.offset(offset).limit(limit).all()
            
            # Format response with rating info
            result = []
            for product in products:
                # Get average rating for this product
                avg_rating = db.session.query(func.avg(ProductReview.rating)).filter(
                    ProductReview.product_id == product.id
                ).scalar() or 0
                
                current_price = product.sale_price if product.sale_active and product.sale_price else product.price
                stock_status = "Còn hàng" if product.in_stock else "Hết hàng"
                
                result.append({
                    'id': product.id,
                    'name': product.name,
                    'slug': product.slug,
                    'price': float(current_price) if current_price else 0,
                    'sale_price': float(product.sale_price) if product.sale_price else None,
                    'sale_active': product.sale_active,
                    'average_rating': round(float(avg_rating), 1),
                    'rating_stars': '★' * int(avg_rating) + '☆' * (5 - int(avg_rating)),
                    'authors': product.authors,
                    'short_desc': product.short_desc,
                    'age_range': f"{product.age_min}-{product.age_max}" if product.age_min and product.age_max else None,
                    'stock_status': stock_status,
                    'categories': [cat.name for cat in product.categories] if product.categories else []
                })
            
            return {
                'status': 'success',
                'data': result,
                'total': len(result)
            }
            
        except Exception as e:
            logger.error(f"Error searching by rating: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi tìm kiếm sản phẩm theo điểm đánh giá'
            }
    
    def get_top_rated_products(self, params):
        """Get top rated products"""
        try:
            from app.models.review import ProductReview
            from sqlalchemy import func
            
            query = Product.query.filter(Product.is_active == True)
            
            # Join with reviews
            query = query.join(ProductReview, Product.id == ProductReview.product_id)
            
            # Category filter
            if 'category_slug' in params and params['category_slug']:
                query = query.join(Product.categories).filter(
                    Category.slug == params['category_slug']
                )
            
            # Group by product and calculate statistics
            query = query.group_by(Product.id)
            
            # Minimum reviews filter
            min_reviews = params.get('min_reviews', 1)
            query = query.having(func.count(ProductReview.id) >= min_reviews)
            
            # Order by average rating descending
            query = query.order_by(func.avg(ProductReview.rating).desc())
            
            # Limit results
            limit = params.get('limit', 10)
            offset = params.get('offset', 0)
            products = query.offset(offset).limit(limit).all()
            
            # Format response with rating info
            result = []
            for product in products:
                # Get rating statistics for this product
                rating_stats = db.session.query(
                    func.avg(ProductReview.rating).label('avg_rating'),
                    func.count(ProductReview.id).label('total_reviews')
                ).filter(ProductReview.product_id == product.id).first()
                
                avg_rating = float(rating_stats.avg_rating) if rating_stats.avg_rating else 0
                total_reviews = rating_stats.total_reviews or 0
                
                current_price = product.sale_price if product.sale_active and product.sale_price else product.price
                stock_status = "Còn hàng" if product.in_stock else "Hết hàng"
                
                result.append({
                    'id': product.id,
                    'name': product.name,
                    'slug': product.slug,
                    'price': float(current_price) if current_price else 0,
                    'sale_price': float(product.sale_price) if product.sale_price else None,
                    'sale_active': product.sale_active,
                    'average_rating': round(avg_rating, 1),
                    'total_reviews': total_reviews,
                    'rating_stars': '★' * int(avg_rating) + '☆' * (5 - int(avg_rating)),
                    'authors': product.authors,
                    'short_desc': product.short_desc,
                    'age_range': f"{product.age_min}-{product.age_max}" if product.age_min and product.age_max else None,
                    'stock_status': stock_status,
                    'categories': [cat.name for cat in product.categories] if product.categories else []
                })
            
            return {
                'status': 'success',
                'data': result,
                'total': len(result)
            }
            
        except Exception as e:
            logger.error(f"Error getting top rated products: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi lấy sản phẩm đánh giá cao nhất'
            }
    
    def get_order_status(self, params):
        """Get order status information"""
        try:
            order = None
            
            if 'order_id' in params and params['order_id']:
                order = Order.query.filter_by(id=params['order_id']).first()
            elif 'phone' in params and params['phone']:
                # Find most recent order by phone
                order = Order.query.filter_by(phone=params['phone']).order_by(Order.created_at.desc()).first()
            
            if not order:
                return {
                    'status': 'not_found',
                    'message': 'Không tìm thấy đơn hàng'
                }
            
            # Map order status to Vietnamese
            status_map = {
                'pending': 'Chờ xác nhận',
                'confirmed': 'Đã xác nhận',
                'processing': 'Đang xử lý',
                'shipped': 'Đã gửi hàng',
                'delivered': 'Đã giao hàng',
                'cancelled': 'Đã hủy'
            }
            
            result = {
                'order_id': order.id,
                'status': status_map.get(order.status, order.status),
                'status_code': order.status,
                'total_amount': float(order.total_amount) if order.total_amount else 0,
                'created_at': order.created_at.strftime('%d/%m/%Y %H:%M') if order.created_at else None,
                'phone': order.phone,
                'address': order.shipping_address
            }
            
            return {
                'status': 'success',
                'data': result
            }
            
        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi lấy thông tin đơn hàng'
            }
    
    def get_policy(self, params):
        """Get policy information"""
        policy_name = params.get('name', '').lower()
        
        policies = {
            'shipping': {
                'title': 'Chính sách giao hàng',
                'content': [
                    'Miễn phí giao hàng với đơn hàng từ 200.000₫',
                    'Giao hàng trong 2-3 ngày làm việc tại TP.HCM',
                    'Giao hàng trong 3-5 ngày làm việc tại các tỉnh khác',
                    'Hỗ trợ giao hàng COD (thanh toán khi nhận hàng)'
                ]
            },
            'return': {
                'title': 'Chính sách đổi trả',
                'content': [
                    'Đổi trả trong vòng 7 ngày kể từ ngày nhận hàng',
                    'Sản phẩm còn nguyên vẹn, chưa sử dụng',
                    'Có hóa đơn mua hàng hợp lệ',
                    'Khách hàng chịu phí vận chuyển đổi trả'
                ]
            },
            'payment': {
                'title': 'Phương thức thanh toán',
                'content': [
                    'Thanh toán khi nhận hàng (COD)',
                    'Chuyển khoản ngân hàng',
                    'Ví điện tử: MoMo, ZaloPay',
                    'Thẻ tín dụng/ghi nợ'
                ]
            },
            'privacy': {
                'title': 'Chính sách bảo mật',
                'content': [
                    'Bảo vệ thông tin cá nhân của khách hàng',
                    'Không chia sẻ thông tin với bên thứ ba',
                    'Sử dụng công nghệ mã hóa SSL',
                    'Tuân thủ luật bảo vệ dữ liệu cá nhân'
                ]
            }
        }
        
        if policy_name in policies:
            return {
                'status': 'success',
                'data': policies[policy_name]
            }
        else:
            return {
                'status': 'not_found',
                'message': 'Không tìm thấy chính sách yêu cầu'
            }
    
    def get_faq(self, params):
        """Get FAQ information"""
        faq_data = {
            'general': [
                {
                    'question': 'Làm thế nào để đặt hàng?',
                    'answer': 'Bạn có thể đặt hàng trực tuyến trên website hoặc gọi hotline để được hỗ trợ.'
                },
                {
                    'question': 'Thời gian giao hàng bao lâu?',
                    'answer': 'Giao hàng trong 2-3 ngày tại TP.HCM và 3-5 ngày tại các tỉnh khác.'
                }
            ],
            'payment': [
                {
                    'question': 'Có thể thanh toán như thế nào?',
                    'answer': 'Hỗ trợ COD, chuyển khoản, ví điện tử và thẻ tín dụng.'
                }
            ]
        }
        
        return {
            'status': 'success',
            'data': faq_data
        }
    
    def get_price_stock(self, params):
        """Get price and stock information"""
        try:
            product = self._find_product_by_reference(params)
            
            if not product:
                return {
                    'status': 'not_found',
                    'message': 'Không tìm thấy sản phẩm'
                }
            
            current_price = product.sale_price if product.sale_active and product.sale_price else product.price
            stock_status = "Còn hàng" if product.in_stock else "Hết hàng"
            
            result = {
                'product_name': product.name,
                'price': float(current_price) if current_price else 0,
                'original_price': float(product.price) if product.price else 0,
                'sale_price': float(product.sale_price) if product.sale_price else None,
                'sale_active': product.sale_active,
                'stock_status': stock_status,
                'in_stock': product.in_stock
            }
            
            return {
                'status': 'success',
                'data': result
            }
            
        except Exception as e:
            logger.error(f"Error getting price/stock: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi lấy thông tin giá và tồn kho'
            }
    
    def list_categories(self, params):
        """Get list of categories"""
        try:
            limit = params.get('limit', 20)
            offset = params.get('offset', 0)
            
            categories = Category.query.filter(
                Category.is_active == True
            ).order_by(Category.sort_order, Category.name).offset(offset).limit(limit).all()
            
            result = []
            for category in categories:
                result.append({
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'intro': category.intro
                })
            
            return {
                'status': 'success',
                'data': result,
                'total': len(result)
            }
            
        except Exception as e:
            logger.error(f"Error listing categories: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi lấy danh sách danh mục'
            }
    
    def search_by_category(self, params):
        """Search products by category"""
        try:
            query = Product.query.filter(Product.is_active == True)
            
            # Category filter
            if 'category_slug' in params and params['category_slug']:
                query = query.join(Product.categories).filter(
                    Category.slug == params['category_slug']
                )
            elif 'category_id' in params and params['category_id']:
                query = query.join(Product.categories).filter(
                    Category.id == params['category_id']
                )
            elif 'category' in params and params['category']:
                query = query.join(Product.categories).filter(
                    Category.name.ilike(f"%{params['category']}%")
                )
            else:
                return {
                    'status': 'error',
                    'message': 'Thiếu thông tin danh mục'
                }
            
            # Limit results
            limit = params.get('limit', 10)
            offset = params.get('offset', 0)
            products = query.offset(offset).limit(limit).all()
            
            # Format response
            result = []
            for product in products:
                current_price = product.sale_price if product.sale_active and product.sale_price else product.price
                stock_status = "Còn hàng" if product.in_stock else "Hết hàng"
                
                result.append({
                    'id': product.id,
                    'name': product.name,
                    'price': float(current_price) if current_price else 0,
                    'sale_price': float(product.sale_price) if product.sale_price else None,
                    'sale_active': product.sale_active,
                    'authors': product.authors,
                    'short_desc': product.short_desc,
                    'age_range': f"{product.age_min}-{product.age_max}" if product.age_min and product.age_max else None,
                    'stock_status': stock_status,
                    'categories': [cat.name for cat in product.categories] if product.categories else []
                })
            
            return {
                'status': 'success',
                'data': result,
                'total': len(result)
            }
            
        except Exception as e:
            logger.error(f"Error searching by category: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi tìm kiếm theo danh mục'
            }
    
    def search_by_age(self, params):
        """Search products by age range"""
        try:
            query = Product.query.filter(Product.is_active == True)
            
            # Age filter
            if 'age_min' in params and params['age_min'] is not None:
                query = query.filter(Product.age_min <= params['age_min'])
            if 'age_max' in params and params['age_max'] is not None:
                query = query.filter(Product.age_max >= params['age_max'])
            
            # If no age filters, return error
            if 'age_min' not in params and 'age_max' not in params:
                return {
                    'status': 'error',
                    'message': 'Thiếu thông tin độ tuổi'
                }
            
            # Limit results
            limit = params.get('limit', 10)
            offset = params.get('offset', 0)
            products = query.offset(offset).limit(limit).all()
            
            # Format response
            result = []
            for product in products:
                current_price = product.sale_price if product.sale_active and product.sale_price else product.price
                stock_status = "Còn hàng" if product.in_stock else "Hết hàng"
                
                result.append({
                    'id': product.id,
                    'name': product.name,
                    'price': float(current_price) if current_price else 0,
                    'sale_price': float(product.sale_price) if product.sale_price else None,
                    'sale_active': product.sale_active,
                    'authors': product.authors,
                    'short_desc': product.short_desc,
                    'age_range': f"{product.age_min}-{product.age_max}" if product.age_min and product.age_max else None,
                    'stock_status': stock_status,
                    'categories': [cat.name for cat in product.categories] if product.categories else []
                })
            
            return {
                'status': 'success',
                'data': result,
                'total': len(result)
            }
            
        except Exception as e:
            logger.error(f"Error searching by age: {e}")
            return {
                'status': 'error',
                'message': 'Lỗi khi tìm kiếm theo độ tuổi'
            }

# Initialize dispatcher
dispatcher = BackendDispatcher()

def dispatch_backend_request_data(data):
    """Dispatch backend request data without making an internal HTTP call."""
    if not data or 'intent' not in data:
        return {
            'status': 'error',
            'message': 'Intent is required'
        }, 400

    intent = data['intent']
    params = data.get('params', data.get('parameters', {}))

    logger.info(f"Backend dispatch - Intent: {intent}, Params: {params}")

    if intent == 'SEARCH_PRODUCTS':
        result = dispatcher.search_products(params)
    elif intent == 'GET_PRODUCT_DETAIL':
        result = dispatcher.get_product_detail(params)
    elif intent == 'GET_BOOK_BY_TITLE':
        result = dispatcher.get_product_detail(params)
    elif intent == 'LIST_CATEGORIES':
        result = dispatcher.list_categories(params)
    elif intent == 'SEARCH_BY_CATEGORY':
        result = dispatcher.search_by_category(params)
    elif intent == 'SEARCH_BY_AGE':
        result = dispatcher.search_by_age(params)
    elif intent == 'GET_ORDER_STATUS':
        result = dispatcher.get_order_status(params)
    elif intent == 'GET_POLICY':
        result = dispatcher.get_policy(params)
    elif intent == 'GET_FAQ':
        result = dispatcher.get_faq(params)
    elif intent == 'GET_PRICE_STOCK':
        result = dispatcher.get_price_stock(params)
    elif intent == 'SEARCH_BY_PRICE_RANGE':
        result = dispatcher.search_by_price_range(params)
    elif intent == 'SEARCH_DISCOUNTED_PRODUCTS':
        result = dispatcher.search_discounted_products(params)
    elif intent == 'GET_RECORD_PRODUCT':
        result = dispatcher.get_record_product(params)
    elif intent == 'SEARCH_BY_CRITERIA':
        result = dispatcher.search_by_criteria(params)
    elif intent == 'SEARCH_BY_CATEGORY_CRITERIA':
        result = dispatcher.search_by_category_criteria(params)
    elif intent == 'GET_STATISTICS':
        result = dispatcher.get_statistics(params)
    elif intent == 'GET_PRODUCT_RATING':
        result = dispatcher.get_product_rating(params)
    elif intent == 'GET_PRODUCT_REVIEWS':
        result = dispatcher.get_product_reviews(params)
    elif intent == 'SEARCH_BY_RATING':
        result = dispatcher.search_by_rating(params)
    elif intent == 'GET_TOP_RATED_PRODUCTS':
        result = dispatcher.get_top_rated_products(params)
    else:
        result = {
            'status': 'error',
            'message': f'Unknown intent: {intent}'
        }

    logger.info(f"Backend dispatch result: {result}")
    return result, 200

@backend_bp.route('/dispatch', methods=['POST'])
def dispatch_request():
    """
    Dispatch backend requests from AI chatbot
    Expected JSON: {"intent": "INTENT_NAME", "parameters": {...}}
    """
    try:
        result, status_code = dispatch_backend_request_data(request.get_json())
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Backend dispatch error: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@backend_bp.route('/health', methods=['GET'])
def backend_health():
    """Health check for backend service"""
    try:
        # Test database connection
        db.session.execute(text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'service': 'backend',
            'database': 'connected'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'service': 'backend',
            'database': 'disconnected',
            'error': str(e)
        }), 500
