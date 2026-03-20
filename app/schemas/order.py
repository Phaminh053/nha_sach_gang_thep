"""Order schemas for validation and serialization"""

from marshmallow import Schema, fields, validate, validates, ValidationError
from app.schemas import BaseSchema, PaginationSchema


class CustomerSchema(Schema):
    """Schema for customer information"""
    name = fields.String(required=True, validate=validate.Length(min=2, max=100))
    phone = fields.String(required=True, validate=validate.Length(min=10, max=30))
    address = fields.String(required=True, validate=validate.Length(min=10))
    province = fields.String(allow_none=True, validate=validate.Length(max=100))
    district = fields.String(allow_none=True, validate=validate.Length(max=100))
    ward = fields.String(allow_none=True, validate=validate.Length(max=100))


class OrderItemRequestSchema(Schema):
    """Schema for order item in request"""
    product_id = fields.Integer(required=True, validate=validate.Range(min=1))
    qty = fields.Integer(required=True, validate=validate.Range(min=1))


class OrderItemResponseSchema(Schema):
    """Schema for order item in response"""
    product_id = fields.Integer()
    product_name = fields.String()
    unit_price = fields.Decimal(as_string=False)
    qty = fields.Integer()
    line_total = fields.Decimal(as_string=False)


class OrderAmountsSchema(Schema):
    """Schema for order amounts"""
    subtotal = fields.Decimal(as_string=False)
    shipping_fee = fields.Decimal(as_string=False)
    discount = fields.Decimal(as_string=False)
    grand_total = fields.Decimal(as_string=False)


class OrderEventSchema(BaseSchema):
    """Schema for order events"""
    event_type = fields.String(dump_only=True)
    note = fields.String(allow_none=True)


class OrderCreateSchema(Schema):
    """Schema for creating orders"""
    customer = fields.Nested(CustomerSchema, required=True)
    payment_method = fields.String(required=True, validate=validate.OneOf(['COD', 'MOMO', 'VNPAY', 'MOCK_TRANSFER']))
    items = fields.List(fields.Nested(OrderItemRequestSchema), required=True, validate=validate.Length(min=1))


class OrderResponseSchema(BaseSchema):
    """Schema for order response"""
    order_code = fields.String(dump_only=True)
    customer_name = fields.String(dump_only=True)
    phone = fields.String(dump_only=True)
    address = fields.String(dump_only=True)
    province = fields.String(dump_only=True)
    district = fields.String(dump_only=True)
    ward = fields.String(dump_only=True)
    payment_method = fields.String(dump_only=True)
    payment_status = fields.String(dump_only=True)
    status = fields.String(dump_only=True)
    transfer_confirmed = fields.Boolean(dump_only=True)
    transfer_confirmed_at = fields.DateTime(dump_only=True)
    discount_code = fields.String(dump_only=True)
    amounts = fields.Nested(OrderAmountsSchema, dump_only=True)
    items = fields.List(fields.Nested(OrderItemResponseSchema), dump_only=True)
    events = fields.List(fields.Nested(OrderEventSchema), dump_only=True)


class OrderStatusUpdateSchema(Schema):
    """Schema for updating order status"""
    status = fields.String(required=True, validate=validate.OneOf([
        'pending', 'pending_payment', 'waiting_admin_confirmation', 
        'confirmed', 'fulfilled', 'completed', 'cancelled'
    ]))


class OrderQuerySchema(PaginationSchema):
    """Schema for order query parameters"""
    status = fields.String(allow_none=True, validate=validate.OneOf([
        'pending', 'pending_payment', 'waiting_admin_confirmation',
        'confirmed', 'fulfilled', 'completed', 'cancelled'
    ]))
    q = fields.String(missing='')  # search in order_code, customer_name, phone