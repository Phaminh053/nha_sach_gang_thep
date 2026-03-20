from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from app.extensions import csrf
from app.services.stock_service import StockService
from app.services.pricing_service import PricingService
from app.services.order_service import OrderService
from app.services.review_service import ReviewService
from app.services.momo_service import MoMoService
from app.services.vnpay_service import VNPayService
from app.repositories.category_repo import CategoryRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.order_repo import OrderRepository
from app.repositories.review_repo import ReviewRepository
from app.blueprints.site.forms import ReviewForm, CheckoutForm, LoginForm, RegisterForm
from app.models.user import User
from app.models.order import Order
from app.db import get_session, close_session
from app.auth import hash_password, check_password, get_current_user
from sqlalchemy.orm import sessionmaker
from app.db import get_db_session
import uuid

site_bp = Blueprint('site', __name__)

# Utility functions
def get_cart_from_session():
    """Get cart items from session with current prices"""
    cart = session.get('cart', {})
    if not cart:
        return [], 0
    
    db_session = get_db_session()
    try:
        product_repo = ProductRepository(db_session)
        pricing_service = PricingService()
        items = []
        subtotal = 0
        
        for product_id, qty in cart.items():
            product = product_repo.get_by_id(int(product_id))
            if product:
                price = pricing_service.get_effective_price(product.id)
                line_total = float(price) * int(qty)  # Ensure both are proper numeric types
                items.append({
                    'product_id': product.id,
                    'name': product.name,
                    'slug': product.slug,
                    'image_url': product.image_url,
                    'unit_price': price,
                    'qty': qty,
                    'line_total': line_total
                })
                subtotal += line_total
        
        return items, subtotal
    finally:
        db_session.close()

def get_cart_count():
    """Get total items count in cart"""
    cart = session.get('cart', {})
    return sum(cart.values())

def calculate_shipping_fee(subtotal, province=None, district=None, ward=None):
    """Calculate shipping fee based on subtotal and location - DISABLED"""
    # Shipping fee removed - always return 0
    return 0

@site_bp.context_processor
def inject_globals():
    """Inject global variables into all templates"""
    db_session = get_db_session()
    try:
        category_repo = CategoryRepository(db_session)
        categories = category_repo.get_all_active()
        cart_count = get_cart_count()
        
        return {
            'categories': categories,
            'cart_count': cart_count
        }
    finally:
        db_session.close()

# Routes
@site_bp.route('/')
def home():
    """Home page with multiple sections"""
    db_session = get_db_session()
    try:
        product_repo = ProductRepository(db_session)
        pricing_service = PricingService()
        
        # Get products on sale
        sale_products = product_repo.get_products_on_sale(limit=8)
        
        # Get latest products
        latest_products = product_repo.get_latest_products(limit=8)
        
        # Get best selling products with fallback
        try:
            best_selling_products = product_repo.get_best_selling_products(limit=8)
        except Exception as e:
            # Fallback to latest products if no order data exists
            best_selling_products = product_repo.get_latest_products(limit=8)[:4]
        
        # Get top rated products with fallback
        try:
            top_rated_products = product_repo.get_top_rated_products(limit=8)
        except Exception as e:
            # Fallback to latest products if no rating data exists
            top_rated_products = product_repo.get_latest_products(limit=8)[-4:]
        
        # Get featured categories
        try:
            featured_categories = product_repo.get_featured_categories(limit=6)
        except Exception as e:
            # Fallback to all active categories
            category_repo = CategoryRepository(db_session)
            featured_categories = category_repo.get_all_active()[:6]
        
        # Add pricing info for all product lists
        all_product_lists = [sale_products, latest_products, best_selling_products, top_rated_products]
        
        for product_list in all_product_lists:
            for product in product_list:
                # Use sale_active from database for sale products
                if hasattr(product, 'sale_active') and product.sale_active and product.sale_price:
                    product.original_price = float(product.price)
                    product.effective_price = float(product.sale_price)
                else:
                    effective_price = pricing_service.get_effective_price(product.id)
                    product.effective_price = effective_price  # Use separate attribute
                    product.original_price = effective_price
        
        return render_template('site/home.html', 
                             sale_products=sale_products,
                             latest_products=latest_products,
                             best_selling_products=best_selling_products,
                             top_rated_products=top_rated_products,
                             featured_categories=featured_categories)
    finally:
        db_session.close()

@site_bp.route('/about')
def about():
    """About Us page"""
    import json
    import os
    
    # Load the JSON data
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 've-dinh-ti-books.json')
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        # Fallback data if JSON file is not found
        data = {
            "title": "Về Nhà sách Gang Thép",
            "sections": {
                "brand_story": {
                    "title": "Câu chuyện thương hiệu",
                    "content": "Nhà sách Gang Thép thành lập năm 2006 với sứ mệnh mang đến những cuốn sách chất lượng cho trẻ em Việt Nam.",
                    "image_url": "https://dinhtibooks.com.vn/images/contents/2022/05/original/group-11567_1652174627.png"
                },
                "core_values": {
                    "title": "Giá trị cốt lõi",
                    "bullets": [
                        "Thương hiệu được xây dựng từ trái tim",
                        "Tập trung cao độ cho thiếu nhi",
                        "Xây dựng hệ sinh thái bền vững"
                    ],
                    "image_url": "https://dinhtibooks.com.vn/images/contents/2022/05/original/gtcl_1652754898.png"
                },
                "mission": {
                    "title": "Sứ mệnh",
                    "bullets": [
                        "Đồng hành cùng sự phát triển của trẻ em Việt",
                        "Giữ gìn bản sắc văn hóa dân tộc",
                        "Người Việt sáng tạo sách cho trẻ em Việt"
                    ],
                    "image_url": "https://dinhtibooks.com.vn/images/contents/2022/05/original/su-menh_1652754924.png"
                },
                "vision": {
                    "title": "Tầm nhìn",
                    "bullets": [
                        "Trở thành đơn vị xuất bản hàng đầu tại Việt Nam",
                        "Tiên phong xuất bản sách chất lượng cao",
                        "Vươn tầm quốc tế"
                    ],
                    "image_url": "https://dinhtibooks.com.vn/images/contents/2022/05/original/tam-nhin_1652754938.png"
                },
                "logo_meaning": {
                    "title": "Ý NGHĨA LOGO NHÀ SÁCH GANG THÉP",
                    "content": "Khởi nguồn từ niềm đam mê với Sách, mong muốn mang đến cho độc giả mọi lứa tuổi đặc biệt là lứa tuổi thiếu nhi những cuốn sách chất lượng nhất.",
                    "image_url": "https://res.cloudinary.com/drpupg1zv/image/upload/v1759033440/z7058272640938_394d78d0821d33082c68690606d559f8_il9soz.jpg"
                },
                "awards": [],
                "milestones": []
            }
        }
    
    return render_template('site/about.html', data=data)

