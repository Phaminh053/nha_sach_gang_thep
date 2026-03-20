"""Management script for Nha Sach Gang Thep Flask application"""

import os
import click
from flask.cli import with_appcontext
from app import create_app
from app.extensions import db
from app.models import *


# Create application
app = create_app()


@app.cli.command()
@with_appcontext
def init_db():
    """Initialize the database."""
    db.create_all()
    click.echo('Initialized the database.')


@app.cli.command()
@with_appcontext
def seed_db():
    """Seed the database with sample data."""
    try:
        # Create sample categories
        categories = [
            {'name': 'Hoa quả nhập khẩu', 'slug': 'hoa-qua-nhap-khau'},
            {'name': 'Hoa quả Việt Nam', 'slug': 'hoa-qua-viet-nam'},
            {'name': 'Trái cây nhiệt đới', 'slug': 'trai-cay-nhiet-doi'},
        ]
        
        for cat_data in categories:
            if not Category.query.filter_by(slug=cat_data['slug']).first():
                category = Category(**cat_data)
                db.session.add(category)
        
        db.session.commit()
        
        # Create sample products
        import_cat = Category.query.filter_by(slug='hoa-qua-nhap-khau').first()
        local_cat = Category.query.filter_by(slug='hoa-qua-viet-nam').first()
        
        products = [
            {
                'name': 'Táo Envy Nhập Khẩu',
                'slug': 'tao-envy-nhap-khau',
                'short_desc': 'Táo Envy nhập khẩu từ New Zealand, giòn ngọt tự nhiên',
                'price': 149000,
                'sale_price': 129000,
                'image_url': 'https://example.com/tao-envy.jpg',
                'categories': [import_cat] if import_cat else []
            },
            {
                'name': 'Cam Sành Việt Nam',
                'slug': 'cam-sanh-viet-nam',
                'short_desc': 'Cam sành Việt Nam tươi ngọt, giàu vitamin C',
                'price': 45000,
                'image_url': 'https://example.com/cam-sanh.jpg',
                'categories': [local_cat] if local_cat else []
            },
            {
                'name': 'Nho Đỏ Không Hạt',
                'slug': 'nho-do-khong-hat',
                'short_desc': 'Nho đỏ không hạt nhập khẩu, ngọt mát',
                'price': 199000,
                'image_url': 'https://example.com/nho-do.jpg',
                'categories': [import_cat] if import_cat else []
            }
        ]
        
        for prod_data in products:
            if not Product.query.filter_by(slug=prod_data['slug']).first():
                categories = prod_data.pop('categories', [])
                product = Product(**prod_data)
                for cat in categories:
                    product.categories.append(cat)
                db.session.add(product)
                
                # Add stock
                db.session.flush()  # Get product ID
                stock = ProductStock(product_id=product.id, qty_on_hand=50)
                db.session.add(stock)
        
        db.session.commit()
        click.echo('Database seeded with sample data.')
        
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error seeding database: {str(e)}')


@app.cli.command()
@with_appcontext
def reset_db():
    """Reset the database (drop all and recreate)."""
    if click.confirm('This will delete all data. Are you sure?'):
        db.drop_all()
        db.create_all()
        click.echo('Database reset.')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)