"""
Handlers module for WordPress AI Agent.
Contains handlers for different aspects of the WooCommerce store management.
"""

from .media_handler import MediaHandler
from .coupon_handler import CouponHandler
from .order_handler import OrderHandler
from .category_handler import CategoryHandler
from .customer_handler import CustomerHandler
from .inventory_handler import InventoryHandler
from .product_handler import ProductHandler
from .settings_handler import SettingsHandler

__all__ = [
    'MediaHandler',
    'CouponHandler',
    'OrderHandler',
    'CategoryHandler',
    'CustomerHandler',
    'InventoryHandler',
    'ProductHandler',
    'SettingsHandler'
] 