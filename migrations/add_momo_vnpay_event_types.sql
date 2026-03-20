-- Migration: Add momo_paid and vnpay_paid to order_events.event_type enum
-- Run this SQL to sync database with code

-- Step 1: Alter the event_type enum to include new values
ALTER TABLE order_events 
MODIFY COLUMN event_type ENUM(
    'placed',
    'payment_confirmed',
    'admin_confirmed',
    'shipping_started',
    'delivered',
    'completed',
    'cancelled',
    'restocked',
    'mock_paid',
    'confirmed',
    'fulfilled',
    'paid',
    'momo_paid',
    'vnpay_paid'
) NOT NULL;

-- Verify the change
-- SHOW COLUMNS FROM order_events LIKE 'event_type';
