"""
Admin views for management functionality
"""
from flask import render_template, request, jsonify, redirect, url_for, flash, session
from app.blueprints.admin import admin_bp
from app.auth import admin_required_web as admin_required, get_current_user, hash_password
from app.models import Product, Category, Order, User, Role
from app.models.product import ProductStock  
from app.models.order import OrderItem
from app.repositories.product_repo import ProductRepository
from app.repositories.category_repo import CategoryRepository 
from app.repositories.order_repo import OrderRepository
from app.services.product_sale_service import ProductSaleService
from app.db import get_session, close_session
from app.extensions import db, csrf
from datetime import datetime, timedelta
from sqlalchemy import func


@admin_bp.route('/login')
def admin_login():
    """Admin login page - redirect to main login with admin check"""
    from flask import redirect, url_for
    return redirect(url_for('site.login', next=url_for('admin.dashboard')))


@admin_bp.before_request
def check_admin_access():
    """Check admin access for all admin routes except login"""
    from flask import request, redirect, url_for, flash
    
    # Allow access to login page
    if request.endpoint == 'admin.admin_login':
        return
        
    # Check if user is logged in and is admin
    user = get_current_user()
    if not user:
        flash('Vui lòng đăng nhập để tiếp tục', 'error')
        return redirect(url_for('admin.admin_login'))
    
    if not user.is_admin():
        flash('Bạn không có quyền truy cập trang quản trị', 'error')
        return redirect(url_for('site.home'))


@admin_bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard with statistics"""
    session_db = get_session()
    try:
        # Get basic statistics
        total_products = session_db.query(Product).count()
        total_orders = session_db.query(Order).count()
        total_users = session_db.query(User).filter(User.role_code == 'customer').count()
        
        # Recent orders (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_orders = session_db.query(Order).filter(
            Order.created_at >= thirty_days_ago
        ).count()
        
        # Total revenue (last 30 days) - only completed orders
        revenue_result = session_db.query(func.sum(Order.grand_total)).filter(
            Order.created_at >= thirty_days_ago,
            Order.status == 'completed'
        ).scalar()
        total_revenue = float(revenue_result or 0)
        
        # Recent orders for display
        recent_orders_list = session_db.query(Order).order_by(
            Order.created_at.desc()
        ).limit(10).all()
        
        # Get sale statistics
        sale_service = ProductSaleService(session_db)
        sale_stats = sale_service.get_sale_statistics()
        
        # Auto update sale status
        sale_service.auto_update_sale_status()
        
        # Get best and least selling books statistics
        book_stats = get_book_sales_stats(session_db)
        
        stats = {
            'total_products': total_products,
            'total_orders': total_orders,
            'total_users': total_users,
            'recent_orders': recent_orders,
            'total_revenue': total_revenue,
            'recent_orders_list': recent_orders_list,  # Pass the objects directly
            'sale_stats': sale_stats,
            'book_stats': book_stats
        }
        
        return render_template('admin/dashboard.html', stats=stats)
        
    finally:
        close_session(session_db)


@admin_bp.route('/inventory')
@admin_required
def inventory_list():
    """Standalone inventory management page"""
    return render_template('admin/inventory.html')


@admin_bp.route('/products')
@admin_required
def products():
    """Product management page"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    per_page = 20
    
    session_db = get_session()
    try:
        product_repo = ProductRepository(session_db)
        products_data, total = product_repo.get_admin_products(search, page, per_page)
        
        # Get categories for filter/form
        categories = session_db.query(Category).filter(Category.is_active == True).all()
        
        return render_template('admin/products.html', 
                             products=products_data,
                             categories=[cat.to_dict() for cat in categories],
                             total=total,
                             page=page,
                             per_page=per_page,
                             search=search)
    finally:
        close_session(session_db)


