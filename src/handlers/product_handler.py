import os
import logging
import requests
from typing import List, Dict, Optional
from woocommerce import API

logger = logging.getLogger(__name__)

class ProductHandler:
    """מחלקה לניהול מוצרים בחנות WooCommerce"""
    
    def __init__(self, wp_url: str):
        """אתחול המחלקה עם כתובת האתר והרשאות"""
        self.wp_url = wp_url
        
        # Initialize WooCommerce API
        wc_key = os.getenv('WC_CONSUMER_KEY')
        wc_secret = os.getenv('WC_CONSUMER_SECRET')
        
        if not wc_key or not wc_secret:
            raise ValueError("WooCommerce API keys not found in environment")
            
        logger.debug(f"Initializing WooCommerce API for products with URL: {wp_url}")
        self.wcapi = API(
            url=wp_url,
            consumer_key=wc_key,
            consumer_secret=wc_secret,
            version="wc/v3",
            timeout=30
        )
        
    def list_products(self, per_page: int = 10) -> List[Dict]:
        """קבלת רשימת המוצרים בחנות"""
        try:
            response = self.wcapi.get("products", params={"per_page": per_page})
            if response.status_code != 200:
                raise Exception(f"Failed to fetch products: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error listing products: {str(e)}")
            raise
            
    def create_product(self, name: str, description: str, regular_price: str, stock_quantity: Optional[int] = None) -> Dict:
        """יצירת מוצר חדש"""
        try:
            product_data = {
                "name": name,
                "description": description,
                "regular_price": regular_price,
                "status": "publish"
            }
            
            if stock_quantity is not None:
                product_data["manage_stock"] = True
                product_data["stock_quantity"] = stock_quantity
                
            response = self.wcapi.post("products", product_data)
            if response.status_code != 201:
                raise Exception(f"Failed to create product: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error creating product: {str(e)}")
            raise
            
    def update_product(self, product_id: int, **kwargs) -> Dict:
        """עדכון פרטי מוצר"""
        try:
            response = self.wcapi.put(f"products/{product_id}", kwargs)
            if response.status_code != 200:
                raise Exception(f"Failed to update product: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error updating product: {str(e)}")
            raise
            
    def delete_product(self, product_id: int) -> Dict:
        """מחיקת מוצר"""
        try:
            response = self.wcapi.delete(f"products/{product_id}", params={"force": True})
            if response.status_code != 200:
                raise Exception(f"Failed to delete product: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error deleting product: {str(e)}")
            raise
            
    def get_product_details(self, product_id: int) -> Dict:
        """קבלת פרטים מלאים על מוצר"""
        try:
            response = self.wcapi.get(f"products/{product_id}")
            if response.status_code != 200:
                raise Exception(f"Failed to get product: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error getting product details: {str(e)}")
            raise
            
    def search_products(self, search_term: str) -> List[Dict]:
        """חיפוש מוצרים לפי טקסט"""
        try:
            response = self.wcapi.get("products", params={"search": search_term})
            if response.status_code != 200:
                raise Exception(f"Failed to search products: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            raise
            
    def update_price(self, product_id: int, price: str, is_sale: bool = False) -> Dict:
        """עדכון מחיר מוצר"""
        try:
            update_data = {}
            if is_sale:
                update_data["sale_price"] = price
            else:
                update_data["regular_price"] = price
                
            response = self.wcapi.put(f"products/{product_id}", update_data)
            if response.status_code != 200:
                raise Exception(f"Failed to update price: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error updating price: {str(e)}")
            raise
            
    def remove_discount(self, product_id: int) -> Dict:
        """הסרת מבצע/הנחה ממוצר"""
        try:
            response = self.wcapi.put(f"products/{product_id}", {"sale_price": ""})
            if response.status_code != 200:
                raise Exception(f"Failed to remove discount: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error removing discount: {str(e)}")
            raise 