@site_bp.route('/c/<slug>')
def category(slug):
    """Category listing with filtering and pagination"""
    db_session = get_db_session()
    try:
        category_repo = CategoryRepository(db_session)
        product_repo = ProductRepository(db_session)
        pricing_service = PricingService()
        
        category = category_repo.get_by_slug(slug)
        if not category:
            flash('Danh mục không tồn tại', 'error')
            return redirect(url_for('site.home'))
        
        # Get query parameters
        q = request.args.get('q', '')
        price_min = request.args.get('price_min', type=int)
        price_max = request.args.get('price_max', type=int)
        sort = request.args.get('sort', 'newest')
        page = request.args.get('page', 1, type=int)
        page_size = 24
        
        # Get products with filters
        products, total = product_repo.get_by_category_with_filters(
            category_id=category.id,
            search_term=q,
            price_min=price_min,
            price_max=price_max,
            sort_by=sort,
            page=page,
            per_page=page_size
        )
        
        # Add pricing info
        for product in products:
            effective_price = pricing_service.get_effective_price(product.id)
            product.effective_price = effective_price  # Add this line
            product.price = effective_price
            if pricing_service.is_on_sale(product.id):
                product.original_price = float(product.price_original) if hasattr(product, 'price_original') else float(product.price)
            else:
                product.original_price = effective_price
        
        return render_template('site/category.html',
                             category=category,
                             items=products,
                             total=total,
                             page=page,
                             page_size=page_size,
                             q=q,
                             price_min=price_min,
                             price_max=price_max,
                             sort=sort)
    finally:
        db_session.close()

@site_bp.route('/products')
def products():
    """All products page with filtering and pagination"""
    db_session = get_db_session()
    try:
        category_repo = CategoryRepository(db_session)
        product_repo = ProductRepository(db_session)
        pricing_service = PricingService()
        
        # Get query parameters
        q = request.args.get('q', '')
        category_id = request.args.get('category', type=int)
        price_min = request.args.get('price_min', type=int)
        price_max = request.args.get('price_max', type=int)
        sort = request.args.get('sort', 'newest')
        page = request.args.get('page', 1, type=int)
        page_size = 24
        
        # Get products with filters
        products, total = product_repo.get_all_with_filters(
            search_term=q,
            category_id=category_id,
            price_min=price_min,
            price_max=price_max,
            sort_by=sort,
            page=page,
            per_page=page_size
        )
        
        # Add pricing info
        for product in products:
            effective_price = pricing_service.get_effective_price(product.id)
            product.effective_price = effective_price  # Use separate attribute
            if pricing_service.is_on_sale(product.id):
                product.original_price = float(product.price) if hasattr(product, 'price') else effective_price
            else:
                product.original_price = effective_price
        
        # Get all categories for filter
        categories = category_repo.get_all_active()
        
        # Get selected category for display
        selected_category = None
        if category_id:
            selected_category = category_repo.get_by_id(category_id)
        
        return render_template('site/products.html',
                             items=products,
                             total=total,
                             page=page,
                             page_size=page_size,
                             q=q,
                             categories=categories,
                             selected_category=selected_category,
                             category_id=category_id,
                             price_min=price_min,
                             price_max=price_max,
                             sort=sort)
    finally:
        db_session.close()

