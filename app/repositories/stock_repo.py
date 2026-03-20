"""Stock repository"""

from app.repositories import BaseRepository
from app.models import ProductStock, InventoryTransaction
from app.extensions import db
from typing import Optional


class StockRepository(BaseRepository):
    """Repository for ProductStock operations"""
    
    def __init__(self, db_session=None):
        super().__init__(ProductStock)
        self.db_session = db_session
    
    def get_by_product_id(self, product_id: int) -> Optional[ProductStock]:
        """Get stock by product ID"""
        return self.model.query.filter_by(product_id=product_id).first()
    
    def get_for_update(self, product_id: int) -> Optional[ProductStock]:
        """Get stock with row lock for updates"""
        return self.model.query.filter_by(product_id=product_id)\
                   .with_for_update().first()
    
    def decrease_stock(self, product_id: int, qty: int, reference_type: str = None, reference_id: str = None, user_id: int = None, note: str = None) -> bool:
        """Decrease stock quantity"""
        stock = self.get_for_update(product_id)
        if not stock or stock.qty_on_hand < qty:
            return False
        
        stock.qty_on_hand -= qty
        
        # Log transaction
        tx = InventoryTransaction(
            product_id=product_id,
            transaction_type='OUT',
            reference_type=reference_type,
            reference_id=reference_id,
            quantity_changed=-qty,
            qty_after_transaction=stock.qty_on_hand,
            user_id=user_id,
            note=note
        )
        db.session.add(tx)
        
        return True
    
    def increase_stock(self, product_id: int, qty: int, reference_type: str = None, reference_id: str = None, user_id: int = None, note: str = None):
        """Increase stock quantity"""
        stock = self.get_for_update(product_id)
        if stock:
            stock.qty_on_hand += qty
        else:
            # Create new stock record if not exists
            stock = ProductStock(product_id=product_id, qty_on_hand=qty)
            db.session.add(stock)
            
        # Log transaction
        tx = InventoryTransaction(
            product_id=product_id,
            transaction_type='IN',
            reference_type=reference_type,
            reference_id=reference_id,
            quantity_changed=qty,
            qty_after_transaction=stock.qty_on_hand,
            user_id=user_id,
            note=note
        )
        db.session.add(tx)
    
    def set_stock(self, product_id: int, qty: int, user_id: int = None, note: str = None):
        """Set stock quantity (adjustment)"""
        stock = self.get_for_update(product_id)  # Lock for update
        
        old_qty = 0
        if stock:
            old_qty = stock.qty_on_hand
            stock.qty_on_hand = qty
        else:
            stock = ProductStock(product_id=product_id, qty_on_hand=qty)
            db.session.add(stock)
            
        diff = qty - old_qty
        if diff != 0:
            tx = InventoryTransaction(
                product_id=product_id,
                transaction_type='ADJUST',
                reference_type='MANUAL',
                quantity_changed=diff,
                qty_after_transaction=qty,
                user_id=user_id,
                note=note or f"Manual adjustment from {old_qty} to {qty}"
            )
            db.session.add(tx)
            
        return stock


# Global instance
stock_repo = StockRepository()