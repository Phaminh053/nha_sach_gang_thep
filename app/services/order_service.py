"""Order service for managing orders and transactions"""

import string
import random
from datetime import datetime
from app.repositories.order_repo import order_repo
from app.repositories.product_repo import product_repo
from app.services.pricing_service import pricing_service
from app.services.stock_service import stock_service, OutOfStockError
from app.models.order import PaymentMethod, PaymentStatus, OrderStatus, EventType
from app.extensions import db
from typing import Dict, List, Tuple


class OrderError(Exception):
    """Base exception for order-related errors"""
    pass


class OrderService:
    """Service for order management"""
    
    def generate_order_code(self) -> str:
        """Generate unique order code like FJ-8X2K9C"""
        while True:
            # Generate 6 random alphanumeric characters
            code_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            order_code = f"FJ-{code_part}"
            
            # Check if code already exists
            if not order_repo.get_by_code(order_code):
                return order_code
    
    def create_order(self, payload: Dict, idempotency_key: str = None) -> Dict:
        """Create new order with stock reservation"""
        
        # Check idempotency (simplified - in production use Redis/DB)
        # For now, just proceed with order creation
        
        try:
            # Start transaction manually instead of using context manager
            # Validate and prepare data
            customer = payload['customer']
            payment_method = PaymentMethod(payload['payment_method'])
            items = payload['items']
            transfer_confirmed = payload.get('transfer_confirmed', False)
            
            # Generate order code
            order_code = self.generate_order_code()
            
            # Determine initial status based on payment method
            if payment_method == PaymentMethod.COD:
                initial_status = 'waiting_admin_confirmation'
                payment_status = 'unpaid'
            elif payment_method == PaymentMethod.MOCK_TRANSFER:
                if transfer_confirmed:
                    initial_status = 'waiting_admin_confirmation'
                    payment_status = 'transfer_confirmed'
                else:
                    initial_status = 'pending_payment'
                    payment_status = 'unpaid'
            else:
                initial_status = 'pending_payment'
                payment_status = 'unpaid'
            
            # Create order record
            order_data = {
                'user_id': payload.get('user_id'),  # Add user_id from payload
                'order_code': order_code,
                'customer_name': customer['name'],
                'phone': customer['phone'],
                'address': customer['address'],
                'province': customer.get('province'),
                'district': customer.get('district'),
                'ward': customer.get('ward'),
                'payment_method': payment_method.value,  # String value
                'payment_status': payment_status,  # Direct string value
                'status': initial_status,  # Direct string value
                'transfer_confirmed': transfer_confirmed,
                'transfer_confirmed_at': datetime.utcnow() if transfer_confirmed else None
            }
            
            # Process order items
            items_data = []
            subtotal = 0
            
            for item in items:
                product_id = item['product_id']
                qty = item['qty']
                
                # Get product and effective price
                product = product_repo.get_by_id(product_id)
                if not product or not product.is_active:
                    raise OrderError(f"Product {product_id} not found or inactive")
                
                effective_price = pricing_service.get_effective_price_for_order(product_id)
                if effective_price is None:
                    raise OrderError(f"Could not get price for product {product_id}")
                
                # Reserve stock
                try:
                    stock_service.reserve_stock(
                        product_id, 
                        qty,
                        reference_type='ORDER',
                        reference_id=order_code,
                        user_id=payload.get('user_id'),
                        note=f"Khách đặt đơn {order_code}"
                    )
                except OutOfStockError as e:
                    raise OrderError(f"Insufficient stock for {product.name}: requested {e.requested}, available {e.available}")
                
                # Calculate line total
                line_total = effective_price * qty
                subtotal += line_total
                
                # Prepare item data
                items_data.append({
                    'product_id': product_id,
                    'product_name': product.name,
                    'unit_price': effective_price,
                    'qty': qty,
                    'line_total': line_total
                })
            
            # No shipping fee calculation
            shipping_fee = 0
            
            # Calculate totals
            
            grand_total = subtotal  # Remove shipping fee from calculation
            
            # Update order data with totals
            order_data.update({
                'subtotal': subtotal,
                'shipping_fee': shipping_fee,
                'grand_total': grand_total,
                'total_amount': grand_total
            })
            
            # Create order with items
            order = order_repo.create_order(order_data, items_data)
            
            # Add initial event
            order_repo.add_event(order.id, 'placed', "Order placed")
            
            db.session.commit()
            
            # Return order response
            return self._format_order_response(order)
        except Exception as e:
            db.session.rollback()
            raise OrderError(f"Failed to create order: {str(e)}")
    
    def get_order_by_code(self, order_code: str, user_id: str = None) -> Dict:
        """Get order details by order code"""
        if user_id:
            # Ensure user_id is string for consistent comparison
            user_id = str(user_id)
            # For authenticated users, only allow access to their own orders
            order = order_repo.get_by_code_for_user(order_code, user_id)
        else:
            # For backward compatibility with admin or public access
            order = order_repo.get_by_code(order_code)
            
        if not order:
            raise OrderError(f"Order {order_code} not found")
        
        return self._format_order_detail_response(order)
    
    def mock_pay(self, order_code: str, user_id: str = None) -> Dict:
        """Mark order as mock paid"""
        try:
            print(f"Starting mock_pay for order_code: {order_code}")
            
            if user_id:
                # Ensure user_id is string for consistent comparison
                user_id = str(user_id)
                # For authenticated users, ensure they own the order
                order = order_repo.get_by_code_for_user(order_code, user_id)
            else:
                order = order_repo.get_by_code_for_update(order_code)
                
            if not order:
                print(f"Order {order_code} not found")
                raise OrderError(f"Order {order_code} not found")
            
            print(f"Found order: {order.id}, current payment_status: {order.payment_status}")
            
            if order.payment_status == 'paid':
                print("Order already paid, returning early")
                return self._format_order_response(order)
            
            print("Updating payment status to paid")
            # Update payment status
            order.payment_status = 'paid'
            
            print("Adding paid event")
            order_repo.add_event(order.id, 'paid', "User marked as paid")
            
            # Auto-confirm if still pending
            if order.status == 'pending_payment':
                print("Auto-confirming order")
                order.status = 'waiting_admin_confirmation'
                order_repo.add_event(order.id, 'admin_confirmed', "Auto-confirm after payment")
            
            print("Committing transaction")
            db.session.commit()
            print("Transaction committed successfully")
            
            return self._format_order_response(order)
                
        except Exception as e:
            print(f"Error in mock_pay: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            raise OrderError(f"Failed to process payment: {str(e)}")
    
    def update_order_status(self, order_code: str, new_status: str) -> Dict:
        """Update order status (admin function)"""
        try:
            order = order_repo.get_by_code_for_update(order_code)
            if not order:
                raise OrderError(f"Order {order_code} not found")
            
            old_status = order.status
            
            # Validate status transition
            if old_status == 'fulfilled' and new_status != 'fulfilled':
                raise OrderError("Cannot change status of fulfilled order")
            
            # Update status
            order.status = new_status
            
            # Handle stock restoration for cancelled orders
            if new_status == 'cancelled' and old_status != 'cancelled':
                for item in order.items:
                    stock_service.restore_stock(
                        item.product_id, 
                        item.qty,
                        reference_type='RETURN',
                        reference_id=order_code,
                        note=f"Hoàn kho do hủy đơn {order_code}"
                    )
                order_repo.add_event(order.id, 'restocked', "Inventory restored after cancel")
            
            # Add status change event
            order_repo.add_event(order.id, new_status, f"Status changed from {old_status} to {new_status}")
            
            db.session.commit()
            return self._format_order_response(order)
            
        except Exception as e:
            db.session.rollback()
            raise OrderError(f"Failed to update status: {str(e)}")
    
    def search_orders(self, status: str = None, query: str = '', page: int = 1, per_page: int = 20, user_id: str = None) -> Tuple[List[Dict], int]:
        """Search orders with filters"""
        # Ensure user_id is string for consistent comparison
        if user_id:
            user_id = str(user_id)
        orders, total = order_repo.search_orders(status, query, page, per_page, user_id)
        
        return [self._format_order_response(order) for order in orders], total
    
    def cancel_order(self, order_code: str, note: str = None, user_id: str = None) -> Dict:
        """Cancel order if possible"""
        try:
            if user_id:
                # Ensure user_id is string for consistent comparison
                user_id = str(user_id)
                # For authenticated users, ensure they own the order
                order = order_repo.get_by_code_for_user(order_code, user_id)
            else:
                order = order_repo.get_by_code_for_update(order_code)
                
            if not order:
                raise OrderError(f"Order {order_code} not found")
            
            # Only allow cancellation for pending, waiting_admin_confirmation and confirmed orders
            if order.status not in ['pending', 'pending_payment', 'waiting_admin_confirmation', 'confirmed']:
                raise OrderError(f"Cannot cancel order with status: {order.status}")
            
            old_status = order.status
            order.status = 'cancelled'
            
            # Restore stock for cancelled order
            for item in order.items:
                stock_service.restore_stock(
                    item.product_id, 
                    item.qty,
                    reference_type='RETURN',
                    reference_id=order_code,
                    user_id=user_id,
                    note=f"Hoàn kho do hủy đơn {order_code}"
                )
                order_repo.add_event(order.id, 'restocked', f"Restored {item.qty} units of {item.product_name}")
            
            # Add cancellation event
            order_repo.add_event(order.id, 'cancelled', note or f"Đơn hàng được hủy từ trạng thái {old_status}")
            
            db.session.commit()
            return self._format_order_detail_response(order)
            
        except Exception as e:
            db.session.rollback()
            raise OrderError(f"Failed to cancel order: {str(e)}")
    
    def get_orders_by_status(self, status: str, page: int = 1, per_page: int = 20, user_id: str = None) -> Tuple[List[Dict], int]:
        """Get orders by status with pagination"""
        # Ensure user_id is string for consistent comparison
        if user_id:
            user_id = str(user_id)
        orders, total = order_repo.get_orders_by_status(status, page, per_page, user_id)
        
        return [self._format_order_response(order) for order in orders], total
    
    def _format_order_response(self, order) -> Dict:
        """Format order for API response"""
        return {
            'order_code': order.order_code,
            'status': order.status,  # Now it's already string
            'payment_status': order.payment_status,  # Now it's already string
            'amounts': {
                'subtotal': float(order.subtotal) if order.subtotal else None,
                'shipping_fee': float(order.shipping_fee),
                'grand_total': float(order.grand_total)
            },
            'items': [
                {
                    'product_id': item.product_id,
                    'product_name': item.product_name,
                    'unit_price': float(item.unit_price),
                    'qty': item.qty,
                    'line_total': float(item.line_total)
                }
                for item in order.items
            ]
        }
    
    def _format_order_detail_response(self, order) -> Dict:
        """Format detailed order for API response"""
        response = self._format_order_response(order)
        
        # Add customer info and events
        response.update({
            'customer': {
                'name': order.customer_name,
                'phone': order.phone,
                'address': order.address,
                'province': order.province,
                'district': order.district,
                'ward': order.ward
            },
            'payment_method': order.payment_method,  # Already string now
            'events': [
                {
                    'type': event.event_type,  # Already string now
                    'time': event.created_at.isoformat() if event.created_at else None,
                    'note': event.note
                }
                for event in order.events
            ],
            'created_at': order.created_at.isoformat() if order.created_at else None
        })
        
        return response
    
    def confirm_bank_transfer(self, order_code: str, user_id: str = None) -> Dict:
        """Confirm bank transfer by user"""
        try:
            if user_id:
                user_id = str(user_id)
                order = order_repo.get_by_code_for_user(order_code, user_id)
            else:
                order = order_repo.get_by_code(order_code)
                
            if not order:
                raise OrderError(f"Order {order_code} not found")
            
            if order.payment_method != 'MOCK_TRANSFER':
                raise OrderError("Order is not bank transfer payment")
                
            if order.transfer_confirmed:
                return self._format_order_response(order)
            
            # Update transfer confirmation
            order.transfer_confirmed = True
            order.transfer_confirmed_at = datetime.utcnow()
            order.payment_status = 'transfer_confirmed'
            order.status = 'waiting_admin_confirmation'
            
            # Add event
            order_repo.add_event(order.id, 'payment_confirmed', "User confirmed bank transfer")
            
            db.session.commit()
            
            return self._format_order_response(order)
            
        except Exception as e:
            db.session.rollback()
            raise OrderError(f"Failed to confirm transfer: {str(e)}")
    
    def admin_confirm_order(self, order_code: str) -> Dict:
        """Admin confirms the order"""
        try:
            order = order_repo.get_by_code(order_code)
            if not order:
                raise OrderError(f"Order {order_code} not found")
            
            if order.status != 'waiting_admin_confirmation':
                raise OrderError(f"Order status is {order.status}, cannot confirm")
            
            order.status = 'shipping'
            order_repo.add_event(order.id, 'admin_confirmed', "Order confirmed by admin")
            
            db.session.commit()
            
            return self._format_order_response(order)
            
        except Exception as e:
            db.session.rollback()
            raise OrderError(f"Failed to confirm order: {str(e)}")
    
    def mark_as_delivered(self, order_code: str) -> Dict:
        """Mark order as delivered (admin function)"""
        try:
            order = order_repo.get_by_code(order_code)
            if not order:
                raise OrderError(f"Order {order_code} not found")
            
            if order.status != 'shipping':
                raise OrderError(f"Order status is {order.status}, cannot mark as delivered")
            
            order.status = 'delivered'
            order_repo.add_event(order.id, 'delivered', "Order delivered to customer")
            
            db.session.commit()
            
            return self._format_order_response(order)
            
        except Exception as e:
            db.session.rollback()
            raise OrderError(f"Failed to mark as delivered: {str(e)}")
    
    def user_confirm_received(self, order_code: str, user_id: str) -> Dict:
        """User confirms they received the order"""
        try:
            user_id = str(user_id)
            order = order_repo.get_by_code_for_user(order_code, user_id)
            
            if not order:
                raise OrderError(f"Order {order_code} not found")
            
            if order.status != 'fulfilled':
                raise OrderError(f"Order status is {order.status}, cannot confirm received")
            
            order.status = 'completed'
            order.payment_status = 'paid'
            # Also set transfer_confirmed when user confirms receipt
            order.transfer_confirmed = True
            order.transfer_confirmed_at = datetime.utcnow()
            order_repo.add_event(order.id, 'completed', "Order confirmed as received by customer")
            
            db.session.commit()
            
            return self._format_order_response(order)
            
        except Exception as e:
            db.session.rollback()
            raise OrderError(f"Failed to confirm received: {str(e)}")


# Global instance
order_service = OrderService()