@site_bp.route('/p/<slug>')
def product_detail(slug):
    """Product detail page"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🔍 PRODUCT_DETAIL_REQUEST: slug='{slug}'")
    
    db_session = get_db_session()
    try:
        product_repo = ProductRepository(db_session)
        review_repo = ReviewRepository(db_session)
        pricing_service = PricingService()
        stock_service = StockService()
        
        logger.info(f"🔍 Looking for product with slug: '{slug}'")
        product = product_repo.get_by_slug(slug)
        logger.info(f"🔍 Found product: {product}")
        
        if not product:
            logger.warning(f"❌ Product not found for slug: '{slug}'")
            flash('Sản phẩm không tồn tại', 'error')
            return redirect(url_for('site.home'))
        
        # Get pricing info
        effective_price = pricing_service.get_effective_price(product.id)
        is_on_sale = pricing_service.is_on_sale(product.id)
        
        # Set effective_price attribute for template compatibility
        product.effective_price = effective_price
        
        # LOG PRICING DETAILS
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🏪 PRODUCT_DETAIL: {product.name} (ID: {product.id})")
        logger.info(f"   Database: price={product.price}, sale_price={product.sale_price}, sale_active={product.sale_active}")
        logger.info(f"   Calculated: effective_price={effective_price}, is_on_sale={is_on_sale}")
        
        # Set original_price based on sale status for consistent display
        if is_on_sale:
            original_price = float(product.price)
            discount = int(((original_price - effective_price) / original_price) * 100)
            logger.info(f"   Template vars: original_price={original_price}, discount={discount}%")
        else:
            original_price = effective_price  # Same as effective price when not on sale
            logger.info(f"   Template vars: original_price={original_price}, no discount")
        
        # Increment view count (similar to API logic)
        if 'viewed_products' not in session:
            session['viewed_products'] = []
        
        if product.id not in session['viewed_products']:
            logger.info(f"Incrementing view count for product {product.id}")
            success = product_repo.increment_view_count(product.id)
            logger.info(f"Increment success: {success}")
            
            session['viewed_products'].append(product.id)
            session.modified = True
        else:
            logger.info(f"Product {product.id} already in session viewed_products")
        
        # Get stock info
        stock_info = stock_service.get_stock_info(product.id)
        stock_data = {
            'in_stock': stock_info['in_stock'],
            'qty': stock_info.get('qty_on_hand')
        }
        
        # Get reviews with pagination
        page = request.args.get('page', 1, type=int)
        reviews_list, reviews_total = review_repo.get_product_reviews(
            product_id=product.id,
            page=page,
            per_page=10
        )
        
        # Create reviews data object for template compatibility
        class ReviewsData:
            def __init__(self, items, total):
                self.items = items
                self.total = total
        
        reviews_data = ReviewsData(reviews_list, reviews_total)
        
        # Get random products for recommendation (exclude current product)
        random_products_raw = product_repo.get_random_products(limit=10, exclude_id=product.id)
        
        # Prepare random products with pricing info
        random_products = []
        for random_product in random_products_raw:
            random_effective_price = pricing_service.get_effective_price(random_product.id)
            random_is_on_sale = pricing_service.is_on_sale(random_product.id)
            
            # Create a simple object with attributes instead of dict
            class ProductData:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)
            
            # Set original_price based on sale status for consistent display
            if random_is_on_sale:
                original_price_for_random = float(random_product.price)
            else:
                original_price_for_random = random_effective_price  # Same as effective price when not on sale
            
            product_data = ProductData(
                id=random_product.id,
                name=random_product.name,
                slug=random_product.slug,
                image_url=random_product.image_url,
                price=float(random_product.price),
                sale_price=float(random_product.sale_price) if random_product.sale_price else None,
                effective_price=random_effective_price,
                original_price=original_price_for_random,
                sale_active=random_is_on_sale
            )
            random_products.append(product_data)
        
        # Create review form
        review_form = ReviewForm()
        
        return render_template('site/product_detail.html',
                             product=product,
                             effective_price=effective_price,
                             original_price=original_price,
                             is_on_sale=is_on_sale,
                             stock_data=stock_data,
                             reviews=reviews_data,
                             review_form=review_form,
                             random_products=random_products)
    finally:
        db_session.close()

@site_bp.route('/p/<slug>/reviews', methods=['POST'])
def submit_review(slug):
    """Submit product review"""
    # Check if user is logged in
    current_user = get_current_user()
    if not current_user:
        flash('Bạn cần đăng nhập để có thể đánh giá sản phẩm', 'error')
        return redirect(url_for('site.login', next=request.url))
    
    db_session = get_db_session()
    try:
        product_repo = ProductRepository(db_session)
        review_repo = ReviewRepository(db_session)
        review_service = ReviewService()
        
        product = product_repo.get_by_slug(slug)
        if not product:
            flash('Sản phẩm không tồn tại', 'error')
            return redirect(url_for('site.home'))
        
        form = ReviewForm()
        if form.validate_on_submit():
            try:
                # Use logged in user's display name or form data
                user_name = form.user_name.data if form.user_name.data else current_user.display_name
                
                # Use the repo instance with session directly
                review = review_repo.create_review(
                    product_id=product.id,
                    user_name=user_name,
                    rating=form.rating.data,
                    content=form.content.data
                )
                db_session.commit()
                flash('Đánh giá của bạn đã được gửi thành công!', 'success')
            except Exception as e:
                db_session.rollback()
                flash('Có lỗi xảy ra khi gửi đánh giá. Vui lòng thử lại.', 'error')
                print(f"Review submission error: {e}")  # For debugging
        else:
            # Display validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{error}', 'error')
        
        return redirect(url_for('site.product_detail', slug=slug) + '#reviews')
    finally:
        db_session.close()

@site_bp.route('/cart')
def cart():
    """Shopping cart page"""
    items, subtotal = get_cart_from_session()
    return render_template('site/cart.html',
                         items=items,
                         subtotal=subtotal)

@site_bp.route('/cart/add', methods=['POST'])
def add_to_cart():
    """Add product to cart"""
    product_id = request.json.get('product_id')
    qty = request.json.get('qty', 1)
    
    if not product_id:
        return jsonify({'success': False, 'message': 'Thiếu thông tin sản phẩm'})
        
    if qty <= 0:
        return jsonify({'success': False, 'message': 'Số lượng phải lớn hơn 0'})
    
    # Validate product exists and in stock
    db_session = get_db_session()
    try:
        product_repo = ProductRepository(db_session)
        stock_service = StockService()
        
        product = product_repo.get_by_id(product_id)
        if not product:
            return jsonify({'success': False, 'message': 'Sản phẩm không tồn tại'})
        
        stock_info = stock_service.get_stock_info(product_id)
        available_qty = stock_info.get('qty_on_hand', 0)
        
        if available_qty <= 0:
            return jsonify({'success': False, 'message': 'Sản phẩm đã hết hàng'})
        
        # Check current cart quantity
        cart = session.get('cart', {})
        product_id_str = str(product_id)
        current_cart_qty = cart.get(product_id_str, 0)
        new_total_qty = current_cart_qty + qty
        
        # Validate total quantity doesn't exceed available stock
        if new_total_qty > available_qty:
            return jsonify({
                'success': False, 
                'message': f'Số lượng vượt quá hàng có sẵn. Còn lại: {available_qty}, trong giỏ: {current_cart_qty}'
            })
        
        # Add to session cart
        cart[product_id_str] = new_total_qty
        session['cart'] = cart
        
        return jsonify({
            'success': True,
            'message': 'Đã thêm vào giỏ hàng',
            'cart_count': get_cart_count()
        })
    finally:
        db_session.close()

@site_bp.route('/cart/update', methods=['POST'])
def update_cart():
    """Update cart quantities"""
    updates = request.json.get('updates', {})
    
    # Validate stock for each update
    db_session = get_db_session()
    try:
        stock_service = StockService()
        cart = session.get('cart', {})
        
        for product_id, qty in updates.items():
            if qty <= 0:
                cart.pop(product_id, None)
            else:
                # Get available stock
                stock_info = stock_service.get_stock_info(int(product_id))
                available_qty = stock_info.get('qty_on_hand', 0)
                
                if qty > available_qty:
                    return jsonify({
                        'success': False,
                        'message': f'Sản phẩm ID {product_id}: Số lượng vượt quá hàng có sẵn ({available_qty})'
                    })
                
                cart[product_id] = qty
        
        session['cart'] = cart
        
        items, subtotal = get_cart_from_session()
        return jsonify({
            'success': True,
            'subtotal': subtotal,
            'cart_count': get_cart_count()
        })
    finally:
        db_session.close()

@site_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    """Checkout page"""
    # Require user to be logged in for checkout
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để tiến hành đặt hàng', 'warning')
        return redirect(url_for('site.login'))
    
    items, subtotal = get_cart_from_session()
    if not items:
        flash('Giỏ hàng trống', 'error')
        return redirect(url_for('site.cart'))
    
    form = CheckoutForm()
    
    # Auto-fill user information if logged in and form not submitted
    if request.method == 'GET' and 'user_id' in session:
        db_session = get_db_session()
        try:
            user = db_session.query(User).filter_by(id=session['user_id']).first()
            if user:
                # Pre-fill form with user's information
                form.customer_name.data = user.full_name or ''
                form.phone.data = user.phone or ''
        except Exception as e:
            pass  # Continue without pre-filling if there's an error
        finally:
            db_session.close()
    
    if form.validate_on_submit():
        try:
            order_service = OrderService()
            
            # No shipping calculation needed
            shipping_fee = 0
            
            # Create order payload with correct structure
            order_payload = {
                'user_id': session['user_id'],  # Add current user's ID
                'customer': {
                    'name': form.customer_name.data,
                    'phone': form.phone.data,
                    'address': form.address.data,
                    'province': form.province.data,
                    'district': form.district.data,
                    'ward': form.ward.data
                },
                'payment_method': form.payment_method.data,
                'transfer_confirmed': False,  # Not used for MoMo
                'items': [{'product_id': item['product_id'], 'qty': item['qty']} for item in items]
            }
            
            order_response = order_service.create_order(order_payload)
            order_code = order_response['order_code']
            
            # Clear cart
            session.pop('cart', None)
            
            # Handle MoMo payment - redirect to MoMo
            if form.payment_method.data == 'MOMO':
                # Calculate total amount in VND (integer)
                grand_total = int(subtotal + shipping_fee)
                
                # Create MoMo payment request
                momo_result = MoMoService.create_payment_request(
                    order_id=order_code,
                    order_code=order_code,
                    amount=grand_total,
                    order_info=f'Thanh toán đơn hàng {order_code}'
                )
                
                if momo_result['success'] and momo_result['pay_url']:
                    # Store request_id in session for verification later
                    session['momo_request_id'] = momo_result['request_id']
                    session['momo_order_code'] = order_code
                    
                    # Update order with MoMo request ID
                    db_session = get_db_session()
                    try:
                        order = db_session.query(Order).filter_by(order_code=order_code).first()
                        if order:
                            order.momo_request_id = momo_result['request_id']
                            db_session.commit()
                    finally:
                        db_session.close()
                    
                    # Redirect to MoMo payment page
                    return redirect(momo_result['pay_url'])
                else:
                    # MoMo API failed - show error but order is created
                    flash(f'Không thể kết nối MoMo: {momo_result.get("error", "Unknown error")}. Đơn hàng đã được tạo, vui lòng thử thanh toán lại.', 'warning')
                    return redirect(url_for('site.order_detail', order_code=order_code))
            
            # Handle VNPay payment - redirect to VNPay
            if form.payment_method.data == 'VNPAY':
                # Calculate total amount in VND (integer)
                grand_total = int(subtotal + shipping_fee)
                
                # Get client IP
                client_ip = request.remote_addr or '127.0.0.1'
                
                # Create VNPay payment URL
                vnpay_result = VNPayService.create_payment_url(
                    order_code=order_code,
                    amount=grand_total,
                    order_info=f'Thanh toan don hang {order_code}',
                    client_ip=client_ip
                )
                
                if vnpay_result['success'] and vnpay_result['payment_url']:
                    # Store order code in session for verification later
                    session['vnpay_order_code'] = order_code
                    
                    # Update order with VNPay txn ref
                    db_session = get_db_session()
                    try:
                        order = db_session.query(Order).filter_by(order_code=order_code).first()
                        if order:
                            order.vnpay_txn_ref = vnpay_result['txn_ref']
                            db_session.commit()
                    finally:
                        db_session.close()
                    
                    # Redirect to VNPay payment page
                    return redirect(vnpay_result['payment_url'])
                else:
                    # VNPay API failed - show error but order is created
                    flash(f'Không thể kết nối VNPay: {vnpay_result.get("error", "Unknown error")}. Đơn hàng đã được tạo, vui lòng thử thanh toán lại.', 'warning')
                    return redirect(url_for('site.order_detail', order_code=order_code))
            
            # COD payment - redirect to order detail
            flash('Đặt hàng thành công!', 'success')
            return redirect(url_for('site.order_detail', order_code=order_code))
            
        except Exception as e:
            # Log the actual error for debugging
            print(f"Error creating order: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # More specific error message based on the error type
            if "stock" in str(e).lower():
                flash('Một số sản phẩm trong giỏ hàng đã hết hàng.', 'error')
            elif "product" in str(e).lower():
                flash('Có sản phẩm không tồn tại trong giỏ hàng.', 'error')
            else:
                flash(f'Có lỗi xảy ra khi đặt hàng: {str(e)}', 'error')
    
    # No shipping fee calculation needed
    shipping_fee = 0
    
    return render_template('site/checkout.html',
                         form=form,
                         items=items,
                         subtotal=subtotal,
                         shipping_fee=shipping_fee,
                         grand_total=subtotal + shipping_fee)


@site_bp.route('/api/calculate-shipping', methods=['POST'])
@csrf.exempt
def api_calculate_shipping():
    """API endpoint to calculate shipping fee - DISABLED"""
    try:
        data = request.get_json()
        
        return jsonify({
            'success': True,
            'shipping_fee': 0,
            'is_free': True,
            'available_methods': [],
            'selected_rate': None
        })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'shipping_fee': 0  # No shipping fee
        }), 400

@site_bp.route('/orders/<order_code>')
def order_detail(order_code):
    """Order detail page"""
    # Require user to be logged in
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để xem chi tiết đơn hàng', 'warning')
        return redirect(url_for('site.login'))
    
    db_session = get_db_session()
    try:
        order_repo = OrderRepository(db_session)
        order_service = OrderService()
        
        order = order_repo.get_by_code(order_code)
        if not order:
            flash('Đơn hàng không tồn tại', 'error')
            return redirect(url_for('site.home'))
        
        # Check if order belongs to current user - fix type mismatch
        current_user_id = session.get('user_id')
        if order.user_id and str(order.user_id) != str(current_user_id):
            flash('Bạn không có quyền truy cập đơn hàng này', 'error')
            return redirect(url_for('site.home'))
        
        # Get order timeline from events relationship
        timeline = order.events  # Order events are already ordered by created_at desc
        
        return render_template('site/order_detail.html',
                             order=order,
                             timeline=timeline)
    finally:
        db_session.close()


@site_bp.route('/my-orders')
def my_orders():
    """My orders page - show all orders"""
    # Require user to be logged in
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để xem đơn hàng', 'warning')
        return redirect(url_for('site.login'))
    
    status = request.args.get('status', 'all')
    page = int(request.args.get('page', 1))
    per_page = 10
    
    db_session = get_db_session()
    try:
        order_repo = OrderRepository(db_session)
        current_user_id = session['user_id']
        
        if status == 'all':
            orders, total = order_repo.search_orders(None, '', page, per_page, current_user_id)
        else:
            orders, total = order_repo.get_orders_by_status(status, page, per_page, current_user_id)
        
        # Calculate pagination
        total_pages = (total + per_page - 1) // per_page
        
        return render_template('site/my_orders.html',
                             orders=orders,
                             current_status=status,
                             page=page,
                             total_pages=total_pages,
                             total=total)
    finally:
        db_session.close()


@site_bp.route('/orders/<order_code>/cancel', methods=['POST'])
@csrf.exempt
def cancel_order_view(order_code):
    """Cancel order from frontend"""
    
    # Require user to be logged in
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để hủy đơn hàng', 'warning')
        return redirect(url_for('site.login'))
    
    db_session = get_db_session()
    try:
        order_repo = OrderRepository(db_session)
        order_service = OrderService()
        
        # Get cancellation note from form if provided
        note = request.form.get('note', 'Khách hàng yêu cầu hủy đơn hàng')
        
        order = order_repo.get_by_code(order_code)
        if not order:
            flash('Đơn hàng không tồn tại', 'error')
            return redirect(url_for('site.my_orders'))
        
        # Check if order belongs to current user - fix type mismatch
        current_user_id = session.get('user_id')
        if order.user_id and str(order.user_id) != str(current_user_id):
            flash('Bạn không có quyền hủy đơn hàng này', 'error')
            return redirect(url_for('site.my_orders'))
        
        # Only allow cancellation for pending, waiting_admin_confirmation and confirmed orders
        if order.status not in ['pending', 'pending_payment', 'waiting_admin_confirmation', 'confirmed']:
            flash(f'Không thể hủy đơn hàng ở trạng thái: {order.status}', 'error')
            return redirect(url_for('site.order_detail', order_code=order_code))
        
        # Cancel the order using service
        order_service.cancel_order(order_code, note)
        
        flash('Đơn hàng đã được hủy thành công!', 'success')
        return redirect(url_for('site.order_detail', order_code=order_code))
        
    except Exception as e:
        flash(f'Có lỗi xảy ra khi hủy đơn hàng: {str(e)}', 'error')
        return redirect(url_for('site.order_detail', order_code=order_code))
    finally:
        db_session.close()

@site_bp.route('/orders/<order_code>/mock-pay', methods=['POST'])
@csrf.exempt
def mock_pay(order_code):
    """Mock payment for transfer orders"""
    
    # Check if user is logged in
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để thanh toán', 'warning')
        return redirect(url_for('site.login'))
    
    db_session = get_db_session()
    try:
        order_repo = OrderRepository(db_session)
        order_service = OrderService()
        
        order = order_repo.get_by_code(order_code)
        if not order:
            flash('Đơn hàng không tồn tại', 'error')
            return redirect(url_for('site.home'))
        
        # Check if order belongs to current user - fix type mismatch
        current_user_id = session.get('user_id')
        if order.user_id and str(order.user_id) != str(current_user_id):
            flash('Bạn không có quyền truy cập đơn hàng này', 'error')
            return redirect(url_for('site.home'))
        
        if order.payment_method != 'MOCK_TRANSFER':
            flash('Phương thức thanh toán không hợp lệ', 'error')
            return redirect(url_for('site.order_detail', order_code=order_code))
        
        if order.payment_status != 'unpaid':
            flash('Đơn hàng đã được thanh toán', 'info')
            return redirect(url_for('site.order_detail', order_code=order_code))
        
        # Process mock payment
        order_service.mock_pay(order_code)
        
        flash('Xác nhận thanh toán thành công!', 'success')
        return redirect(url_for('site.order_detail', order_code=order_code))
        
    except Exception as e:
        # Log the actual error for debugging
        print(f"Error processing mock payment: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # More specific error messages
        if "Order" in str(e) and "not found" in str(e):
            flash('Đơn hàng không tồn tại.', 'error')
        elif "payment_status" in str(e):
            flash('Trạng thái thanh toán không hợp lệ.', 'error')
        else:
            flash('Có lỗi xảy ra khi xử lý thanh toán. Vui lòng thử lại.', 'error')
        return redirect(url_for('site.order_detail', order_code=order_code))
    finally:
        db_session.close()


# MoMo Payment Routes
@site_bp.route('/momo/ipn', methods=['POST'])
@csrf.exempt
def momo_ipn():
    """MoMo IPN (Instant Payment Notification) callback - server to server"""
    import json
    
    try:
        # Get IPN data from MoMo
        data = request.get_json()
        
        if not data:
            return jsonify({'message': 'Invalid data'}), 400
        
        # Log IPN for debugging
        print(f"MoMo IPN received: {json.dumps(data, indent=2)}")
        
        # Verify signature
        if not MoMoService.verify_ipn_signature(data):
            print("MoMo IPN: Invalid signature")
            return jsonify({'message': 'Invalid signature'}), 400
        
        # Get order info from IPN data
        order_code = data.get('orderId')
        result_code = data.get('resultCode')
        trans_id = data.get('transId')
        
        if not order_code:
            return jsonify({'message': 'Missing orderId'}), 400
        
        db_session = get_db_session()
        try:
            order = db_session.query(Order).filter_by(order_code=order_code).first()
            
            if not order:
                print(f"MoMo IPN: Order {order_code} not found")
                return jsonify({'message': 'Order not found'}), 404
            
            # Check if payment is successful (resultCode = 0)
            if MoMoService.is_payment_successful(result_code):
                # Update order status
                order.payment_status = 'paid'
                order.status = 'waiting_admin_confirmation'
                order.momo_trans_id = str(trans_id) if trans_id else None
                
                # Add order event
                from app.models.order import OrderEvent
                event = OrderEvent(
                    order_id=order.id,
                    event_type='momo_paid',
                    note=f'Thanh toán MoMo thành công. Trans ID: {trans_id}'
                )
                db_session.add(event)
                
                db_session.commit()
                print(f"MoMo IPN: Order {order_code} paid successfully")
            else:
                # Payment failed - log but don't change status
                print(f"MoMo IPN: Payment failed for order {order_code}, resultCode: {result_code}")
            
            return jsonify({'message': 'Success'}), 200
            
        finally:
            db_session.close()
            
    except Exception as e:
        print(f"MoMo IPN error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'message': 'Internal error'}), 500


@site_bp.route('/momo/return')
def momo_return():
    """MoMo return URL - user is redirected back here after payment"""
    
    # Get query parameters from MoMo redirect
    order_code = request.args.get('orderId')
    result_code = request.args.get('resultCode')
    message = request.args.get('message', '')
    trans_id = request.args.get('transId', '')
    
    if not order_code:
        flash('Không tìm thấy thông tin đơn hàng', 'error')
        return redirect(url_for('site.home'))
    
    db_session = get_db_session()
    try:
        order = db_session.query(Order).filter_by(order_code=order_code).first()
        
        if not order:
            flash('Đơn hàng không tồn tại', 'error')
            return redirect(url_for('site.home'))
        
        # Check payment result
        if result_code and int(result_code) == 0:
            # Payment successful - update order status if not already updated by IPN
            if order.payment_status != 'paid':
                order.payment_status = 'paid'
                order.status = 'waiting_admin_confirmation'
                order.momo_trans_id = str(trans_id) if trans_id else None
                
                # Add order event
                from app.models.order import OrderEvent
                event = OrderEvent(
                    order_id=order.id,
                    event_type='momo_paid',
                    note=f'Thanh toán MoMo thành công. Trans ID: {trans_id}'
                )
                db_session.add(event)
                db_session.commit()
            
            flash('Thanh toán MoMo thành công! Cảm ơn bạn đã đặt hàng.', 'success')
        else:
            # Payment failed or cancelled
            flash(f'Thanh toán chưa thành công: {message}. Bạn có thể thử lại sau.', 'warning')
        
        return redirect(url_for('site.order_detail', order_code=order_code))
        
    finally:
        db_session.close()


# VNPay Payment Routes
@site_bp.route('/vnpay/return')
def vnpay_return():
    """VNPay return URL - user is redirected back here after payment"""
    
    # Get all query parameters from VNPay redirect
    query_params = dict(request.args)
    
    order_code = query_params.get('vnp_TxnRef')
    response_code = query_params.get('vnp_ResponseCode', '')
    
    if not order_code:
        flash('Không tìm thấy thông tin đơn hàng', 'error')
        return redirect(url_for('site.home'))
    
    # Verify signature
    if not VNPayService.verify_return_signature(query_params):
        print(f"VNPay Return: Invalid signature for order {order_code}")
        flash('Chữ ký không hợp lệ. Vui lòng liên hệ hỗ trợ.', 'error')
        return redirect(url_for('site.order_detail', order_code=order_code))
    
    db_session = get_db_session()
    try:
        order = db_session.query(Order).filter_by(order_code=order_code).first()
        
        if not order:
            flash('Đơn hàng không tồn tại', 'error')
            return redirect(url_for('site.home'))
        
        # Check payment result
        if VNPayService.is_payment_successful(response_code):
            # Update order status if not already updated by IPN
            if order.payment_status != 'paid':
                order.payment_status = 'paid'
                order.status = 'waiting_admin_confirmation'
                
                # Add order event
                from app.models.order import OrderEvent
                trans_no = query_params.get('vnp_TransactionNo', '')
                event = OrderEvent(
                    order_id=order.id,
                    event_type='vnpay_paid',
                    note=f'Thanh toán VNPay thành công. Trans No: {trans_no}'
                )
                db_session.add(event)
                db_session.commit()
            
            flash('Thanh toán VNPay thành công! Cảm ơn bạn đã đặt hàng.', 'success')
        else:
            # Payment failed or cancelled
            message = VNPayService.get_response_message(response_code)
            flash(f'Thanh toán chưa thành công: {message}. Bạn có thể thử lại sau.', 'warning')
        
        return redirect(url_for('site.order_detail', order_code=order_code))
        
    finally:
        db_session.close()


@site_bp.route('/vnpay/ipn', methods=['GET', 'POST'])
@csrf.exempt
def vnpay_ipn():
    """VNPay IPN (Instant Payment Notification) callback - server to server"""
    import json
    
    try:
        # Get IPN data from VNPay (can be GET or POST)
        if request.method == 'POST':
            data = request.get_json() or dict(request.form)
        else:
            data = dict(request.args)
        
        if not data:
            return jsonify({'RspCode': '99', 'Message': 'Invalid data'})
        
        # Log IPN for debugging
        print(f"VNPay IPN received: {json.dumps(data, indent=2)}")
        
        # Verify signature
        if not VNPayService.verify_return_signature(data):
            print("VNPay IPN: Invalid signature")
            return jsonify({'RspCode': '97', 'Message': 'Invalid signature'})
        
        # Get order info from IPN data
        order_code = data.get('vnp_TxnRef')
        response_code = data.get('vnp_ResponseCode', '')
        trans_no = data.get('vnp_TransactionNo', '')
        amount = data.get('vnp_Amount', '')
        
        if not order_code:
            return jsonify({'RspCode': '01', 'Message': 'Order not found'})
        
        db_session = get_db_session()
        try:
            order = db_session.query(Order).filter_by(order_code=order_code).first()
            
            if not order:
                print(f"VNPay IPN: Order {order_code} not found")
                return jsonify({'RspCode': '01', 'Message': 'Order not found'})
            
            # Verify amount (VNPay sends amount * 100)
            expected_amount = int(float(order.grand_total) * 100)
            received_amount = int(amount) if amount else 0
            
            if received_amount != expected_amount:
                print(f"VNPay IPN: Amount mismatch. Expected {expected_amount}, received {received_amount}")
                return jsonify({'RspCode': '04', 'Message': 'Invalid amount'})
            
            # Check if already processed
            if order.payment_status == 'paid':
                print(f"VNPay IPN: Order {order_code} already paid")
                return jsonify({'RspCode': '02', 'Message': 'Order already confirmed'})
            
            # Check if payment is successful (responseCode = "00")
            if VNPayService.is_payment_successful(response_code):
                # Update order status
                order.payment_status = 'paid'
                order.status = 'waiting_admin_confirmation'
                
                # Add order event
                from app.models.order import OrderEvent
                event = OrderEvent(
                    order_id=order.id,
                    event_type='vnpay_paid',
                    note=f'Thanh toán VNPay thành công. Trans No: {trans_no}'
                )
                db_session.add(event)
                
                db_session.commit()
                print(f"VNPay IPN: Order {order_code} paid successfully")
                return jsonify({'RspCode': '00', 'Message': 'Confirm Success'})
            else:
                # Payment failed - log but don't change status
                print(f"VNPay IPN: Payment failed for order {order_code}, responseCode: {response_code}")
                return jsonify({'RspCode': '00', 'Message': 'Confirm Success'})
            
        finally:
            db_session.close()
            
    except Exception as e:
        print(f"VNPay IPN error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'RspCode': '99', 'Message': 'Unknown error'})


# Authentication routes
@site_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    form = LoginForm()
    
    if form.validate_on_submit():
        db_session = get_db_session()
        try:
            user = db_session.query(User).filter_by(username=form.username.data).first()
            
            if user and check_password(form.password.data, user.password_hash):
                if not user.is_active:
                    flash('Tài khoản đã bị vô hiệu hóa', 'error')
                    return render_template('site/login.html', form=form)
                
                # Update last login
                user.update_last_login()
                db_session.commit()
                
                # Store user in session with proper session management
                session['user_id'] = user.id
                session['user_email'] = user.email
                session['user_name'] = user.display_name
                session['user_full_name'] = user.full_name
                session['user_phone'] = user.phone
                session['user_role'] = user.role_code
                
                # Set session as permanent for better persistence
                session.permanent = True
                
                # Force session to be saved
                session.modified = True
                
                flash(f'Chào mừng {user.full_name}!', 'success')
                
                # Redirect to appropriate page based on user role
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                elif user.is_admin():
                    return redirect(url_for('admin.dashboard'))
                else:
                    return redirect(url_for('site.home'))
            else:
                flash('Tên đăng nhập hoặc mật khẩu không đúng', 'error')
                
        except Exception as e:
            flash('Có lỗi xảy ra khi đăng nhập', 'error')
        finally:
            db_session.close()
    
    return render_template('site/login.html', form=form)


@site_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page"""
    form = RegisterForm()
    
    if form.validate_on_submit():
        db_session = get_db_session()
        try:
            # Create new user
            user = User(
                username=form.username.data,
                email=form.email.data,
                password_hash=hash_password(form.password.data),
                full_name=form.full_name.data or None,
                phone=form.phone.data or None,
                is_active=True,
                email_verified=False
            )
            
            db_session.add(user)
            db_session.commit()
            
            flash('Đăng ký thành công! Bạn có thể đăng nhập ngay bây giờ.', 'success')
            return redirect(url_for('site.login'))
            
        except Exception as e:
            db_session.rollback()
            flash('Có lỗi xảy ra khi đăng ký. Vui lòng thử lại.', 'error')
        finally:
            db_session.close()
    
    return render_template('site/register.html', form=form)


