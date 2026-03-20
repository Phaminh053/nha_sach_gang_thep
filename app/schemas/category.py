"""Category schemas"""

from marshmallow import Schema, fields, validate
from app.schemas import BaseSchema


class CategorySchema(BaseSchema):
    """Schema for categories"""
    parent_id = fields.Integer(allow_none=True)
    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    slug = fields.String(dump_only=True)
    children = fields.List(fields.Nested('self'), dump_only=True)


class CategoryCreateSchema(Schema):
    """Schema for creating categories"""
    parent_id = fields.Integer(allow_none=True)
    name = fields.String(required=True, validate=validate.Length(min=1, max=255))