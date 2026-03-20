from app.extensions import db
from datetime import datetime

class InventoryTransaction(db.Model):
    """Inventory transaction model for tracking stock changes"""
    __tablename__ = 'inventory_transactions'
    
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    product_id = db.Column(db.BigInteger, db.ForeignKey('products.id'), nullable=False)
    transaction_type = db.Column(db.Enum('IN', 'OUT', 'ADJUST', name='transaction_type_enum'), nullable=False)
    reference_type = db.Column(db.Enum('ORDER', 'PURCHASE', 'RETURN', 'MANUAL', name='reference_type_enum'), nullable=True)
    reference_id = db.Column(db.String(50), nullable=True)
    quantity_changed = db.Column(db.Integer, nullable=False)
    qty_after_transaction = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships definition
    product = db.relationship('Product', backref=db.backref('inventory_transactions', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('inventory_transactions', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'transaction_type': self.transaction_type,
            'reference_type': self.reference_type,
            'reference_id': self.reference_id,
            'quantity_changed': self.quantity_changed,
            'qty_after_transaction': self.qty_after_transaction,
            'user_id': self.user_id,
            'note': self.note,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
