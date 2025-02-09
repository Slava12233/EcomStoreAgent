import os
import logging
from typing import List, Dict, Optional
from woocommerce import API
from datetime import datetime
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class InventoryHandler:
    """מחלקה לניהול מלאי מתקדם בחנות WooCommerce"""
    
    def __init__(self, wp_url: str):
        """אתחול המחלקה עם כתובת האתר והרשאות"""
        self.wp_url = wp_url
        
        # Initialize WooCommerce API
        wc_key = os.getenv('WC_CONSUMER_KEY')
        wc_secret = os.getenv('WC_CONSUMER_SECRET')
        
        if not wc_key or not wc_secret:
            raise ValueError("WooCommerce API keys not found in environment")
            
        logger.debug(f"Initializing WooCommerce API for inventory with URL: {wp_url}")
        self.wcapi = API(
            url=wp_url,
            consumer_key=wc_key,
            consumer_secret=wc_secret,
            version="wc/v3",
            timeout=30
        )
        
    def get_low_stock_products(self, threshold: int = 5) -> List[Dict]:
        """קבלת רשימת מוצרים עם מלאי נמוך"""
        try:
            logger.debug(f"Fetching products with stock below {threshold}")
            
            # Get all products that have stock management enabled
            response = self.wcapi.get("products", params={
                "per_page": 100,
                "stock_status": "instock",
                "manage_stock": True
            })
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch products. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to fetch products: {response.text}")
            
            products = response.json()
            
            # Filter products with low stock
            low_stock = [
                product for product in products
                if product.get('manage_stock', False) 
                and product.get('stock_quantity', 0) <= threshold
            ]
            
            logger.debug(f"Found {len(low_stock)} products with low stock")
            return low_stock
            
        except Exception as e:
            logger.error(f"Error getting low stock products: {str(e)}")
            raise
            
    def update_stock_quantity(self, product_id: int, quantity: int, operation: str = 'set') -> Dict:
        """
        עדכון כמות מלאי למוצר
        
        Args:
            product_id: מזהה המוצר
            quantity: הכמות לעדכון
            operation: סוג הפעולה ('set' - קביעת כמות, 'add' - הוספה, 'subtract' - הפחתה)
        """
        try:
            logger.debug(f"Updating stock for product {product_id}, operation: {operation}, quantity: {quantity}")
            
            # Get current stock
            response = self.wcapi.get(f"products/{product_id}")
            if response.status_code != 200:
                raise Exception(f"Failed to get product: {response.text}")
            
            product = response.json()
            current_stock = product.get('stock_quantity', 0)
            
            # Calculate new stock based on operation
            if operation == 'set':
                new_stock = quantity
            elif operation == 'add':
                new_stock = current_stock + quantity
            elif operation == 'subtract':
                new_stock = current_stock - quantity
            else:
                raise ValueError("Invalid operation. Must be 'set', 'add', or 'subtract'")
            
            # Update product stock
            update_data = {
                "manage_stock": True,
                "stock_quantity": new_stock
            }
            
            response = self.wcapi.put(f"products/{product_id}", update_data)
            if response.status_code != 200:
                raise Exception(f"Failed to update stock: {response.text}")
            
            logger.debug(f"Stock updated successfully. New stock: {new_stock}")
            return response.json()
            
        except Exception as e:
            logger.error(f"Error updating stock quantity: {str(e)}")
            raise
            
    def get_stock_status(self, product_id: int) -> Dict:
        """קבלת סטטוס מלאי מפורט למוצר"""
        try:
            logger.debug(f"Getting stock status for product {product_id}")
            
            response = self.wcapi.get(f"products/{product_id}")
            if response.status_code != 200:
                raise Exception(f"Failed to get product: {response.text}")
            
            product = response.json()
            
            return {
                "product_id": product_id,
                "name": product.get('name'),
                "manage_stock": product.get('manage_stock', False),
                "stock_quantity": product.get('stock_quantity', 0),
                "stock_status": product.get('stock_status', 'instock'),
                "backorders_allowed": product.get('backorders_allowed', False),
                "low_stock_amount": product.get('low_stock_amount', None)
            }
            
        except Exception as e:
            logger.error(f"Error getting stock status: {str(e)}")
            raise
            
    def manage_stock_by_attributes(self, product_id: int, attributes: Dict[str, Dict[str, int]]) -> Dict:
        """
        ניהול מלאי לפי מאפיינים (למשל: צבע, מידה)
        
        Args:
            product_id: מזהה המוצר
            attributes: מילון של מאפיינים וכמויות, למשל:
                {
                    "color": {
                        "red": 5,
                        "blue": 3
                    },
                    "size": {
                        "S": 2,
                        "M": 4,
                        "L": 1
                    }
                }
        """
        try:
            logger.debug(f"Managing stock by attributes for product {product_id}")
            
            # Get current product data
            response = self.wcapi.get(f"products/{product_id}")
            if response.status_code != 200:
                raise Exception(f"Failed to get product: {response.text}")
            
            product = response.json()
            
            # Update or create variations based on attributes
            variations = []
            for attr_name, attr_values in attributes.items():
                for value, quantity in attr_values.items():
                    variation_data = {
                        "manage_stock": True,
                        "stock_quantity": quantity,
                        "attributes": [
                            {
                                "name": attr_name,
                                "option": value
                            }
                        ]
                    }
                    variations.append(variation_data)
            
            # Create/update variations
            for variation in variations:
                response = self.wcapi.post(f"products/{product_id}/variations", variation)
                if response.status_code not in [200, 201]:
                    raise Exception(f"Failed to create/update variation: {response.text}")
            
            logger.debug(f"Successfully updated stock for all variations")
            return {"status": "success", "variations_updated": len(variations)}
            
        except Exception as e:
            logger.error(f"Error managing stock by attributes: {str(e)}")
            raise
            
    def set_low_stock_threshold(self, product_id: int, threshold: int) -> Dict:
        """הגדרת סף התראה למלאי נמוך"""
        try:
            logger.debug(f"Setting low stock threshold for product {product_id} to {threshold}")
            
            update_data = {
                "manage_stock": True,
                "low_stock_amount": threshold
            }
            
            response = self.wcapi.put(f"products/{product_id}", update_data)
            if response.status_code != 200:
                raise Exception(f"Failed to set threshold: {response.text}")
            
            logger.debug("Low stock threshold updated successfully")
            return response.json()
            
        except Exception as e:
            logger.error(f"Error setting low stock threshold: {str(e)}")
            raise 