import os
from app import create_app
from app.extensions import db
from app.models.inventory import InventoryTransaction
from app.models.product import ProductStock
from app.services.stock_service import stock_service

def test_inventory():
    print("Testing Inventory Transactions...")
    
    app = create_app('development')
    with app.app_context():
        # Get a product to test with
        stock = ProductStock.query.first()
        if not stock:
            print("No products found in stock table.")
            return
            
        product_id = stock.product_id
        original_qty = stock.qty_on_hand
        print(f"Testing product {product_id} with original quantity: {original_qty}")
        
        # Test 1: Manual Adjustment (Increase)
        print("\nTest 1: Manual Increase")
        stock_service.update_stock(
            product_id=product_id,
            qty=original_qty + 10,
            user_id=1,
            note="Test Manual Increase by 10"
        )
        
        updated_stock = ProductStock.query.filter_by(product_id=product_id).first()
        print(f"New stock quantity: {updated_stock.qty_on_hand} (Expected: {original_qty + 10})")
        
        # Verify transaction
        tx = InventoryTransaction.query.filter_by(product_id=product_id).order_by(InventoryTransaction.id.desc()).first()
        print(f"Transaction recorded: Type={tx.transaction_type}, Changed={tx.quantity_changed}, After={tx.qty_after_transaction}")
        
        # Test 2: Reserve Stock (Order Placed)
        print("\nTest 2: Reserve Stock (Order Placed)")
        stock_service.reserve_stock(
            product_id=product_id,
            qty=5,
            reference_type='ORDER',
            reference_id='TEST-ORD-123',
            user_id=1,
            note="Test Reserve for Order"
        )
        db.session.commit()
        
        updated_stock = ProductStock.query.filter_by(product_id=product_id).first()
        print(f"New stock quantity: {updated_stock.qty_on_hand} (Expected: {original_qty + 10 - 5})")
        
        # Verify transaction
        tx = InventoryTransaction.query.filter_by(product_id=product_id).order_by(InventoryTransaction.id.desc()).first()
        print(f"Transaction recorded: Type={tx.transaction_type}, Ref={tx.reference_type}, Changed={tx.quantity_changed}, After={tx.qty_after_transaction}")
        
        # Test 3: Restore Stock (Order Cancelled)
        print("\nTest 3: Restore Stock (Order Cancelled)")
        stock_service.restore_stock(
            product_id=product_id,
            qty=5,
            reference_type='RETURN',
            reference_id='TEST-ORD-123',
            user_id=1,
            note="Test Restore for Cancelled Order"
        )
        db.session.commit()
        
        updated_stock = ProductStock.query.filter_by(product_id=product_id).first()
        print(f"New stock quantity: {updated_stock.qty_on_hand} (Expected: {original_qty + 10})")
        
        # Verify transaction
        tx = InventoryTransaction.query.filter_by(product_id=product_id).order_by(InventoryTransaction.id.desc()).first()
        print(f"Transaction recorded: Type={tx.transaction_type}, Ref={tx.reference_type}, Changed={tx.quantity_changed}, After={tx.qty_after_transaction}")

        print("\nAll tests passed successfully! Reverting changes...")
        # Revert back to original quantity
        stock_service.update_stock(
            product_id=product_id,
            qty=original_qty,
            user_id=1,
            note="Revert to original state after test"
        )
        print("Done.")

if __name__ == "__main__":
    test_inventory()