@admin_bp.route('/products/create', methods=['GET', 'POST'])
@csrf.exempt
@admin_required
def create_product():
    """Create new product"""
    if request.method == 'GET':
        session_db = get_session()
        try:
            categories = session_db.query(Category).filter(Category.is_active == True).all()
            return render_template('admin/product_form.html', 
                                 categories=[cat.to_dict() for cat in categories],
                                 product=None)
        finally:
            close_session(session_db)
    
    # Handle POST request
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Dữ liệu không hợp lệ'}), 400
    
    session_db = get_session()
    try:
        # Validate required fields
        if not data.get('name'):
            return jsonify({'success': False, 'message': 'Tên sách là bắt buộc'}), 400
        
        if not data.get('price'):
            return jsonify({'success': False, 'message': 'Giá sách là bắt buộc'}), 400
        
        # Create new product
        product = Product(
            name=data['name'],
            short_desc=data.get('short_desc'),
            price=float(data['price']),
            sale_price=float(data['sale_price']) if data.get('sale_price') else None,
            image_url=data.get('image_url'),
            is_active=data.get('is_active', True),
            # Book specific fields
            isbn13=data.get('isbn13'),
            sku=data.get('sku'),
            authors=data.get('authors'),
            translators=data.get('translators'),
            illustrators=data.get('illustrators'),
            publisher_name=data.get('publisher_name'),
            publish_year=int(data['publish_year']) if data.get('publish_year') else None,
            pages=int(data['pages']) if data.get('pages') else None,
            dimensions_raw=data.get('dimensions_raw'),
            width_cm=float(data['width_cm']) if data.get('width_cm') else None,
            height_cm=float(data['height_cm']) if data.get('height_cm') else None,
            thickness_mm=float(data['thickness_mm']) if data.get('thickness_mm') else None,
            age_min=int(data['age_min']) if data.get('age_min') else None,
            age_max=int(data['age_max']) if data.get('age_max') else None
        )
        
        # Generate slug from name
        from app.utils.slugs import slugify
        product.slug = slugify(product.name)
        
        session_db.add(product)
        session_db.flush()  # Get the ID
        
        # Add categories if provided
        if data.get('categories'):
            category_ids = [int(cat_id) for cat_id in data['categories']]
            categories = session_db.query(Category).filter(Category.id.in_(category_ids)).all()
            product.categories = categories
        
        # Create initial stock record
        qty_on_hand = int(data.get('qty_on_hand', 0))
        stock = ProductStock(
            product_id=product.id,
            qty_on_hand=qty_on_hand
        )
        session_db.add(stock)
        
        session_db.commit()
        return jsonify({'success': True, 'message': 'Sách đã được tạo thành công'})
        
    except ValueError as e:
        session_db.rollback()
        return jsonify({'success': False, 'message': 'Dữ liệu giá không hợp lệ'}), 400
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'message': f'Lỗi tạo sách: {str(e)}'}), 500
    finally:
        close_session(session_db)


@admin_bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@csrf.exempt
@admin_required
def edit_product(product_id):
    """Edit existing product"""
    session_db = get_session()
    try:
        product = session_db.query(Product).get(product_id)
        if not product:
            flash('Không tìm thấy sách', 'error')
            return redirect(url_for('admin.products'))
        
        if request.method == 'GET':
            categories = session_db.query(Category).filter(Category.is_active == True).all()
            product_dict = product.to_dict(include_relations=True)
            
            # Ensure stock data is included
            if not product_dict.get('stock') and product.stock:
                product_dict['stock'] = product.stock.to_dict()
            elif not product_dict.get('stock'):
                product_dict['stock'] = {'qty_on_hand': 0, 'in_stock': False}
                
            return render_template('admin/product_form.html',
                                 categories=[cat.to_dict() for cat in categories],
                                 product=product_dict)
        
        # Handle POST request - update product
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Dữ liệu không hợp lệ'}), 400
        
        try:
            # Update basic fields
            if 'name' in data:
                product.name = data['name']
            if 'short_desc' in data:
                product.short_desc = data['short_desc']
            if 'price' in data:
                product.price = float(data['price'])
            if 'sale_price' in data and data['sale_price']:
                product.sale_price = float(data['sale_price'])
            else:
                product.sale_price = None
            if 'image_url' in data:
                product.image_url = data['image_url']
            if 'is_active' in data:
                product.is_active = bool(data['is_active'])
            
            # Update book specific fields
            if 'isbn13' in data:
                product.isbn13 = data['isbn13']
            if 'sku' in data:
                product.sku = data['sku']
            if 'authors' in data:
                product.authors = data['authors']
            if 'translators' in data:
                product.translators = data['translators']
            if 'illustrators' in data:
                product.illustrators = data['illustrators']
            if 'publisher_name' in data:
                product.publisher_name = data['publisher_name']
            if 'publish_year' in data and data['publish_year']:
                product.publish_year = int(data['publish_year'])
            if 'pages' in data and data['pages']:
                product.pages = int(data['pages'])
            if 'dimensions_raw' in data:
                product.dimensions_raw = data['dimensions_raw']
            if 'width_cm' in data and data['width_cm']:
                product.width_cm = float(data['width_cm'])
            if 'height_cm' in data and data['height_cm']:
                product.height_cm = float(data['height_cm'])
            if 'thickness_mm' in data and data['thickness_mm']:
                product.thickness_mm = float(data['thickness_mm'])
            if 'age_min' in data and data['age_min']:
                product.age_min = int(data['age_min'])
            if 'age_max' in data and data['age_max']:
                product.age_max = int(data['age_max'])
            
            # Update categories
            if 'categories' in data:
                category_ids = [int(cat_id) for cat_id in data['categories']] if data['categories'] else []
                categories = session_db.query(Category).filter(Category.id.in_(category_ids)).all()
                product.categories = categories
            
            # Update stock
            if 'qty_on_hand' in data:
                if product.stock:
                    product.stock.qty_on_hand = int(data['qty_on_hand'])
                else:
                    # Create stock record if doesn't exist
                    stock = ProductStock(
                        product_id=product.id,
                        qty_on_hand=int(data['qty_on_hand'])
                    )
                    session_db.add(stock)
            
            session_db.commit()
            return jsonify({'success': True, 'message': 'Sách đã được cập nhật thành công'})
            
        except ValueError as e:
            session_db.rollback()
            return jsonify({'success': False, 'message': 'Dữ liệu giá không hợp lệ'}), 400
        except Exception as e:
            session_db.rollback()
            return jsonify({'success': False, 'message': f'Lỗi cập nhật sách: {str(e)}'}), 500
        
    finally:
        close_session(session_db)


