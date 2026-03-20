"""Public API endpoints (no authentication required)"""

from flask import request, jsonify
from app.api import api_bp
from app.api.errors import NotFoundError, ValidationAPIError, BusinessLogicError, validate_request_json, serialize_response
from app.auth import login_required, get_current_user
from app.repositories.category_repo import category_repo
from app.repositories.product_repo import product_repo
from app.services.review_service import review_service
from app.services.order_service import order_service, OrderError
from app.schemas.product import ProductQuerySchema, ProductListSchema, ProductDetailSchema
from app.schemas.review import ReviewCreateSchema, ProductReviewSchema, ReviewQuerySchema
from app.schemas.order import OrderCreateSchema, OrderResponseSchema
from app.schemas.category import CategorySchema
from app.utils.pagination import PaginationHelper
from app.utils.idempotency import handle_idempotency
from app.extensions import limiter


# Categories
@api_bp.route('/categories', methods=['GET'])
def get_categories():
    """Get category tree"""
    try:
        categories = category_repo.get_category_tree()
        result = []
        
        for category in categories:
            cat_dict = category.to_dict(include_children=True)
            result.append(cat_dict)
        
        return jsonify(result)
    except Exception as e:
        raise BusinessLogicError(f"Failed to fetch categories: {str(e)}")


# Products
@api_bp.route('/products', methods=['GET'])
def get_products():
    """Search and list products with filters"""
    try:
        # Validate query parameters
        query_data = validate_request_json(ProductQuerySchema, request.args.to_dict())
        
        # Extract parameters
        search_query = query_data.get('q', '')
        category_slug = query_data.get('category')
        price_min = query_data.get('price_min')
        price_max = query_data.get('price_max')
        sort = query_data.get('sort', 'newest')
        page = query_data.get('page', 1)
        page_size = query_data.get('page_size', 24)
        
        # Validate pagination
        page, page_size = PaginationHelper.validate_pagination_params(page, page_size)
        
        # Search products
        products, total = product_repo.search_products(
            query=search_query,
            category_slug=category_slug,
            price_min=price_min,
            price_max=price_max,
            sort=sort,
            page=page,
            per_page=page_size
        )
        
        # Format response
        response_data = PaginationHelper.paginate_data(products, page, page_size, total)
        
        response = jsonify(response_data)
        return PaginationHelper.add_pagination_headers(response, page, page_size, total)
        
    except Exception as e:
        raise BusinessLogicError(f"Failed to search products: {str(e)}")


from flask import request, jsonify, session

@api_bp.route('/products/<slug>', methods=['GET'])
def get_product_detail(slug):
    """Get detailed product information"""
    try:
        product_dict = product_repo.get_product_detail(slug)
        
        if not product_dict:
            raise NotFoundError("Product", slug)
        
        product_id = product_dict.get('id')
        if product_id:
            import logging
            logger = logging.getLogger(__name__)
            
            # Initialize viewed_products in session if not exists
            if 'viewed_products' not in session:
                logger.info("Initializing viewed_products in session")
                session['viewed_products'] = []
                
            logger.info(f"Session viewed_products: {session['viewed_products']}")
            
            # If product hasn't been viewed in this session, increment
            if product_id not in session['viewed_products']:
                logger.info(f"Incrementing view count for product {product_id}")
                success = product_repo.increment_view_count(product_id)
                logger.info(f"Increment success: {success}")
                
                session['viewed_products'].append(product_id)
                session.modified = True
                
                # Update the returned dict
                product_dict['view_count'] = product_dict.get('view_count', 0) + 1
            else:
                logger.info(f"Product {product_id} already in session viewed_products")
        
        return jsonify(product_dict)
        
    except NotFoundError:
        raise
    except Exception as e:
        raise BusinessLogicError(f"Failed to fetch product: {str(e)}")


# Reviews
@api_bp.route('/products/<slug>/reviews', methods=['GET'])
def get_product_reviews(slug):
    """Get reviews for a product"""
    try:
        # Validate query parameters
        query_data = validate_request_json(ReviewQuerySchema, request.args.to_dict())
        page = query_data.get('page', 1)
        page_size = query_data.get('page_size', 10)
        
        # Validate pagination
        page, page_size = PaginationHelper.validate_pagination_params(page, page_size, 50)
        
        # Get reviews
        reviews, total = review_service.get_product_reviews(slug, page, page_size)
        
        # Format response
        response_data = PaginationHelper.paginate_data(reviews, page, page_size, total)
        
        response = jsonify(response_data)
        return PaginationHelper.add_pagination_headers(response, page, page_size, total)
        
    except ValueError as e:
        raise NotFoundError("Product", slug)
    except Exception as e:
        raise BusinessLogicError(f"Failed to fetch reviews: {str(e)}")


