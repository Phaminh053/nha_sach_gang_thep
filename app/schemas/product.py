"""Product schemas for validation and serialization"""

from marshmallow import Schema, fields, validate, validates, ValidationError
from app.schemas import BaseSchema, PaginationSchema


class ProductImageSchema(BaseSchema):
    """Schema for product images"""
    image_url = fields.Url(required=True)
    alt = fields.String(allow_none=True)
    sort_order = fields.Integer(missing=0)


class ProductStockSchema(Schema):
    """Schema for product stock"""
    qty_on_hand = fields.Integer(required=True, validate=validate.Range(min=0))
    in_stock = fields.Boolean(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class ProductRatingSchema(Schema):
    """Schema for product rating"""
    avg = fields.Float(dump_only=True, attribute='avg_rating')
    count = fields.Integer(dump_only=True, attribute='review_count')


class ProductListSchema(BaseSchema):
    """Schema for product list (catalog)"""
    name = fields.String(required=True)
    slug = fields.String(dump_only=True)
    price = fields.Decimal(as_string=False, dump_only=True)
    effective_price = fields.Decimal(as_string=False, dump_only=True)
    image_url = fields.Url(allow_none=True)
    in_stock = fields.Boolean(dump_only=True)
    rating = fields.Nested(ProductRatingSchema, dump_only=True)


class ProductDetailSchema(BaseSchema):
    """Schema for product detail"""
    name = fields.String(required=True)
    slug = fields.String(dump_only=True)
    short_desc = fields.String(allow_none=True)
    price = fields.Decimal(as_string=False, required=True)
    original_price = fields.Decimal(as_string=False, dump_only=True, attribute='price')
    sale_price = fields.Decimal(as_string=False, allow_none=True)
    sale_start = fields.DateTime(allow_none=True)
    sale_end = fields.DateTime(allow_none=True)
    effective_price = fields.Decimal(as_string=False, dump_only=True)
    image_url = fields.Url(allow_none=True)
    is_active = fields.Boolean(missing=True)
    
    # Book specific fields
    isbn13 = fields.String(allow_none=True)
    sku = fields.String(allow_none=True)
    authors = fields.String(allow_none=True)
    translators = fields.String(allow_none=True)
    illustrators = fields.String(allow_none=True)
    publisher_name = fields.String(allow_none=True)
    publish_year = fields.Integer(allow_none=True)
    pages = fields.Integer(allow_none=True)
    dimensions_raw = fields.String(allow_none=True)
    width_cm = fields.Decimal(as_string=False, allow_none=True)
    height_cm = fields.Decimal(as_string=False, allow_none=True)
    thickness_mm = fields.Decimal(as_string=False, allow_none=True)
    age_min = fields.Integer(allow_none=True)
    age_max = fields.Integer(allow_none=True)
    stock = fields.Nested(ProductStockSchema, dump_only=True)
    rating = fields.Nested(ProductRatingSchema, dump_only=True)
    images = fields.List(fields.String(), dump_only=True)  # List of image URLs


class ProductCreateSchema(Schema):
    """Schema for creating products"""
    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    short_desc = fields.String(allow_none=True)
    price = fields.Decimal(required=True, validate=validate.Range(min=0))
    sale_price = fields.Decimal(allow_none=True, validate=validate.Range(min=0))
    sale_start = fields.DateTime(allow_none=True)
    sale_end = fields.DateTime(allow_none=True)
    image_url = fields.Url(allow_none=True)
    category_ids = fields.List(fields.Integer(), missing=[])
    
    # Book specific fields
    isbn13 = fields.String(allow_none=True, validate=validate.Length(max=20))
    sku = fields.String(allow_none=True, validate=validate.Length(max=64))
    authors = fields.String(allow_none=True, validate=validate.Length(max=512))
    translators = fields.String(allow_none=True, validate=validate.Length(max=512))
    illustrators = fields.String(allow_none=True, validate=validate.Length(max=512))
    publisher_name = fields.String(allow_none=True, validate=validate.Length(max=255))
    publish_year = fields.Integer(allow_none=True, validate=validate.Range(min=1000, max=2100))
    pages = fields.Integer(allow_none=True, validate=validate.Range(min=1))
    dimensions_raw = fields.String(allow_none=True, validate=validate.Length(max=64))
    width_cm = fields.Decimal(allow_none=True, validate=validate.Range(min=0))
    height_cm = fields.Decimal(allow_none=True, validate=validate.Range(min=0))
    thickness_mm = fields.Decimal(allow_none=True, validate=validate.Range(min=0))
    age_min = fields.Integer(allow_none=True, validate=validate.Range(min=0, max=100))
    age_max = fields.Integer(allow_none=True, validate=validate.Range(min=0, max=100))
    
    @validates('sale_price')
    def validate_sale_price(self, value):
        if value is not None and 'price' in self.context:
            if value >= self.context['price']:
                raise ValidationError('Sale price must be less than regular price')


class ProductUpdateSchema(ProductCreateSchema):
    """Schema for updating products"""
    name = fields.String(validate=validate.Length(min=1, max=255))
    price = fields.Decimal(validate=validate.Range(min=0))


class ProductQuerySchema(PaginationSchema):
    """Schema for product search/filter parameters"""
    q = fields.String(missing='')  # search query
    category = fields.String(allow_none=True)  # category slug or id
    price_min = fields.Decimal(allow_none=True, validate=validate.Range(min=0))
    price_max = fields.Decimal(allow_none=True, validate=validate.Range(min=0))
    sort = fields.String(missing='newest', validate=validate.OneOf([
        'price_asc', 'price_desc', 'newest', 'oldest', 'name_asc', 'name_desc'
    ]))
    
    @validates('price_max')
    def validate_price_range(self, value):
        if value is not None and 'price_min' in self.context:
            price_min = self.context.get('price_min')
            if price_min is not None and value < price_min:
                raise ValidationError('price_max must be greater than price_min')


class ProductSaleSchema(Schema):
    """Schema for setting product sale"""
    sale_price = fields.Decimal(required=True, validate=validate.Range(min=0))
    sale_start = fields.DateTime(allow_none=True)
    sale_end = fields.DateTime(allow_none=True)
    
    @validates('sale_end')
    def validate_sale_period(self, value):
        if value is not None and 'sale_start' in self.context:
            sale_start = self.context.get('sale_start')
            if sale_start is not None and value <= sale_start:
                raise ValidationError('sale_end must be after sale_start')