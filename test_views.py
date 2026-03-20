import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import create_app
from app.repositories.product_repo import product_repo

app = create_app()

with app.app_context():
    print("--- ADMIN VIEW PRODUCTS (PAGE 1) ---")
    try:
        products, total = product_repo.get_admin_products(search='', page=1, per_page=10)
        print(f"Total products: {total}")
        for p in products:
            print(f"ID: {p.get('id')} | Name: {p.get('name')[:30]} | Views: {p.get('view_count')}")
    except Exception as e:
        print(f"Error querying db: {e}")
        
    print("\nscript done")
