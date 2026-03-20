"""
Inventory Management API
Provides endpoints for admins to view and manage stock
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.auth import login_required, get_current_user
from app.extensions import db
from app.models.product import Product
from app.models.inventory import InventoryTransaction
from app.services.stock_service import stock_service
from app.api.errors import format_error_response
import logging

logger = logging.getLogger(__name__)

inventory_bp = Blueprint('inventory', __name__, url_prefix='/api/v1/admin/inventory')

@inventory_bp.route('', methods=['GET'])
@login_required
def get_inventory():
    """Get products with their current stock levels"""
    user = get_current_user()
    if not user or not user.is_admin():
        return jsonify(format_error_response('UNAUTHORIZED', 'Admin access required')), 403
        
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('query', '')
    
    query = Product.query
    if search:
        query = query.filter(
            db.or_(
                Product.name.ilike(f'%{search}%'),
                Product.sku.ilike(f'%{search}%')
            )
        )
        
    pagination = query.order_by(Product.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    products_data = []
    for p in pagination.items:
        p_dict = {
            'id': p.id,
            'name': p.name,
            'slug': p.slug,
            'sku': p.sku,
            'price': float(p.price) if p.price else 0,
            'image_url': p.image_url,
            'is_active': p.is_active
        }
        qty = p.stock.qty_on_hand if p.stock else 0
        p_dict['stock'] = {
            'qty_on_hand': qty,
            'in_stock': qty > 0
        }
        products_data.append(p_dict)
        
    return jsonify({
        'status': 'success',
        'data': {
            'items': products_data,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }
    })


@inventory_bp.route('/<int:product_id>/transactions', methods=['GET'])
@login_required
def get_inventory_transactions(product_id):
    """Get inventory transaction history for a product"""
    user = get_current_user()
    if not user or not user.is_admin():
        return jsonify(format_error_response('UNAUTHORIZED', 'Admin access required')), 403
        
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    product = Product.query.get_or_404(product_id)
    
    pagination = InventoryTransaction.query.filter_by(product_id=product_id)\
        .order_by(InventoryTransaction.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
        
    return jsonify({
        'status': 'success',
        'data': {
            'product': {
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'current_stock': product.stock.qty_on_hand if product.stock else 0
            },
            'transactions': [tx.to_dict() for tx in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }
    })


@inventory_bp.route('/transaction', methods=['POST'])
@login_required
def create_inventory_transaction():
    """Create a manual inventory transaction (Restock or Adjust)"""
    user = get_current_user()
    if not user or not user.is_admin():
        return jsonify(format_error_response('UNAUTHORIZED', 'Admin access required')), 403
        
    data = request.json
    
    # Validation
    required_fields = ['product_id', 'transaction_type', 'quantity']
    for field in required_fields:
        if field not in data:
            return jsonify(format_error_response('VALIDATION_ERROR', f"Missing required field: {field}")), 400
            
    product_id = int(data['product_id'])
    tx_type = data['transaction_type']
    qty = int(data['quantity'])
    note = data.get('note', '')
    
    if tx_type not in ['IN', 'ADJUST']:
        return jsonify(format_error_response('VALIDATION_ERROR', "Invalid transaction type for manual entry. Use IN or ADJUST.")), 400
        
    if tx_type == 'IN' and qty <= 0:
        return jsonify(format_error_response('VALIDATION_ERROR', "Quantity for IN transaction must be greater than 0")), 400
        
    product = Product.query.get_or_404(product_id)
    admin_id = user.id
    
    try:
        if tx_type == 'IN':
            stock_service.release_stock(
                product_id=product_id,
                qty=qty,
                reference_type='MANUAL',
                user_id=admin_id,
                note=note or 'Manual restock'
            )
            db.session.commit()
        else: # ADJUST
            stock_service.update_stock(
                product_id=product_id,
                qty=qty, # The new absolute quantity
                user_id=admin_id,
                note=note or 'Manual adjustment'
            )
            # update_stock already commits the transaction
            
        # Get updated stock - refresh to get latest data
        db.session.refresh(product)
        updated_stock = product.stock.qty_on_hand if product.stock else 0
        
        return jsonify({
            'status': 'success',
            'message': 'Inventory updated successfully',
            'data': {
                'product_id': product_id,
                'new_quantity': updated_stock
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating inventory transaction: {e}")
        return jsonify(format_error_response('INTERNAL_ERROR', f"Failed to update inventory: {str(e)}")), 500
