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

class CouponHandler:
    def __init__(self, wp_url):
        """Initialize CouponHandler with WooCommerce API credentials"""
        self.wp_url = wp_url
        
        # Initialize WooCommerce API with WooCommerce API keys
        wc_key = os.getenv('WC_CONSUMER_KEY')
        wc_secret = os.getenv('WC_CONSUMER_SECRET')
        
        if not wc_key or not wc_secret:
            raise ValueError("WooCommerce API keys not found in environment")
            
        logger.debug(f"Initializing WooCommerce API for coupons with URL: {wp_url}")
        self.wcapi = API(
            url=wp_url,
            consumer_key=wc_key,
            consumer_secret=wc_secret,
            version="wc/v3",
            timeout=30
        )
    
    def create_coupon(self, code: str, discount_type: str, amount: float, description: str = None,
                     expiry_date: str = None, min_amount: float = None, max_amount: float = None,
                     individual_use: bool = True, exclude_sale_items: bool = False) -> dict:
        """
        Create a new coupon
        
        Args:
            code: קוד הקופון (חובה)
            discount_type: סוג ההנחה ('percent' או 'fixed_cart')
            amount: גובה ההנחה (באחוזים או בשקלים)
            description: תיאור הקופון (אופציונלי)
            expiry_date: תאריך תפוגה בפורמט YYYY-MM-DD (אופציונלי)
            min_amount: סכום מינימלי להזמנה (אופציונלי)
            max_amount: סכום מקסימלי להנחה (אופציונלי)
            individual_use: האם ניתן להשתמש רק בקופון זה
            exclude_sale_items: האם לא תקף על פריטים במבצע
        """
        try:
            logger.debug(f"Creating new coupon with code: {code}")
            
            # Prepare coupon data
            coupon_data = {
                "code": code,
                "discount_type": discount_type,
                "amount": str(amount),
                "individual_use": individual_use,
                "exclude_sale_items": exclude_sale_items
            }
            
            # Add optional fields
            if description:
                coupon_data["description"] = description
            if expiry_date:
                coupon_data["date_expires"] = f"{expiry_date}T23:59:59"
            if min_amount:
                coupon_data["minimum_amount"] = str(min_amount)
            if max_amount:
                coupon_data["maximum_amount"] = str(max_amount)
            
            # Create coupon
            response = self.wcapi.post("coupons", coupon_data)
            
            if response.status_code != 201:
                logger.error(f"Failed to create coupon. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to create coupon: {response.text}")
            
            logger.debug("Coupon created successfully")
            return response.json()
            
        except Exception as e:
            logger.error(f"Error creating coupon: {str(e)}")
            raise
    
    def list_coupons(self) -> list:
        """Get list of all coupons"""
        try:
            logger.debug("Fetching list of coupons")
            
            response = self.wcapi.get("coupons")
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch coupons. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to fetch coupons: {response.text}")
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error listing coupons: {str(e)}")
            raise
    
    def get_coupon_details(self, coupon_id: int) -> dict:
        """Get detailed information about a specific coupon"""
        try:
            logger.debug(f"Fetching details for coupon ID: {coupon_id}")
            
            response = self.wcapi.get(f"coupons/{coupon_id}")
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch coupon details. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to fetch coupon details: {response.text}")
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error getting coupon details: {str(e)}")
            raise
    
    def edit_coupon(self, coupon_id: int, **kwargs) -> dict:
        """
        Edit an existing coupon
        
        Args:
            coupon_id: מזהה הקופון
            **kwargs: שדות לעדכון (code, amount, description, וכו')
        """
        try:
            logger.debug(f"Updating coupon ID: {coupon_id}")
            
            # Convert numeric values to strings for the API
            if 'amount' in kwargs:
                kwargs['amount'] = str(kwargs['amount'])
            if 'minimum_amount' in kwargs:
                kwargs['minimum_amount'] = str(kwargs['minimum_amount'])
            if 'maximum_amount' in kwargs:
                kwargs['maximum_amount'] = str(kwargs['maximum_amount'])
            
            response = self.wcapi.put(f"coupons/{coupon_id}", kwargs)
            
            if response.status_code != 200:
                logger.error(f"Failed to update coupon. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to update coupon: {response.text}")
            
            logger.debug("Coupon updated successfully")
            return response.json()
            
        except Exception as e:
            logger.error(f"Error updating coupon: {str(e)}")
            raise
    
    def delete_coupon(self, coupon_id: int, force: bool = True) -> dict:
        """Delete a coupon"""
        try:
            logger.debug(f"Deleting coupon ID: {coupon_id}")
            
            response = self.wcapi.delete(f"coupons/{coupon_id}", params={"force": force})
            
            if response.status_code != 200:
                logger.error(f"Failed to delete coupon. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to delete coupon: {response.text}")
            
            logger.debug("Coupon deleted successfully")
            return response.json()
            
        except Exception as e:
            logger.error(f"Error deleting coupon: {str(e)}")
            raise
    
    def search_coupons(self, search_term: str) -> list:
        """Search for coupons by code or description"""
        try:
            logger.debug(f"Searching for coupons with term: {search_term}")
            
            response = self.wcapi.get("coupons", params={"search": search_term})
            
            if response.status_code != 200:
                logger.error(f"Failed to search coupons. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to search coupons: {response.text}")
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error searching coupons: {str(e)}")
            raise 