@admin_bp.route('/products/<int:product_id>/delete', methods=['POST'])
@csrf.exempt
@admin_required
def delete_product(product_id):
    """Delete product"""
    session_db = get_session()
    try:
        product = session_db.query(Product).get(product_id)
        if not product:
            return jsonify({'success': False, 'message': 'Không tìm thấy sách'}), 404
        
        # Soft delete by setting is_active = False
        product.is_active = False
        session_db.commit()
        
        return jsonify({'success': True, 'message': 'Sách đã được xóa'})
        
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    finally:
        close_session(session_db)


@admin_bp.route('/orders')
@admin_required
def orders():
    """Order management page"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '', type=str)
    per_page = 20
    
    session_db = get_session()
    try:
        order_repo = OrderRepository(session_db)
        orders, total = order_repo.get_orders_for_admin(page, per_page, status)
        
        return render_template('admin/orders.html',
                             orders=orders,
                             total=total,
                             page=page,
                             per_page=per_page,
                             status=status)
    finally:
        close_session(session_db)


@admin_bp.route('/orders/<int:order_id>')
@admin_required
def order_detail(order_id):
    """Order detail page"""
    session_db = get_session()
    try:
        order = session_db.query(Order).get(order_id)
        if not order:
            flash('Không tìm thấy đ�n hàng', 'error')
            return redirect(url_for('admin.orders'))
        
        # Pass the order object directly instead of converting to dict
        # This preserves datetime objects for template strftime usage
        return render_template('admin/order_detail.html', order=order)
        
    finally:
        close_session(session_db)


@admin_bp.route('/orders/<int:order_id>/status', methods=['POST'])
@csrf.exempt
@admin_required
def update_order_status(order_id):
    """Update order status via AJAX"""
    session_db = get_session()
    try:
        # Get order
        order = session_db.query(Order).get(order_id)
        if not order:
            return jsonify({'success': False, 'message': 'Không tìm thấy đơn hàng'}), 404

        # Get new status from request
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({'success': False, 'message': 'Dữ liệu không hợp lệ'}), 400
        
        new_status = data['status']
        
        # Validate status
        valid_statuses = ['pending', 'waiting_admin_confirmation', 'confirmed', 'fulfilled', 'cancelled']
        if new_status not in valid_statuses:
            return jsonify({'success': False, 'message': 'Trạng thái không hợp lệ'}), 400
        
        # Handle cancellation separately to restore stock
        if new_status == 'cancelled':
            from app.services.order_service import OrderService
            order_service = OrderService()
            try:
                order_service.cancel_order(order.order_code, 'Admin đã hủy đơn hàng')
                return jsonify({
                    'success': True, 
                    'message': 'Đơn hàng đã hủy và hoàn kho thành công'
                })
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)}), 400
        
        # Update order status using repository
        order_repo = OrderRepository(session_db)
        success = order_repo.update_order_status(order_id, new_status)
        
        if success:
            session_db.commit()
            status_text = {
                'pending': 'chờ xử lý',
                'waiting_admin_confirmation': 'chờ xác nhận',
                'confirmed': 'đã xác nhận',
                'fulfilled': 'đang giao hàng',
                'cancelled': 'đã hủy'
            }
            return jsonify({
                'success': True, 
                'message': f'Đơn hàng đã được cập nhật thành {status_text.get(new_status, new_status)}'
            })
        else:
            return jsonify({'success': False, 'message': 'Không thể cập nhật trạng thái đơn hàng'}), 400
            
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'message': f'Lỗi hệ thống: {str(e)}'}), 500
    finally:
        close_session(session_db)


@admin_bp.route('/orders/<order_code>/confirm', methods=['POST'])
@csrf.exempt
@admin_required
def confirm_order(order_code):
    """Admin confirms order (moves from pending to confirmed)"""
    session_db = get_session()
    try:
        order = session_db.query(Order).filter_by(order_code=order_code).first()
        if not order:
            return jsonify({'success': False, 'error': 'Không tìm thấy đơn hàng'}), 404
        
        if order.status not in ['pending', 'waiting_admin_confirmation']:
            return jsonify({'success': False, 'error': f'Đơn hàng đang ở trạng thái {order.status}, không thể xác nhận'}), 400
        
        # Update order status to confirmed
        order.status = 'confirmed'
        
        # Add event to order history
        from app.models.order import OrderEvent
        event = OrderEvent(
            order_id=order.id,
            event_type='confirmed',
            note='Admin đã xác nhận đơn hàng'
        )
        session_db.add(event)
        
        session_db.commit()
        
        return jsonify({'success': True, 'message': 'Đã xác nhận đơn hàng!'})
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        close_session(session_db)


@admin_bp.route('/orders/<order_code>/mark-fulfilled', methods=['POST'])
@csrf.exempt
@admin_required
def mark_fulfilled(order_code):
    """Admin marks order as fulfilled (processing completed)"""
    session_db = get_session()
    try:
        order = session_db.query(Order).filter_by(order_code=order_code).first()
        if not order:
            return jsonify({'success': False, 'error': 'Không tìm thấy đơn hàng'}), 404
        
        if order.status != 'confirmed':
            return jsonify({'success': False, 'error': f'Đơn hàng đang ở trạng thái {order.status}, không thể bắt đầu giao hàng'}), 400
        
        # Update order status to fulfilled
        order.status = 'fulfilled'
        
        # Add event to order history
        from app.models.order import OrderEvent
        event = OrderEvent(
            order_id=order.id,
            event_type='fulfilled',
            note='Đơn hàng đang được giao'
        )
        session_db.add(event)
        
        session_db.commit()
        
        return jsonify({'success': True, 'message': 'Đã bắt đầu giao hàng!'})
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        close_session(session_db)

# DEPRECATED: Admin mark delivered route - no longer needed
# Users now confirm receipt directly from fulfilled status
"""
@admin_bp.route('/orders/<order_code>/mark-delivered', methods=['POST'])
@csrf.exempt
@admin_required
def mark_delivered(order_code):
    \"\"\"Admin marks order as delivered\"\"\"
    session_db = get_session()
    try:
        order = session_db.query(Order).filter_by(order_code=order_code).first()
        if not order:
            return jsonify({'success': False, 'error': 'Không tìm thấy đơn hàng'}), 404
        
        if order.status != 'fulfilled':
            return jsonify({'success': False, 'error': f'Đơn hàng đang ở trạng thái {order.status}, không thể đánh dấu đã giao'}), 400
        
        # Mark as delivered by setting transfer_confirmed = True
        from datetime import datetime
        order.transfer_confirmed = True
        order.transfer_confirmed_at = datetime.utcnow()
        session_db.commit()
        
        return jsonify({'success': True, 'message': 'Đã đánh dấu đơn hàng đã giao hàng!'})
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        close_session(session_db)
"""


# DEPRECATED: Admin mark received route - no longer needed  
# Users now confirm receipt directly from fulfilled status
"""
@admin_bp.route('/orders/<order_code>/mark-received', methods=['POST'])
@admin_bp.route('/orders/<order_code>/mark-received', methods=['POST'])
@csrf.exempt
@admin_required
def mark_received(order_code):
    \"\"\"Admin marks that customer has received the order\"\"\"
    session_db = get_session()
    try:
        order = session_db.query(Order).filter_by(order_code=order_code).first()
        if not order:
            return jsonify({'success': False, 'error': 'Không tìm thấy đơn hàng'}), 404
        
        if order.status != 'fulfilled' or not order.transfer_confirmed:
            return jsonify({'success': False, 'error': 'Đơn hàng chưa được giao, không thể xác nhận đã nhận'}), 400
        
        # For COD orders, mark payment as completed when customer receives
        if order.payment_method == 'COD':
            order.payment_status = 'mock_paid'
        
        session_db.commit()
        
        return jsonify({'success': True, 'message': 'Đã xác nhận khách hàng đã nhận hàng!'})
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        close_session(session_db)
"""


@admin_bp.route('/product-sales')
@admin_required
def product_sales():
    """Product sale management page"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    category_id = request.args.get('category_id', '', type=str)
    sale_status = request.args.get('sale_status', '', type=str)
    per_page = 20
    
    session_db = get_session()
    try:
        query = session_db.query(Product).filter(Product.is_active == True)
        
        # Search filter
        if search:
            query = query.filter(Product.name.ilike(f'%{search}%'))
        
        # Category filter
        if category_id:
            query = query.join(Product.categories).filter(Category.id == category_id)
        
        # Sale status filter
        if sale_status == 'on_sale':
            query = query.filter(Product.sale_active == True)
        elif sale_status == 'not_on_sale':
            query = query.filter(Product.sale_active == False)
        
        total = query.count()
        products = query.order_by(Product.name).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        
        # Get categories for filter
        categories = session_db.query(Category).filter(Category.is_active == True).all()
        
        return render_template('admin/product_sales.html',
                             products=[p.to_dict(include_relations=True) for p in products],
                             categories=[cat.to_dict() for cat in categories],
                             total=total,
                             page=page,
                             per_page=per_page,
                             search=search,
                             category_id=category_id,
                             sale_status=sale_status)
    finally:
        close_session(session_db)


