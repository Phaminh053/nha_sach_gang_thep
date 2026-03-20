"""Stock service for inventory management"""

from app.repositories.stock_repo import stock_repo
from app.extensions import db
from typing import Dict


class OutOfStockError(Exception):
    """Raised when product is out of stock"""
    def __init__(self, product_id: int, requested: int, available: int):
        self.product_id = product_id
        self.requested = requested
        self.available = available
        super().__init__(f"Product {product_id}: requested {requested}, available {available}")


class StockService:
    """Service for stock management"""
    
    def check_availability(self, product_id: int, qty: int) -> bool:
        """Check if requested quantity is available"""
        stock = stock_repo.get_by_product_id(product_id)
        return stock and stock.qty_on_hand >= qty
    
    def reserve_stock(self, product_id: int, qty: int, reference_type: str = None, reference_id: str = None, user_id: int = None, note: str = None):
        """Reserve stock for order (decrease quantity)"""
        if not stock_repo.decrease_stock(product_id, qty, reference_type, reference_id, user_id, note):
            stock = stock_repo.get_by_product_id(product_id)
            available = stock.qty_on_hand if stock else 0
            raise OutOfStockError(product_id, qty, available)
    
    def release_stock(self, product_id: int, qty: int, reference_type: str = None, reference_id: str = None, user_id: int = None, note: str = None):
        """Release reserved stock (increase quantity)"""
        stock_repo.increase_stock(product_id, qty, reference_type, reference_id, user_id, note)
    
    def restore_stock(self, product_id: int, qty: int, reference_type: str = None, reference_id: str = None, user_id: int = None, note: str = None):
        """Restore stock when order is cancelled (same as release_stock)"""
        self.release_stock(product_id, qty, reference_type, reference_id, user_id, note)
    
    def update_stock(self, product_id: int, qty: int, user_id: int = None, note: str = None) -> Dict:
        """Update stock quantity (admin function)"""
        stock = stock_repo.set_stock(product_id, qty, user_id, note)
        db.session.commit()
        
        return {
            'product_id': product_id,
            'qty_on_hand': qty,
            'in_stock': qty > 0
        }
    
    def get_stock_info(self, product_id: int) -> Dict:
        """Get stock information for a product"""
        stock = stock_repo.get_by_product_id(product_id)
        
        if not stock:
            return {
                'product_id': product_id,
                'qty_on_hand': 0,
                'in_stock': False
            }
        
        return stock.to_dict()
    
    def bulk_check_availability(self, items: list) -> Dict:
        """Check availability for multiple items"""
        results = {}
        
        for item in items:
            product_id = item['product_id']
            qty = item['qty']
            
            stock = stock_repo.get_by_product_id(product_id)
            available = stock.qty_on_hand if stock else 0
            
            results[product_id] = {
                'requested': qty,
                'available': available,
                'sufficient': available >= qty
            }
        
        return results


# Global instance
stock_service = StockService()