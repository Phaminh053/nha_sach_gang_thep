-- Add VNPay transaction reference column to orders table
ALTER TABLE orders ADD COLUMN vnpay_txn_ref VARCHAR(50) NULL AFTER momo_trans_id;

-- Add index for faster lookups
CREATE INDEX idx_orders_vnpay_txn_ref ON orders(vnpay_txn_ref);
