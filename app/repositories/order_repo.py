"""Order repository"""

from app.repositories import BaseRepository
from app.models import Order, OrderItem, OrderEvent, OrderStatus
from app.extensions import db
from sqlalchemy import desc, or_
from typing import List, Optional, Tuple


class OrderRepository(BaseRepository):
    """Repository for Order operations"""
    
    def __init__(self, db_session=None):
        super().__init__(Order)
        self.db_session = db_session
    
    def get_by_code(self, order_code: str) -> Optional[Order]:
        """Get order by order code"""
        return self.model.query.filter_by(order_code=order_code).first()
    
    def get_by_code_for_user(self, order_code: str, user_id: str) -> Optional[Order]:
        """Get order by code for specific user (ensuring ownership)"""
        return self.model.query.filter_by(order_code=order_code, user_id=user_id).first()
    
    def get_by_code_for_update(self, order_code: str) -> Optional[Order]:
        """Get order by code with row lock"""
        return self.model.query.filter_by(order_code=order_code)\
                   .with_for_update().first()
    
    def create_order(self, order_data: dict, items_data: List[dict]) -> Order:
        """Create order with items in transaction"""
        # Create order
        order = Order(**order_data)
        db.session.add(order)
        db.session.flush()  # Get order ID
        
        # Create order items
        for item_data in items_data:
            item_data['order_id'] = order.id
            item = OrderItem(**item_data)
            db.session.add(item)
        
        return order
    
    def add_event(self, order_id: int, event_type: str, note: str = None):
        """Add event to order timeline"""
        event = OrderEvent(
            order_id=order_id,
            event_type=event_type,
            note=note
        )
        # Use the session passed to constructor if available
        if self.db_session:
            self.db_session.add(event)
        else:
            db.session.add(event)
    
    def search_orders(self, 
                     status: str = None,
                     search_query: str = '',
                     page: int = 1,
                     per_page: int = 20,
                     user_id: str = None) -> Tuple[List[Order], int]:
        """Search orders with filters"""
        query = self.model.query
        
        # User filter for authenticated users
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        # Status filter
        if status:
            query = query.filter_by(status=status)  # Use status directly as string
        
        # Text search in order_code, customer_name, phone
        if search_query:
            query = query.filter(
                or_(
                    Order.order_code.ilike(f'%{search_query}%'),
                    Order.customer_name.ilike(f'%{search_query}%'),
                    Order.phone.ilike(f'%{search_query}%')
                )
            )
        
        query = query.order_by(desc(Order.created_at))
        
        # Get total count
        total = query.count()
        
        # Pagination
        offset = (page - 1) * per_page
        orders = query.offset(offset).limit(per_page).all()
        
        return orders, total
    
    def get_order_detail(self, order_id: int) -> Optional[Order]:
        """Get order with all relations"""
        return self.model.query.options(
            db.joinedload(Order.items),
            db.joinedload(Order.events)
        ).filter_by(id=order_id).first()
    
    def get_orders_by_status(self, status: str, page: int = 1, per_page: int = 20, user_id: str = None) -> Tuple[List[Order], int]:
        """Get orders by status with pagination"""
        query = self.model.query
        
        # Regular status filtering
        query = query.filter_by(status=status)
        
        # User filter for authenticated users
        if user_id:
            query = query.filter_by(user_id=user_id)
        query = query.order_by(desc(Order.created_at))
        
        # Get total count
        total = query.count()
        
        # Pagination
        offset = (page - 1) * per_page
        orders = query.offset(offset).limit(per_page).all()
        
        return orders, total
    
    def get_orders_for_admin(self, page: int = 1, per_page: int = 20, status: str = None) -> Tuple[List[Order], int]:
        """Get orders for admin interface with pagination and optional status filter"""
        query = self.model.query
        
        # Status filter (if provided)
        if status and status.strip():
            query = query.filter_by(status=status)  # Use status directly as string
        
        query = query.order_by(desc(Order.created_at))
        
        # Get total count
        total = query.count()
        
        # Pagination
        offset = (page - 1) * per_page
        orders = query.offset(offset).limit(per_page).all()
        
        return orders, total
    
    def update_order_status(self, order_id: int, new_status: str, note: str = None) -> bool:
        """Update order status and add event"""
        try:
            # Use the session passed to constructor if available
            if self.db_session:
                order = self.db_session.query(Order).get(order_id)
            else:
                order = self.get_by_id(order_id)
            
            if not order:
                return False
            
            old_status = order.status
            order.status = new_status
            
            # Add status change event
            self.add_event(order_id, new_status, note or f"Đơn hàng chuyển từ {old_status} sang {new_status}")
            
            return True
        except Exception as e:
            print(f"Error updating order status: {e}")
            return False
    
    def cancel_order(self, order_id: int, note: str = None) -> bool:
        """Cancel order if possible"""
        try:
            order = self.get_by_id(order_id)
            if not order:
                return False
            
            # Only allow cancellation for orders that can still be cancelled
            if order.status not in ['pending', 'pending_payment', 'waiting_admin_confirmation', 'confirmed']:
                return False
            
            order.status = 'cancelled'
            self.add_event(order_id, 'cancelled', note or "Đơn hàng đã được hủy")
            
            return True
        except Exception:
            return False


class OrderItemRepository(BaseRepository):
    """Repository for OrderItem operations"""
    
    def __init__(self):
        super().__init__(OrderItem)


class OrderEventRepository(BaseRepository):
    """Repository for OrderEvent operations"""
    
    def __init__(self):
        super().__init__(OrderEvent)


# Global instances
order_repo = OrderRepository()
order_item_repo = OrderItemRepository()
order_event_repo = OrderEventRepository()