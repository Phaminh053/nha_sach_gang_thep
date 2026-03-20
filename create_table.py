import os
from app import create_app
from app.extensions import db
from sqlalchemy import text

def create_table():
    print("Manually creating table...")
    
    app = create_app('development')
    with app.app_context():
        # Read the SQL creation string from Alembic logs or write directly
        sql = """
        CREATE TABLE IF NOT EXISTS inventory_transactions (
            id BIGINT NOT NULL AUTO_INCREMENT,
            product_id BIGINT NOT NULL,
            transaction_type ENUM('IN','OUT','ADJUST') NOT NULL,
            reference_type ENUM('ORDER','PURCHASE','RETURN','MANUAL'),
            reference_id VARCHAR(50),
            quantity_changed INTEGER NOT NULL,
            qty_after_transaction INTEGER NOT NULL,
            user_id BIGINT,
            note TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            FOREIGN KEY(product_id) REFERENCES products (id),
            FOREIGN KEY(user_id) REFERENCES users (id)
        )
        """
        db.session.execute(text(sql))
        db.session.commit()
        print("Table created successfully!")

if __name__ == "__main__":
    create_table()
