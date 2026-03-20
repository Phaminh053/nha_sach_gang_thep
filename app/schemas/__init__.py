"""Marshmallow schemas for request/response validation"""

from marshmallow import Schema, fields, validate, validates, ValidationError
from app.extensions import ma


class BaseSchema(ma.Schema):
    """Base schema with common fields"""
    id = fields.Integer(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class PaginationSchema(Schema):
    """Schema for pagination parameters"""
    page = fields.Integer(missing=1, validate=validate.Range(min=1))
    page_size = fields.Integer(missing=24, validate=validate.Range(min=1, max=100))


class MetaSchema(Schema):
    """Schema for metadata in paginated responses"""
    page = fields.Integer()
    page_size = fields.Integer()
    total = fields.Integer()
    pages = fields.Integer()