@api_bp.route('/products/<slug>/reviews', methods=['POST'])
@limiter.limit("5 per minute")  # Rate limit review creation
def create_product_review(slug):
    """Create a new product review"""
    try:
        # Validate request
        if not request.is_json:
            raise ValidationAPIError("Request must be JSON")
        
        review_data = validate_request_json(ReviewCreateSchema, request.get_json())
        
        # Create review
        review = review_service.create_review(
            product_slug=slug,
            user_name=review_data.get('user_name'),
            rating=review_data['rating'],
            content=review_data['content']
        )
        
        return jsonify(review), 201
        
    except ValueError as e:
        if "not found" in str(e):
            raise NotFoundError("Product", slug)
        raise ValidationAPIError(str(e))
    except Exception as e:
        raise BusinessLogicError(f"Failed to create review: {str(e)}")


# Orders
@api_bp.route('/orders', methods=['POST'])
@login_required
@handle_idempotency
def create_order():
    """Create a new order"""
    try:
        # Get current authenticated user
        current_user = get_current_user()
        
        # Validate request
        if not request.is_json:
            raise ValidationAPIError("Request must be JSON")
        
        order_data = validate_request_json(OrderCreateSchema, request.get_json())
        
        # Add user_id to order data
        order_data['user_id'] = current_user.id
        
        # Get idempotency key from headers
        idempotency_key = request.headers.get('Idempotency-Key')
        
        # Create order
        order = order_service.create_order(order_data, idempotency_key)
        
        return jsonify(order), 201
        
    except OrderError as e:
        if "not found" in str(e) or "inactive" in str(e):
            raise NotFoundError("Product", "")
        elif "stock" in str(e).lower():
            raise BusinessLogicError(str(e))
        else:
            raise BusinessLogicError(str(e))
    except Exception as e:
        raise BusinessLogicError(f"Failed to create order: {str(e)}")


@api_bp.route('/orders/<order_code>', methods=['GET'])
@login_required
def get_order_detail(order_code):
    """Get order details by order code"""
    try:
        # Get current authenticated user
        current_user = get_current_user()
        
        order = order_service.get_order_by_code(order_code, current_user.id)
        return jsonify(order)
        
    except OrderError as e:
        if "not found" in str(e):
            raise NotFoundError("Order", order_code)
        raise BusinessLogicError(str(e))
    except Exception as e:
        raise BusinessLogicError(f"Failed to fetch order: {str(e)}")


@api_bp.route('/orders/<order_code>/mock-pay', methods=['POST'])
@login_required
def mock_pay_order(order_code):
    """Mark order as mock paid"""
    try:
        # Get current authenticated user
        current_user = get_current_user()
        
        order = order_service.mock_pay(order_code, current_user.id)
        return jsonify(order)
        
    except OrderError as e:
        if "not found" in str(e):
            raise NotFoundError("Order", order_code)
        raise BusinessLogicError(str(e))
    except Exception as e:
        raise BusinessLogicError(f"Failed to process payment: {str(e)}")


@api_bp.route('/orders/<order_code>/cancel', methods=['POST'])
@login_required
def cancel_order(order_code):
    """Cancel an order"""
    try:
        # Get current authenticated user
        current_user = get_current_user()
        
        request_data = request.get_json() or {}
        note = request_data.get('note')
        
        order = order_service.cancel_order(order_code, note, current_user.id)
        return jsonify(order)
        
    except OrderError as e:
        if "not found" in str(e):
            raise NotFoundError("Order", order_code)
        raise BusinessLogicError(str(e))
    except Exception as e:
        raise BusinessLogicError(f"Failed to cancel order: {str(e)}")


@api_bp.route('/orders', methods=['GET'])
@login_required
def get_orders():
    """Get orders by status with pagination"""
    try:
        # Get current authenticated user
        current_user = get_current_user()
        
        status = request.args.get('status')
        query = request.args.get('q', '')
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        
        if status:
            orders, total = order_service.get_orders_by_status(status, page, per_page, current_user.id)
        else:
            orders, total = order_service.search_orders(status, query, page, per_page, current_user.id)
        
        return jsonify({
            'orders': orders,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        raise BusinessLogicError(f"Failed to fetch orders: {str(e)}")


# Health check
@api_bp.route('/health', methods=['GET'])
def health_check():
    """API health check"""
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0',
        'api': '/api/v1'
    })