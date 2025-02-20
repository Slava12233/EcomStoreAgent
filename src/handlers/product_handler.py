import os
import logging
import requests
from typing import List, Dict, Optional
from woocommerce import API

# הגדרת לוגר ייעודי לקריאות API
api_logger = logging.getLogger('api_calls')
api_logger.setLevel(logging.DEBUG)

# הגדרת handler לקובץ
api_handler = logging.FileHandler('logs/api.log', encoding='utf-8')
api_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
api_logger.addHandler(api_handler)

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
            api_logger.info(f"Fetching products list (per_page={per_page})")
            response = self.wcapi.get("products", params={"per_page": per_page})
            api_logger.info(f"Products list response: {response.status_code}")
            api_logger.debug(f"Products list response body: {response.text}")
            
            if response.status_code != 200:
                api_logger.error(f"Failed to fetch products: {response.text}")
                raise Exception(f"Failed to fetch products: {response.text}")
            return response.json()
        except Exception as e:
            api_logger.error(f"Error listing products: {str(e)}")
            raise
            
    def create_product(self, name: str, description: str, regular_price: str, stock_quantity: Optional[int] = None) -> Dict:
        """יצירת מוצר חדש"""
        try:
            # בדיקת חיבור בסיסי
            api_logger.info("=== Starting Basic Connection Test ===")
            test_response = self.wcapi.get("")
            api_logger.info(f"Basic Connection Test Response: {test_response.status_code}")
            api_logger.debug(f"Basic Connection Response Body: {test_response.text}")
            
            # בדיקת הרשאות
            api_logger.info("=== Testing API Permissions ===")
            api_logger.info(f"Using URL: {self.wp_url}")
            api_logger.info(f"Using Consumer Key: {os.getenv('WC_CONSUMER_KEY')}")
            api_logger.info(f"Using Consumer Secret: {os.getenv('WC_CONSUMER_SECRET')}")
            
            # בדיקת רשימת מוצרים קיימת
            api_logger.info("=== Testing Products List ===")
            products_response = self.wcapi.get("products")
            api_logger.info(f"Products List Response: {products_response.status_code}")
            api_logger.debug(f"Products List Body: {products_response.text}")
            
            # וידוא שכל השדות הנדרשים קיימים
            if not name or not regular_price:
                api_logger.error("Missing required fields")
                raise ValueError("נדרש לפחות שם מוצר ומחיר")
            
            # יצירת מוצר בסיסי לבדיקה
            test_data = {
                "name": name,
                "type": "simple",
                "regular_price": str(regular_price),
                "description": description,
                "manage_stock": True if stock_quantity is not None else False,
                "stock_quantity": stock_quantity if stock_quantity is not None else None,
                "status": "publish"
            }
            
            api_logger.info("=== Creating Basic Product ===")
            api_logger.info(f"Product Data: {test_data}")
            
            # ניסיון יצירת מוצר
            response = self.wcapi.post("products", test_data)
            
            api_logger.info(f"Create Product Response Code: {response.status_code}")
            api_logger.info(f"Create Product Headers: {dict(response.headers)}")
            api_logger.debug(f"Create Product Response Body: {response.text}")
            
            if response.status_code != 201:
                api_logger.error("=== Product Creation Failed ===")
                api_logger.error(f"Status Code: {response.status_code}")
                api_logger.error(f"Error: {response.text}")
                raise Exception(f"Failed to create product: {response.text}")
            
            product = response.json()
            api_logger.info("=== Product Creation Successful ===")
            api_logger.info(f"Product ID: {product.get('id')}")
            api_logger.debug(f"Full Product Data: {product}")
            
            return product
            
        except ValueError as ve:
            api_logger.error("=== Product Creation Value Error ===")
            api_logger.error(f"Error Type: ValueError")
            api_logger.error(f"Error Message: {str(ve)}")
            raise
            
        except Exception as e:
            api_logger.error("=== Product Creation Error ===")
            api_logger.error(f"Error Type: {type(e)}")
            api_logger.error(f"Error Message: {str(e)}")
            api_logger.error("Stack Trace:", exc_info=True)
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