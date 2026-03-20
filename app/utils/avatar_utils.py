"""
Avatar utilities for user avatar generation
"""

def get_default_avatar_icon(user_id, username=None):
    """
    Get a default avatar icon based on user ID and username
    Returns an appropriate Font Awesome icon class
    """
    # Always return a nice user circle icon instead of random
    return 'fas fa-user-circle'


def get_default_avatar_color(user_id, username=None):
    """
    Get a default avatar background color based on user ID
    Returns a CSS class for background color
    """
    # Color palette without orange variants - only nice blues, greens, purples
    colors = [
        'bg-primary',       # Blue
        'bg-success',       # Green
        'bg-info',          # Light blue
        'bg-secondary',     # Gray
        'bg-dark',          # Dark
        'bg-purple',        # Purple gradient
        'bg-teal',          # Teal gradient
        'bg-pink',          # Pink gradient
        'bg-indigo',        # Indigo gradient
        'bg-gradient-1',    # Custom gradient 1 (purple)
        'bg-gradient-3',    # Custom gradient 3 (blue-teal)
    ]
    
    # Use user ID to pick a consistent color
    color_index = user_id % len(colors)
    return colors[color_index]


def get_avatar_initials(full_name=None, username=None):
    """
    Get user initials for text-based avatars
    """
    if full_name and full_name.strip():
        # Get initials from full name
        words = full_name.strip().split()
        if len(words) >= 2:
            return (words[0][0] + words[-1][0]).upper()
        elif len(words) == 1:
            return words[0][:2].upper()
    
    # Fallback to username
    if username and username.strip():
        username = username.strip()
        if len(username) >= 2:
            return username[:2].upper()
        else:
            return username.upper()
    
    return "U"  # Ultimate fallback


def get_user_avatar_data(user):
    """
    Get complete avatar data for a user
    Returns dict with icon, color, and initials
    """
    return {
        'icon': get_default_avatar_icon(user.id, user.username),
        'color': get_default_avatar_color(user.id, user.username),
        'initials': get_avatar_initials(user.full_name, user.username),
        'has_custom_avatar': bool(user.avatar_url)
    }