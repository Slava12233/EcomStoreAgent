import os
import logging
from woocommerce import API
from dotenv import load_dotenv
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class OrderHandler:
    def __init__(self, wp_url):
        """Initialize OrderHandler with WooCommerce API credentials"""
        self.wp_url = wp_url
        
        # Initialize WooCommerce API with WooCommerce API keys
        wc_key = os.getenv('WC_CONSUMER_KEY')
        wc_secret = os.getenv('WC_CONSUMER_SECRET')
        
        if not wc_key or not wc_secret:
            raise ValueError("WooCommerce API keys not found in environment")
            
        logger.debug(f"Initializing WooCommerce API for orders with URL: {wp_url}")
        self.wcapi = API(
            url=wp_url,
            consumer_key=wc_key,
            consumer_secret=wc_secret,
            version="wc/v3",
            timeout=30
        )
    
    def create_order(self, customer_data: dict, items: list, shipping_method: str = None) -> dict:
        """
        Create a new order
        
        Args:
            customer_data: פרטי הלקוח (שם, טלפון, אימייל, כתובת)
            items: רשימת פריטים להזמנה (מזהה מוצר, כמות)
            shipping_method: שיטת משלוח (אופציונלי)
        
        Example customer_data:
        {
            "first_name": "ישראל",
            "last_name": "ישראלי",
            "email": "israel@example.com",
            "phone": "0501234567",
            "address_1": "רחוב הרצל 1",
            "city": "תל אביב",
            "postcode": "6123456"
        }
        
        Example items:
        [
            {"product_id": 123, "quantity": 2},
            {"product_id": 456, "quantity": 1}
        ]
        """
        try:
            logger.debug(f"Creating new order for customer: {customer_data.get('email')}")
            
            # Prepare order data
            order_data = {
                "status": "pending",
                "billing": {
                    "first_name": customer_data.get("first_name", ""),
                    "last_name": customer_data.get("last_name", ""),
                    "email": customer_data.get("email", ""),
                    "phone": customer_data.get("phone", ""),
                    "address_1": customer_data.get("address_1", ""),
                    "city": customer_data.get("city", ""),
                    "postcode": customer_data.get("postcode", ""),
                    "country": "IL"
                },
                "shipping": {
                    "first_name": customer_data.get("first_name", ""),
                    "last_name": customer_data.get("last_name", ""),
                    "address_1": customer_data.get("address_1", ""),
                    "city": customer_data.get("city", ""),
                    "postcode": customer_data.get("postcode", ""),
                    "country": "IL"
                },
                "line_items": items
            }
            
            # Add shipping method if specified
            if shipping_method:
                order_data["shipping_lines"] = [
                    {
                        "method_id": shipping_method,
                        "method_title": shipping_method
                    }
                ]
            
            # Create order
            response = self.wcapi.post("orders", order_data)
            
            if response.status_code != 201:
                logger.error(f"Failed to create order. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to create order: {response.text}")
            
            logger.debug("Order created successfully")
            return response.json()
            
        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            raise
    
    def list_orders(self, status: str = None, per_page: int = 10) -> list:
        """
        Get list of orders with optional filtering
        
        Args:
            status: סטטוס ההזמנות לסינון (למשל: 'processing', 'completed', 'on-hold')
            per_page: כמה הזמנות להציג בכל עמוד
        """
        try:
            logger.debug(f"Fetching orders with status: {status}, per_page: {per_page}")
            
            # Prepare parameters
            params = {"per_page": per_page}
            if status:
                params["status"] = status
            
            response = self.wcapi.get("orders", params=params)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch orders. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to fetch orders: {response.text}")
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error listing orders: {str(e)}")
            raise
    
    def get_order_details(self, order_id: int) -> dict:
        """Get detailed information about a specific order"""
        try:
            logger.debug(f"Fetching details for order ID: {order_id}")
            
            response = self.wcapi.get(f"orders/{order_id}")
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch order details. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to fetch order details: {response.text}")
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error getting order details: {str(e)}")
            raise
    
    def update_order_status(self, order_id: int, status: str) -> dict:
        """
        Update order status
        
        Args:
            order_id: מזהה ההזמנה
            status: הסטטוס החדש ('processing', 'completed', 'on-hold', etc.)
        """
        try:
            logger.debug(f"Updating status for order {order_id} to: {status}")
            
            # Validate status
            valid_statuses = ['pending', 'processing', 'on-hold', 'completed', 'cancelled', 'refunded', 'failed']
            if status not in valid_statuses:
                raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            
            response = self.wcapi.put(f"orders/{order_id}", {"status": status})
            
            if response.status_code != 200:
                logger.error(f"Failed to update order status. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to update order status: {response.text}")
            
            logger.debug("Order status updated successfully")
            return response.json()
            
        except Exception as e:
            logger.error(f"Error updating order status: {str(e)}")
            raise
    
    def search_orders(self, search_term: str = None, customer_id: int = None,
                     date_from: str = None, date_to: str = None,
                     status: str = None) -> list:
        """
        Search orders by various parameters
        
        Args:
            search_term: חיפוש חופשי בהזמנות
            customer_id: מזהה לקוח לסינון
            date_from: תאריך התחלה בפורמט YYYY-MM-DD
            date_to: תאריך סיום בפורמט YYYY-MM-DD
            status: סטטוס הזמנה לסינון
        """
        try:
            logger.debug(f"Searching orders with term: {search_term}, customer: {customer_id}, dates: {date_from}-{date_to}, status: {status}")
            
            # Prepare search parameters
            params = {}
            if search_term:
                params["search"] = search_term
            if customer_id:
                params["customer"] = customer_id
            if date_from:
                params["after"] = f"{date_from}T00:00:00"
            if date_to:
                params["before"] = f"{date_to}T23:59:59"
            if status:
                params["status"] = status
            
            response = self.wcapi.get("orders", params=params)
            
            if response.status_code != 200:
                logger.error(f"Failed to search orders. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to search orders: {response.text}")
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error searching orders: {str(e)}")
            raise
    
    def get_order_notes(self, order_id: int) -> list:
        """Get all notes for a specific order"""
        try:
            logger.debug(f"Fetching notes for order ID: {order_id}")
            
            response = self.wcapi.get(f"orders/{order_id}/notes")
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch order notes. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to fetch order notes: {response.text}")
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error getting order notes: {str(e)}")
            raise
    
    def add_order_note(self, order_id: int, note: str, is_customer_note: bool = False) -> dict:
        """
        Add a note to an order
        
        Args:
            order_id: מזהה ההזמנה
            note: תוכן ההערה
            is_customer_note: האם ההערה מיועדת ללקוח
        """
        try:
            logger.debug(f"Adding note to order {order_id}: {note}")
            
            data = {
                "note": note,
                "customer_note": is_customer_note
            }
            
            response = self.wcapi.post(f"orders/{order_id}/notes", data)
            
            if response.status_code != 201:
                logger.error(f"Failed to add order note. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to add order note: {response.text}")
            
            logger.debug("Order note added successfully")
            return response.json()
            
        except Exception as e:
            logger.error(f"Error adding order note: {str(e)}")
            raise 