@site_bp.route('/logout')
def logout():
    """Logout user"""
    user_name = session.get('user_name', 'Bạn')
    session.clear()
    flash(f'Tạm biệt {user_name}!', 'info')
    return redirect(url_for('site.home'))


@site_bp.route('/profile')
def profile():
    """User profile page"""
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để xem thông tin cá nhân', 'warning')
        return redirect(url_for('site.login'))
    
    db_session = get_db_session()
    try:
        user = db_session.query(User).filter_by(id=session['user_id']).first()
        if not user:
            session.clear()
            flash('Phiên đăng nhập đã hết hạn', 'warning')
            return redirect(url_for('site.login'))
        
        return render_template('site/profile.html', user=user)
    finally:
        db_session.close()


@site_bp.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    """Edit user profile"""
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để chỉnh sửa thông tin', 'warning')
        return redirect(url_for('site.login'))
    
    db_session = get_db_session()
    try:
        user = db_session.query(User).filter_by(id=session['user_id']).first()
        if not user:
            session.clear()
            flash('Phiên đăng nhập đã hết hạn', 'warning')
            return redirect(url_for('site.login'))
        
        if request.method == 'POST':
            # Get form data
            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            
            # Validate email uniqueness if provided and changed
            if email and email != user.email:
                existing_email = db_session.query(User).filter(
                    User.email == email,
                    User.id != user.id
                ).first()
                if existing_email:
                    flash('Email này đã được sử dụng bởi tài khoản khác', 'error')
                    return render_template('site/edit_profile.html', user=user)
            
            # Update user info
            user.full_name = full_name if full_name else None
            user.email = email if email else None
            user.phone = phone if phone else None
            
            db_session.commit()
            
            # Update session with new display name
            session['user_name'] = user.display_name
            
            flash('Cập nhật thông tin thành công!', 'success')
            return redirect(url_for('site.profile'))
        
        # GET request - show edit form
        return render_template('site/edit_profile.html', user=user)
        
    except Exception as e:
        db_session.rollback()
        flash(f'Có lỗi xảy ra: {str(e)}', 'error')
        return redirect(url_for('site.profile'))
    finally:
        db_session.close()


