-- MoMo Payment Integration Migration
-- Run this script to add MoMo payment tracking columns to orders table

-- Add momo_request_id column
ALTER TABLE orders ADD COLUMN momo_request_id VARCHAR(50) NULL;

-- Add momo_trans_id column  
ALTER TABLE orders ADD COLUMN momo_trans_id VARCHAR(50) NULL;

-- Add MOMO to payment_method enum (if using MySQL ENUM type)
-- Note: This may need adjustment based on your exact table structure
-- If payment_method is VARCHAR, no change needed
-- If payment_method is ENUM, run:
-- ALTER TABLE orders MODIFY COLUMN payment_method ENUM('COD', 'MOCK_TRANSFER', 'MOMO') NOT NULL DEFAULT 'COD';

-- Add 'paid' to payment_status enum (if using MySQL ENUM type)
-- If payment_status is VARCHAR, no change needed
-- If payment_status is ENUM, run:
-- ALTER TABLE orders MODIFY COLUMN payment_status ENUM('unpaid', 'mock_paid', 'paid') NOT NULL DEFAULT 'unpaid';

-- Verify columns were added
DESCRIBE orders;