@admin_bp.route('/product-sales/<int:product_id>/set-sale', methods=['POST'])
@csrf.exempt
@admin_required
def set_product_sale(product_id):
    """Set sale price for a product"""
    data = request.get_json()
    session_db = get_session()
    try:
        sale_service = ProductSaleService(session_db)
        
        sale_price = data.get('sale_price')
        sale_start = data.get('sale_start')
        sale_end = data.get('sale_end')
        
        # Parse dates
        start_date = None
        end_date = None
        
        if sale_start:
            try:
                start_date = datetime.fromisoformat(sale_start.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'success': False, 'message': 'Định dạng ngày bắt đầu không hợp lệ'}), 400
        
        if sale_end:
            try:
                end_date = datetime.fromisoformat(sale_end.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'success': False, 'message': 'Định dạng ngày kết thúc không hợp lệ'}), 400
        
        # Update product using service
        product = sale_service.set_product_sale(product_id, sale_price, start_date, end_date)
        
        return jsonify({
            'success': True, 
            'message': 'Đã thiết lập giá khuyến mãi thành công',
            'product': product.to_dict()
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'message': 'Có lỗi xảy ra: ' + str(e)}), 400
    finally:
        close_session(session_db)


@admin_bp.route('/product-sales/<int:product_id>/remove-sale', methods=['POST'])
@csrf.exempt
@admin_required
def remove_product_sale(product_id):
    """Remove sale price from a product"""
    session_db = get_session()
    try:
        sale_service = ProductSaleService(session_db)
        product = sale_service.remove_product_sale(product_id)
        
        return jsonify({
            'success': True, 
            'message': 'Đã xóa giá khuyến mãi thành công',
            'product': product.to_dict()
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'message': 'Có lỗi xảy ra: ' + str(e)}), 400
    finally:
        close_session(session_db)