@site_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    """Change user password"""
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để tiếp tục', 'error')
        return redirect(url_for('site.login'))
    
    db_session = get_session()
    try:
        user = db_session.query(User).get(session['user_id'])
        if not user:
            flash('Không tìm thấy thông tin người dùng', 'error')
            return redirect(url_for('site.login'))
        
        if request.method == 'POST':
            # Get form data
            current_password = request.form.get('current_password', '').strip()
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            
            # Validate current password
            if not current_password or not check_password(current_password, user.password_hash):
                flash('Mật khẩu hiện tại không đúng', 'error')
                return render_template('site/change_password.html', user=user)
            
            # Validate new password
            if not new_password:
                flash('Mật khẩu mới không được để trống', 'error')
                return render_template('site/change_password.html', user=user)
            
            if len(new_password) < 6:
                flash('Mật khẩu mới phải có ít nhất 6 ký tự', 'error')
                return render_template('site/change_password.html', user=user)
            
            if new_password != confirm_password:
                flash('Xác nhận mật khẩu không khớp', 'error')
                return render_template('site/change_password.html', user=user)
            
            # Update password
            user.password_hash = hash_password(new_password)
            db_session.commit()
            
            flash('Đổi mật khẩu thành công', 'success')
            return redirect(url_for('site.profile'))
        
        # GET request - show change password form
        return render_template('site/change_password.html', user=user)
        
    except Exception as e:
        db_session.rollback()
        flash(f'Có lỗi xảy ra: {str(e)}', 'error')
        return redirect(url_for('site.profile'))
    finally:
        db_session.close()


