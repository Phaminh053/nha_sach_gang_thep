"""Review schemas for validation and serialization"""

from marshmallow import Schema, fields, validate, validates, ValidationError
from app.schemas import BaseSchema, PaginationSchema


class ProductReviewSchema(BaseSchema):
    """Schema for product reviews"""
    product_id = fields.Integer(dump_only=True)
    user_name = fields.String(allow_none=True, validate=validate.Length(max=100))
    rating = fields.Integer(required=True, validate=validate.Range(min=1, max=5))
    content = fields.String(allow_none=True, validate=validate.Length(min=5, max=1000))


class ReviewCreateSchema(Schema):
    """Schema for creating reviews"""
    user_name = fields.String(allow_none=True, validate=validate.Length(min=2, max=100))
    rating = fields.Integer(required=True, validate=validate.Range(min=1, max=5))
    content = fields.String(required=True, validate=validate.Length(min=5, max=1000))


class ReviewQuerySchema(PaginationSchema):
    """Schema for review query parameters"""
    product_id = fields.Integer(allow_none=True)