@admin_bp.route('/product-sales/bulk-actions', methods=['POST'])
@csrf.exempt
@admin_required
def bulk_sale_actions():
    """Bulk actions for product sales"""
    data = request.get_json()
    product_ids = data.get('product_ids', [])
    action = data.get('action')
    
    if not product_ids:
        return jsonify({'success': False, 'message': 'Không có sản phẩm nào được chọn'}), 400
    
    session_db = get_session()
    try:
        sale_service = ProductSaleService(session_db)
        
        if action == 'remove_sale':
            count = sale_service.bulk_remove_sales(product_ids)
            return jsonify({
                'success': True, 
                'message': f'Đã xóa giá khuyến mãi cho {count} sản phẩm'
            })
        
        elif action == 'activate_sale':
            count = sale_service.bulk_activate_sales(product_ids)
            return jsonify({
                'success': True, 
                'message': f'Đã kích hoạt khuyến mãi cho {count} sản phẩm'
            })
        
        elif action == 'deactivate_sale':
            count = sale_service.bulk_deactivate_sales(product_ids)
            return jsonify({
                'success': True, 
                'message': f'Đã tạm dừng khuyến mãi cho {count} sản phẩm'
            })
        
        else:
            return jsonify({'success': False, 'message': 'Hành động không hợp lệ'}), 400
            
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'message': 'Có lỗi xảy ra: ' + str(e)}), 400
    finally:
        close_session(session_db)


