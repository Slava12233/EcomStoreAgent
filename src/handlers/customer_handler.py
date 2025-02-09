import os
import logging
import requests
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class CustomerHandler:
    """מחלקה לניהול לקוחות בחנות WooCommerce"""
    
    def __init__(self, wp_url: str):
        """אתחול המחלקה עם כתובת האתר והרשאות"""
        self.wp_url = wp_url
        self.auth_params = {
            'consumer_key': os.getenv('WC_CONSUMER_KEY'),
            'consumer_secret': os.getenv('WC_CONSUMER_SECRET')
        }
        
    def list_customers(self, page: int = 1, per_page: int = 10) -> List[Dict]:
        """קבלת רשימת כל הלקוחות בחנות"""
        try:
            response = requests.get(
                f"{self.wp_url}/wp-json/wc/v3/customers",
                params={**self.auth_params, "page": page, "per_page": per_page},
                verify=False
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error listing customers: {e}")
            raise Exception(f"שגיאה בקבלת רשימת הלקוחות: {str(e)}")
            
    def get_customer_details(self, customer_id: int) -> Dict:
        """קבלת פרטים מלאים על לקוח ספציפי"""
        try:
            response = requests.get(
                f"{self.wp_url}/wp-json/wc/v3/customers/{customer_id}",
                params=self.auth_params,
                verify=False
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting customer details: {e}")
            raise Exception(f"שגיאה בקבלת פרטי הלקוח: {str(e)}")
            
    def update_customer(self, customer_id: int, **kwargs) -> Dict:
        """עדכון פרטי לקוח"""
        try:
            response = requests.put(
                f"{self.wp_url}/wp-json/wc/v3/customers/{customer_id}",
                params=self.auth_params,
                json=kwargs,
                verify=False
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error updating customer: {e}")
            raise Exception(f"שגיאה בעדכון פרטי הלקוח: {str(e)}")
            
    def search_customers(self, search: str) -> List[Dict]:
        """חיפוש לקוחות לפי טקסט חופשי"""
        try:
            response = requests.get(
                f"{self.wp_url}/wp-json/wc/v3/customers",
                params={**self.auth_params, "search": search},
                verify=False
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error searching customers: {e}")
            raise Exception(f"שגיאה בחיפוש לקוחות: {str(e)}")
            
    def get_customer_orders(self, customer_id: int) -> List[Dict]:
        """קבלת רשימת ההזמנות של לקוח ספציפי"""
        try:
            response = requests.get(
                f"{self.wp_url}/wp-json/wc/v3/orders",
                params={**self.auth_params, "customer": customer_id},
                verify=False
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting customer orders: {e}")
            raise Exception(f"שגיאה בקבלת הזמנות הלקוח: {str(e)}")
            
    def get_customer_total_spent(self, customer_id: int) -> float:
        """חישוב סך כל הרכישות של לקוח"""
        try:
            orders = self.get_customer_orders(customer_id)
            total = sum(float(order['total']) for order in orders if order['status'] == 'completed')
            return total
        except Exception as e:
            logger.error(f"Error calculating customer total spent: {e}")
            raise Exception(f"שגיאה בחישוב סך הרכישות: {str(e)}")
            
    def create_customer(self, first_name: str, last_name: str, email: str, **kwargs) -> Dict:
        """יצירת לקוח חדש"""
        try:
            data = {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "username": email,  # נדרש ע"י WooCommerce
                "role": "customer"  # נדרש ע"י WooCommerce
            }
            
            # אם יש פרטי חיוב, נארגן אותם במבנה הנכון
            if any(k.startswith('billing_') for k in kwargs):
                billing = {}
                for k, v in dict(kwargs).items():
                    if k.startswith('billing_'):
                        billing_key = k.replace('billing_', '')
                        billing[billing_key] = v
                        del kwargs[k]
                data['billing'] = billing
            
            # הוספת שאר הפרמטרים
            data.update({k: v for k, v in kwargs.items() if not k.startswith('billing_')})
            
            logger.info(f"Creating customer with data: {data}")
            
            response = requests.post(
                f"{self.wp_url}/wp-json/wc/v3/customers",
                params=self.auth_params,
                json=data,
                verify=False
            )
            
            if response.status_code != 201:
                logger.error(f"Error response from WooCommerce: {response.status_code} - {response.text}")
                error_data = response.json() if response.text else {}
                if 'message' in error_data:
                    raise Exception(f"שגיאה מ-WooCommerce: {error_data['message']}")
                raise Exception(f"שגיאה ביצירת הלקוח: {response.status_code} - {response.text}")
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error creating customer: {e}")
            raise Exception(f"שגיאת רשת ביצירת הלקוח: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating customer: {e}")
            raise Exception(f"שגיאה ביצירת הלקוח: {str(e)}") 