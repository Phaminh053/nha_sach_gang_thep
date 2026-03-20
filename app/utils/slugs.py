"""Slug generation utilities"""

import re
import unicodedata
from typing import Optional


class SlugGenerator:
    """Utility for generating URL-friendly slugs"""
    
    @staticmethod
    def slugify(text: str, max_length: int = 50) -> str:
        """Convert text to URL-friendly slug"""
        if not text:
            return ""
        
        # Normalize unicode characters
        text = unicodedata.normalize('NFKD', text)
        
        # Convert to lowercase
        text = text.lower()
        
        # Replace Vietnamese characters
        vietnamese_map = {
            'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
            'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
            'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
            'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
            'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
            'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
            'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
            'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
            'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
            'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
            'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
            'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
            'đ': 'd'
        }
        
        for vn_char, en_char in vietnamese_map.items():
            text = text.replace(vn_char, en_char)
        
        # Remove special characters and replace with hyphens
        text = re.sub(r'[^a-z0-9\s-]', '', text)
        text = re.sub(r'[\s-]+', '-', text)
        
        # Remove leading/trailing hyphens
        text = text.strip('-')
        
        # Truncate to max length
        if len(text) > max_length:
            text = text[:max_length].rstrip('-')
        
        return text
    
    @staticmethod
    def ensure_unique_slug(base_slug: str, check_function, max_attempts: int = 100) -> str:
        """Ensure slug is unique by appending numbers if necessary"""
        slug = base_slug
        counter = 1
        
        while counter <= max_attempts:
            if not check_function(slug):
                return slug
            
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        # If we can't find a unique slug after max_attempts, use timestamp
        import time
        return f"{base_slug}-{int(time.time())}"
    
    @staticmethod
    def generate_product_slug(name: str, check_function) -> str:
        """Generate unique slug for product"""
        base_slug = SlugGenerator.slugify(name)
        if not base_slug:
            base_slug = "product"
        
        return SlugGenerator.ensure_unique_slug(base_slug, check_function)
    
    @staticmethod
    def generate_category_slug(name: str, check_function) -> str:
        """Generate unique slug for category"""
        base_slug = SlugGenerator.slugify(name)
        if not base_slug:
            base_slug = "category"
        
        return SlugGenerator.ensure_unique_slug(base_slug, check_function)


# Convenience function for simple slugify
def slugify(text: str, max_length: int = 50) -> str:
    """Convenience function to slugify text"""
    return SlugGenerator.slugify(text, max_length)