@site_bp.route('/orders/<order_code>/confirm-transfer', methods=['POST'])
@csrf.exempt
def confirm_transfer(order_code):
    """User confirms bank transfer payment"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        order_service = OrderService()
        result = order_service.confirm_bank_transfer(order_code, session['user_id'])
        return jsonify({'success': True, 'message': 'Đã xác nhận chuyển khoản!', 'order': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@site_bp.route('/orders/<order_code>/complete', methods=['POST'])
@csrf.exempt
def complete_order(order_code):
    """User confirms receipt of order"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        order_service = OrderService()
        result = order_service.complete_order(order_code, session['user_id'])
        flash('Cảm ơn bạn đã xác nhận nhận hàng!', 'success')
        return jsonify({'success': True, 'message': 'Đã xác nhận nhận hàng!', 'order': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@site_bp.route('/user/orders/<order_code>/confirm-received', methods=['POST'])
@csrf.exempt
def confirm_received(order_code):
    """User confirms receipt of order (new endpoint matching JavaScript)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Bạn cần đăng nhập để thực hiện thao tác này'}), 401
    
    session_db = get_session()
    try:
        # Get order and verify ownership
        order = session_db.query(Order).filter_by(order_code=order_code, user_id=str(session['user_id'])).first()
        if not order:
            return jsonify({'success': False, 'error': 'Không tìm thấy đơn hàng hoặc bạn không có quyền truy cập'}), 404
        
        # Check if order can be confirmed as received
        if order.status != 'fulfilled':
            return jsonify({'success': False, 'error': 'Đơn hàng chưa hoàn thành, không thể xác nhận đã nhận'}), 400
        
        # Check if already confirmed
        if order.status == 'completed':
            return jsonify({'success': False, 'error': 'Đơn hàng đã được xác nhận nhận hàng trước đó'}), 400
        
        # Update order status to completed
        order.status = 'completed'
        
        # For COD orders, mark payment as completed when customer receives
        if order.payment_method == 'COD':
            order.payment_status = 'mock_paid'
        
        # For transfer orders, ensure transfer is confirmed
        if order.payment_method == 'MOCK_TRANSFER':
            order.transfer_confirmed = True
        
        # Add event to order history
        from app.models.order import OrderEvent
        event = OrderEvent(
            order_id=order.id,
            event_type='completed',
            note='Khách hàng đã xác nhận nhận hàng'
        )
        session_db.add(event)
        
        session_db.commit()
        
        return jsonify({'success': True, 'message': 'Cảm ơn bạn đã xác nhận nhận hàng! Đơn hàng đã hoàn tất.'})
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        close_session(session_db)

@site_bp.route('/chatbot-test')
def chatbot_test():
    """Test page for chatbot functionality"""
    return render_template('chatbot_test.html')

@site_bp.route('/chatbot-demo')
def chatbot_demo():
    """Demo page for chatbot features"""
    return render_template('chatbot_demo.html')