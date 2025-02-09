import os
import logging
import requests
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class CategoryHandler:
    """מחלקה לניהול קטגוריות בחנות WooCommerce"""
    
    def __init__(self, wp_url: str):
        """אתחול המחלקה עם כתובת האתר והרשאות"""
        self.wp_url = wp_url
        self.auth_params = {
            'consumer_key': os.getenv('WC_CONSUMER_KEY'),
            'consumer_secret': os.getenv('WC_CONSUMER_SECRET')
        }
        
    def list_categories(self) -> List[Dict]:
        """קבלת רשימת כל הקטגוריות בחנות"""
        try:
            response = requests.get(
                f"{self.wp_url}/wp-json/wc/v3/products/categories",
                params=self.auth_params,
                verify=False
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error listing categories: {e}")
            raise Exception(f"שגיאה בקבלת רשימת הקטגוריות: {str(e)}")
            
    def create_category(self, name: str, description: str = "", parent_id: Optional[int] = None) -> Dict:
        """יצירת קטגוריה חדשה"""
        try:
            data = {
                "name": name,
                "description": description
            }
            if parent_id:
                data["parent"] = parent_id
                
            response = requests.post(
                f"{self.wp_url}/wp-json/wc/v3/products/categories",
                params=self.auth_params,
                json=data,
                verify=False
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error creating category: {e}")
            raise Exception(f"שגיאה ביצירת הקטגוריה: {str(e)}")
            
    def update_category(self, category_id: int, **kwargs) -> Dict:
        """עדכון פרטי קטגוריה קיימת"""
        try:
            response = requests.put(
                f"{self.wp_url}/wp-json/wc/v3/products/categories/{category_id}",
                params=self.auth_params,
                json=kwargs,
                verify=False
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error updating category: {e}")
            raise Exception(f"שגיאה בעדכון הקטגוריה: {str(e)}")
            
    def delete_category(self, category_id: int) -> Dict:
        """מחיקת קטגוריה"""
        try:
            response = requests.delete(
                f"{self.wp_url}/wp-json/wc/v3/products/categories/{category_id}",
                params={**self.auth_params, "force": True},
                verify=False
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error deleting category: {e}")
            raise Exception(f"שגיאה במחיקת הקטגוריה: {str(e)}")
            
    def assign_product_to_category(self, product_id: int, category_ids: List[int]) -> Dict:
        """שיוך מוצר לקטגוריות"""
        try:
            data = {
                "categories": [{"id": cat_id} for cat_id in category_ids]
            }
            
            response = requests.put(
                f"{self.wp_url}/wp-json/wc/v3/products/{product_id}",
                params=self.auth_params,
                json=data,
                verify=False
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error assigning product to categories: {e}")
            raise Exception(f"שגיאה בשיוך המוצר לקטגוריות: {str(e)}") 