@admin_bp.route('/product-sales/auto-update', methods=['POST'])
@csrf.exempt
@admin_required
def auto_update_sales():
    """Auto update product sale status based on dates"""
    session_db = get_session()
    try:
        sale_service = ProductSaleService(session_db)
        updated_count = sale_service.auto_update_sale_status()
        
        return jsonify({
            'success': True, 
            'message': f'Đã cập nhật trạng thái cho {updated_count} sản phẩm',
            'updated_count': updated_count
        })
        
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'message': 'Có lỗi xảy ra: ' + str(e)}), 400
    finally:
        close_session(session_db)


@admin_bp.route('/product-sales/statistics')
@admin_required
def sale_statistics():
    """Get sale statistics"""
    session_db = get_session()
    try:
        sale_service = ProductSaleService(session_db)
        stats = sale_service.get_sale_statistics()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': 'Có lỗi xảy ra: ' + str(e)}), 400
    finally:
        close_session(session_db)


# ==================== USER MANAGEMENT ====================

@admin_bp.route('/users')
@admin_required
def users():
    """List all users"""
    session_db = get_session()
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = 20
        search = request.args.get('search', '')
        role_filter = request.args.get('role', '')
        
        # Build query
        query = session_db.query(User)
        
        # Apply search filter
        if search:
            query = query.filter(
                db.or_(
                    User.username.ilike(f'%{search}%'),
                    User.email.ilike(f'%{search}%'),
                    User.full_name.ilike(f'%{search}%')
                )
            )
        
        # Apply role filter
        if role_filter:
            from app.models.user import user_roles
            query = query.join(user_roles).join(Role).filter(Role.code == role_filter)
        
        # Get paginated results
        pagination = query.order_by(User.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        users_list = pagination.items
        
        # Get available roles for filter
        roles = session_db.query(Role).all()
        
        return render_template('admin/users.html',
                             users=users_list,
                             pagination=pagination,
                             search=search,
                             role_filter=role_filter,
                             roles=roles)
        
    finally:
        close_session(session_db)


@admin_bp.route('/users/<int:user_id>')
@admin_required
def user_detail(user_id):
    """User detail page"""
    session_db = get_session()
    try:
        user = session_db.query(User).get(user_id)
        if not user:
            flash('Không tìm thấy người dùng', 'error')
            return redirect(url_for('admin.users'))
        
        # Get user's orders
        orders = session_db.query(Order).filter(Order.user_id == user_id).order_by(
            Order.created_at.desc()
        ).limit(10).all()
        
        # Get available roles
        roles = session_db.query(Role).all()
        
        return render_template('admin/user_detail.html',
                             user=user,
                             orders=orders,
                             roles=roles)
        
    finally:
        close_session(session_db)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Edit user information"""
    session_db = get_session()
    try:
        user = session_db.query(User).get(user_id)
        if not user:
            flash('Không tìm thấy người dùng', 'error')
            return redirect(url_for('admin.users'))
        
        if request.method == 'POST':
            # Get form data
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            full_name = request.form.get('full_name', '').strip()
            phone = request.form.get('phone', '').strip()
            role_ids = request.form.getlist('roles')
            
            # Validate required fields
            if not username:
                flash('Tên đăng nhập không được để trống', 'error')
                return redirect(request.url)
            
            # Check username uniqueness (exclude current user)
            existing_user = session_db.query(User).filter(
                User.username == username,
                User.id != user_id
            ).first()
            if existing_user:
                flash('Tên đăng nhập đã tồn tại', 'error')
                return redirect(request.url)
            
            # Check email uniqueness if provided (exclude current user)
            if email:
                existing_email = session_db.query(User).filter(
                    User.email == email,
                    User.id != user_id
                ).first()
                if existing_email:
                    flash('Email đã tồn tại', 'error')
                    return redirect(request.url)
            
            # Update user info
            user.username = username
            user.email = email if email else None
            user.full_name = full_name if full_name else None
            user.phone = phone if phone else None
            
            # Update roles
            user.roles = []
            if role_ids:
                roles = session_db.query(Role).filter(Role.id.in_(role_ids)).all()
                user.roles = roles
            else:
                # Default to customer role if no roles selected
                customer_role = session_db.query(Role).filter(Role.code == 'customer').first()
                if customer_role:
                    user.roles = [customer_role]
            
            session_db.commit()
            flash('Cập nhật thông tin người dùng thành công', 'success')
            return redirect(url_for('admin.user_detail', user_id=user_id))
        
        # GET request - show edit form
        roles = session_db.query(Role).all()
        
        return render_template('admin/edit_user.html',
                             user=user,
                             roles=roles)
        
    except Exception as e:
        session_db.rollback()
        flash(f'Có lỗi xảy ra: {str(e)}', 'error')
        return redirect(url_for('admin.users'))
    finally:
        close_session(session_db)


@admin_bp.route('/users/<int:user_id>/change-password', methods=['GET', 'POST'])
@admin_required
def change_user_password(user_id):
    """Change user password"""
    session_db = get_session()
    try:
        user = session_db.query(User).get(user_id)
        if not user:
            flash('Không tìm thấy người dùng', 'error')
            return redirect(url_for('admin.users'))
        
        if request.method == 'POST':
            # Get form data
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            
            # Validate passwords
            if not new_password:
                flash('Mật khẩu mới không được để trống', 'error')
                return redirect(request.url)
            
            if len(new_password) < 6:
                flash('Mật khẩu mới phải có ít nhất 6 ký tự', 'error')
                return redirect(request.url)
            
            if new_password != confirm_password:
                flash('Xác nhận mật khẩu không khớp', 'error')
                return redirect(request.url)
            
            # Update password
            user.password_hash = hash_password(new_password)
            session_db.commit()
            
            flash('Đổi mật khẩu thành công', 'success')
            return redirect(url_for('admin.user_detail', user_id=user_id))
        
        # GET request - show change password form
        return render_template('admin/change_password.html', user=user)
        
    except Exception as e:
        session_db.rollback()
        flash(f'Có lỗi xảy ra: {str(e)}', 'error')
        return redirect(url_for('admin.users'))
    finally:
        close_session(session_db)

def get_book_sales_stats(session_db):
    """Get statistics for best selling books and most viewed books"""
    try:
        # Get books with their total sold quantities
        sales_query = session_db.query(
            Product.id,
            Product.name,
            Product.image_url,
            func.coalesce(func.sum(OrderItem.qty), 0).label('total_sold')
        ).outerjoin(
            OrderItem, Product.id == OrderItem.product_id
        ).join(
            Order, OrderItem.order_id == Order.id
        ).filter(
            Order.status.in_(['completed', 'fulfilled'])  # Only count completed/fulfilled orders
        ).group_by(Product.id, Product.name, Product.image_url)
        
        # Get top 5 best selling books
        best_selling = sales_query.order_by(func.sum(OrderItem.qty).desc()).limit(5).all()
        
        # Get top 5 most viewed books
        most_viewed_query = session_db.query(
            Product.id,
            Product.name,
            Product.image_url,
            Product.view_count
        ).filter(
            Product.view_count > 0
        ).order_by(Product.view_count.desc()).limit(5)
        
        most_viewed = most_viewed_query.all()
        
        return {
            'best_selling': [{
                'id': book.id,
                'name': book.name,
                'image_url': book.image_url,
                'total_sold': int(book.total_sold)
            } for book in best_selling],
            'most_viewed': [{
                'id': book.id, 
                'name': book.name,
                'image_url': book.image_url,
                'view_count': int(book.view_count or 0)
            } for book in most_viewed]
        }
        
    except Exception as e:
        print(f"Error getting book sales stats: {e}")
        return {'best_selling': [], 'least_selling': []}
