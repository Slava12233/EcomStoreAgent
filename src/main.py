import os
import json
import logging
import requests
import pytz
import asyncio
import warnings
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from handlers.media_handler import MediaHandler
from dotenv import load_dotenv
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain.agents import AgentType, Tool, initialize_agent
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import SystemMessage
import re
from handlers.coupon_handler import CouponHandler
from handlers.order_handler import OrderHandler
from langchain.callbacks.base import BaseCallbackHandler

# השתקת אזהרות
warnings.filterwarnings("ignore")
# השתקת אזהרות ספציפיות של urllib3
import urllib3
urllib3.disable_warnings()

# יצירת תיקיית לוגים אם לא קיימת
os.makedirs('logs', exist_ok=True)

# הגדרת לוגר ראשי
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# הסרת כל ההנדלרים הקיימים
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# הגדרת StreamHandler לשלוח רק שגיאות קריטיות לטרמינל
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.CRITICAL)
console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logger.addHandler(console_handler)

# הוספת הנדלר לקובץ עבור כל הלוגים
log_file_path = os.path.join(os.path.dirname(__file__), 'logs', 'bot.log')
file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8', delay=False)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# הגדרת לוגר ספציפי ל-python-telegram-bot
telegram_logger = logging.getLogger('telegram')
telegram_logger.setLevel(logging.INFO)
telegram_logger.addHandler(file_handler)
telegram_logger.propagate = False  # מניעת העברת לוגים למעלה בהיררכיה

# הגדרת לוגר ספציפי ל-LangChain
langchain_logger = logging.getLogger('langchain')
langchain_logger.setLevel(logging.WARNING)  # רק אזהרות חשובות
langchain_logger.addHandler(file_handler)
langchain_logger.propagate = False

# הגדרת לוגר ספציפי ל-urllib3
urllib3_logger = logging.getLogger('urllib3')
urllib3_logger.setLevel(logging.WARNING)  # רק אזהרות חשובות
urllib3_logger.addHandler(file_handler)
urllib3_logger.propagate = False

# Add initial log entry to verify logging is working
current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
logger.info("="*50)
logger.info(f"Bot Started at {current_time}")
logger.info(f"Log file location: {log_file_path}")
logger.info("="*50)

# Load environment variables
load_dotenv()
logger.debug("Environment variables loaded")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
logger.debug(f"Bot token loaded: {TELEGRAM_BOT_TOKEN[:10]}...")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in .env file")

WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASSWORD = os.getenv("WP_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([WP_URL, WP_USER, WP_PASSWORD, OPENAI_API_KEY]):
    raise ValueError("Missing required environment variables")

# Initialize MediaHandler
media_handler = MediaHandler(WP_URL, WP_USER, WP_PASSWORD)
coupon_handler = CouponHandler(WP_URL)
order_handler = OrderHandler(WP_URL)

# Set timezone
timezone = pytz.timezone('Asia/Jerusalem')

# Store temporary product creation state
product_creation_state = {}

def list_products(_: str = "") -> str:
    """Get list of products from WordPress"""
    try:
        auth_params = {
            'consumer_key': os.getenv('WC_CONSUMER_KEY'),
            'consumer_secret': os.getenv('WC_CONSUMER_SECRET')
        }
        
        response = requests.get(
            f"{WP_URL}/wp-json/wc/v3/products",
            params={**auth_params, "per_page": 10},
            verify=False
        )
        response.raise_for_status()
        products = response.json()
        
        if not products:
            return "לא נמצאו מוצרים בחנות"
            
        products_text = []
        for p in products:
            product_line = f"- {p['name']}: ₪{p.get('price', 'לא זמין')}"
            
            # Add stock information
            if p.get('manage_stock'):
                stock = p.get('stock_quantity', 0)
                status = "במלאי" if stock > 0 else "אזל מהמלאי"
                product_line += f" | {status} ({stock} יחידות)"
            else:
                status = "במלאי" if p.get('in_stock', True) else "אזל מהמלאי"
                product_line += f" | {status}"
                
            products_text.append(product_line)
            
        return f"המוצרים בחנות:\n" + "\n".join(products_text)
        
    except Exception as e:
        logger.error(f"Error listing products: {e}")
        return f"שגיאה בהצגת המוצרים: {str(e)}"

def update_price(product_info: str) -> str:
    """Update product price in WordPress"""
    try:
        # Parse product info - can be either "product_name new_price" or "product_name -X%"
        parts = product_info.strip().split()
        if len(parts) < 2:
            return "נדרש שם מוצר ומחיר חדש או אחוז שינוי"
            
        # Get product name (everything except the last part)
        product_name = " ".join(parts[:-1])
        price_info = parts[-1]
        
        # Check if it's a percentage change
        percentage_match = re.match(r'^-?(\d+)%$', price_info)
        
        auth_params = {
            'consumer_key': os.getenv('WC_CONSUMER_KEY'),
            'consumer_secret': os.getenv('WC_CONSUMER_SECRET')
        }
        
        # Search for product
        search_response = requests.get(
            f"{WP_URL}/wp-json/wc/v3/products",
            params={**auth_params, "search": product_name},
            verify=False
        )
        search_response.raise_for_status()
        products = search_response.json()
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product = products[0]
        product_id = product["id"]
        current_price = float(product.get("price", 0))
        
        # Calculate new price
        if percentage_match:
            percentage = float(percentage_match.group(1))
            new_price = current_price * (1 - percentage/100)
        else:
            # Try to extract direct price
            price_match = re.search(r'(\d+)(?:\s*שקלים|\s*ש"ח|\s*₪)?$', price_info)
            if not price_match:
                return "לא צוין מחיר תקין"
            new_price = float(price_match.group(1))
        
        # Update product
        update_data = {
            "regular_price": str(new_price)
        }
        
        response = requests.put(
            f"{WP_URL}/wp-json/wc/v3/products/{product_id}",
            params=auth_params,
            json=update_data,
            verify=False
        )
        response.raise_for_status()
        
        return f"המחיר של {product_name} עודכן בהצלחה ל-₪{new_price:.2f}"
        
    except Exception as e:
        logger.error(f"Error updating price: {e}")
        return f"שגיאה בעדכון המחיר: {str(e)}"

def remove_discount(product_name: str) -> str:
    """Remove discount from a product"""
    try:
        auth_params = {
            'consumer_key': os.getenv('WC_CONSUMER_KEY'),
            'consumer_secret': os.getenv('WC_CONSUMER_SECRET')
        }
        
        # Search for product
        search_response = requests.get(
            f"{WP_URL}/wp-json/wc/v3/products",
            params={**auth_params, "search": product_name},
            verify=False
        )
        search_response.raise_for_status()
        products = search_response.json()
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product_id = products[0]["id"]
        
        # Remove sale price
        update_data = {
            "sale_price": ""
        }
        
        response = requests.put(
            f"{WP_URL}/wp-json/wc/v3/products/{product_id}",
            params=auth_params,
            json=update_data,
            verify=False
        )
        response.raise_for_status()
        
        return f"המבצע הוסר בהצלחה מהמוצר {products[0]['name']}"
        
    except Exception as e:
        logger.error(f"Error removing discount: {e}")
        return f"שגיאה בהסרת המבצע: {str(e)}"

def create_product(product_info: str) -> str:
    """Create a new product in WordPress"""
    try:
        # Parse product info from string format
        # Expected format: name | description | regular_price | [stock_quantity]
        parts = product_info.strip().split("|")
        if len(parts) < 3:
            return "נדרש לפחות: שם מוצר | תיאור | מחיר"
            
        name = parts[0].strip()
        description = parts[1].strip()
        regular_price = parts[2].strip()
        stock_quantity = int(parts[3].strip()) if len(parts) > 3 else None
        
        auth_params = {
            'consumer_key': os.getenv('WC_CONSUMER_KEY'),
            'consumer_secret': os.getenv('WC_CONSUMER_SECRET')
        }
        
        # Prepare product data
        product_data = {
            "name": name,
            "description": description,
            "regular_price": regular_price,
            "status": "publish"
        }
        
        if stock_quantity is not None:
            product_data["manage_stock"] = True
            product_data["stock_quantity"] = stock_quantity
        
        # Create product
        response = requests.post(
            f"{WP_URL}/wp-json/wc/v3/products",
            params=auth_params,
            json=product_data,
            verify=False
        )
        response.raise_for_status()
        
        return f"המוצר {name} נוצר בהצלחה"
        
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        return f"שגיאה ביצירת המוצר: {str(e)}"

def edit_product(product_info: str) -> str:
    """Edit product details in WordPress"""
    try:
        # Parse product info from string format
        # Expected format: product_name | field_to_edit | new_value
        parts = product_info.strip().split("|")
        if len(parts) != 3:
            return "נדרש: שם מוצר | שדה לעריכה | ערך חדש"
            
        product_name = parts[0].strip()
        field = parts[1].strip()
        new_value = parts[2].strip()
        
        auth_params = {
            'consumer_key': os.getenv('WC_CONSUMER_KEY'),
            'consumer_secret': os.getenv('WC_CONSUMER_SECRET')
        }
        
        # Search for product
        search_response = requests.get(
            f"{WP_URL}/wp-json/wc/v3/products",
            params={**auth_params, "search": product_name},
            verify=False
        )
        search_response.raise_for_status()
        products = search_response.json()
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product_id = products[0]["id"]
        
        # Map field names to API fields
        field_mapping = {
            "שם": "name",
            "תיאור": "description",
            "מחיר": "regular_price",
            "כמות": "stock_quantity"
        }
        
        if field not in field_mapping:
            return f"שדה לא חוקי. אפשרויות: {', '.join(field_mapping.keys())}"
            
        # Prepare update data
        update_data = {
            field_mapping[field]: new_value
        }
        
        # If updating stock, make sure manage_stock is enabled
        if field == "כמות":
            update_data["manage_stock"] = True
            update_data["stock_quantity"] = int(new_value)
        
        # Update product
        response = requests.put(
            f"{WP_URL}/wp-json/wc/v3/products/{product_id}",
            params=auth_params,
            json=update_data,
            verify=False
        )
        response.raise_for_status()
        
        return f"המוצר {product_name} עודכן בהצלחה"
        
    except Exception as e:
        logger.error(f"Error editing product: {e}")
        return f"שגיאה בעריכת המוצר: {str(e)}"

def delete_product(product_name: str) -> str:
    """Delete a product from WordPress"""
    try:
        auth_params = {
            'consumer_key': os.getenv('WC_CONSUMER_KEY'),
            'consumer_secret': os.getenv('WC_CONSUMER_SECRET')
        }
        
        # Search for product
        search_response = requests.get(
            f"{WP_URL}/wp-json/wc/v3/products",
            params={**auth_params, "search": product_name},
            verify=False
        )
        search_response.raise_for_status()
        products = search_response.json()
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product_id = products[0]["id"]
        
        # Delete product
        response = requests.delete(
            f"{WP_URL}/wp-json/wc/v3/products/{product_id}",
            params={**auth_params, "force": True},
            verify=False
        )
        response.raise_for_status()
        
        return f"המוצר {product_name} נמחק בהצלחה"
        
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        return f"שגיאה במחיקת המוצר: {str(e)}"

def get_product_details(product_name: str) -> str:
    """Get detailed information about a product"""
    try:
        auth_params = {
            'consumer_key': os.getenv('WC_CONSUMER_KEY'),
            'consumer_secret': os.getenv('WC_CONSUMER_SECRET')
        }
        
        # Search for product
        search_response = requests.get(
            f"{WP_URL}/wp-json/wc/v3/products",
            params={**auth_params, "search": product_name},
            verify=False
        )
        search_response.raise_for_status()
        products = search_response.json()
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product = products[0]
        
        # Format product details
        details = [
            f"שם: {product['name']}",
            f"תיאור: {product['description']}",
            f"מחיר: ₪{product.get('price', 'לא זמין')}",
            f"סטטוס: {product['status']}",
        ]
        
        if product.get('manage_stock'):
            details.append(f"כמות במלאי: {product.get('stock_quantity', 0)}")
            
        if product.get('sale_price'):
            details.append(f"מחיר מבצע: ₪{product['sale_price']}")
            
        return "\n".join(details)
        
    except Exception as e:
        logger.error(f"Error getting product details: {e}")
        return f"שגיאה בקבלת פרטי המוצר: {str(e)}"

def get_sales() -> str:
    """Get sales data from WordPress"""
    try:
        auth_params = {
            'consumer_key': WP_USER,
            'consumer_secret': WP_PASSWORD
        }
        
        response = requests.get(
            f"{WP_URL}/wp-json/wc/v3/reports/sales",
            params=auth_params,
            verify=False
        )
        response.raise_for_status()
        data = response.json()
        
        total_sales = data.get("total_sales", 0)
        return f"סך המכירות: {total_sales} יחידות"
        
    except Exception as e:
        logger.error(f"Error getting sales data: {e}")
        return f"שגיאה בקבלת נתוני המכירות: {str(e)}"

# Initialize LangChain components
llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4-0125-preview")
memory = ConversationBufferWindowMemory(
    memory_key="chat_history",
    k=5,
    return_messages=True
)


def get_product_images(product_id: int) -> str:
    """Get all images for a product"""
    try:
        images = media_handler.get_product_images(product_id)
        if not images:
            return "אין תמונות למוצר זה"
            
        image_urls = [f"{i+1}. {img['src']}" for i, img in enumerate(images)]
        return "תמונות המוצר:\n" + "\n".join(image_urls)
        
    except Exception as e:
        logger.error(f"Error getting product images: {e}")
        return f"שגיאה בקבלת תמונות המוצר: {str(e)}"

def delete_product_image(product_id: int, image_number: int) -> str:
    """Delete a product image by its number in the list"""
    try:
        images = media_handler.get_product_images(product_id)
        if not images or image_number > len(images):
            return "מספר תמונה לא חוקי"
            
        image = images[image_number - 1]
        media_handler.delete_product_image(product_id, image['id'])
        return "התמונה נמחקה בהצלחה"
        
    except Exception as e:
        logger.error(f"Error deleting product image: {e}")
        return f"שגיאה במחיקת התמונה: {str(e)}"

def create_coupon(coupon_info: str) -> str:
    """Create a new coupon in WooCommerce"""
    try:
        # Parse coupon info from string format
        # Expected format: code | type | amount | [description] | [expiry_date] | [min_amount] | [max_amount]
        parts = coupon_info.strip().split("|")
        logger.debug(f"Received coupon info: {coupon_info}")
        logger.debug(f"Split into parts: {parts}")
        
        if len(parts) < 3:
            return "נדרש לפחות: קוד קופון | סוג הנחה | סכום הנחה"
            
        code = parts[0].strip()
        discount_type = parts[1].strip().lower()
        amount = float(parts[2].strip())
        
        # Optional parameters with detailed logging
        description = parts[3].strip() if len(parts) > 3 else None
        expiry_date = parts[4].strip() if len(parts) > 4 else None
        min_amount = float(parts[5].strip()) if len(parts) > 5 else None
        max_amount = float(parts[6].strip()) if len(parts) > 6 else None
        
        logger.debug(f"Parsed values: code={code}, type={discount_type}, amount={amount}")
        logger.debug(f"Optional values: description={description}, expiry={expiry_date}, min={min_amount}, max={max_amount}")
        
        # Validate discount type
        if discount_type not in ['percent', 'fixed_cart']:
            logger.error(f"Invalid discount type: {discount_type}")
            return "סוג ההנחה חייב להיות 'percent' (אחוזים) או 'fixed_cart' (סכום קבוע)"
        
        try:
            # Create coupon
            coupon = coupon_handler.create_coupon(
                code=code,
                discount_type=discount_type,
                amount=amount,
                description=description,
                expiry_date=expiry_date,
                min_amount=min_amount,
                max_amount=max_amount
            )
            logger.debug(f"Coupon created successfully: {coupon}")
            return f"הקופון {code} נוצר בהצלחה!"
            
        except Exception as api_error:
            logger.error(f"API Error creating coupon: {str(api_error)}")
            error_msg = str(api_error)
            if "already exists" in error_msg.lower():
                return f"קופון עם הקוד {code} כבר קיים במערכת"
            return f"שגיאה ביצירת הקופון: {error_msg}"
        
    except ValueError as ve:
        logger.error(f"Value error in create_coupon: {str(ve)}")
        return f"שגיאה בערכים שהוזנו: {str(ve)}"
    except Exception as e:
        logger.error(f"Error creating coupon: {str(e)}")
        return f"שגיאה ביצירת הקופון: {str(e)}"

def list_coupons(_: str = "") -> str:
    """Get list of all coupons"""
    try:
        coupons = coupon_handler.list_coupons()
        
        if not coupons:
            return "אין קופונים פעילים בחנות"
            
        coupons_text = []
        for c in coupons:
            discount = f"{c['amount']}%" if c['discount_type'] == 'percent' else f"₪{c['amount']}"
            expiry = f" (בתוקף עד {c['date_expires'][:10]})" if c.get('date_expires') else ""
            coupons_text.append(f"- {c['code']}: {discount}{expiry}")
            
        return "הקופונים בחנות:\n" + "\n".join(coupons_text)
        
    except Exception as e:
        logger.error(f"Error listing coupons: {e}")
        return f"שגיאה בהצגת הקופונים: {str(e)}"

def edit_coupon(coupon_info: str) -> str:
    """Edit an existing coupon"""
    try:
        # Parse coupon info from string format
        # Expected format: code | field | new_value
        parts = coupon_info.strip().split("|")
        if len(parts) != 3:
            return "נדרש: קוד קופון | שדה לעריכה | ערך חדש"
            
        code = parts[0].strip()
        field = parts[1].strip()
        new_value = parts[2].strip()
        
        # Search for coupon by code
        coupons = coupon_handler.search_coupons(code)
        if not coupons:
            return f"לא נמצא קופון עם הקוד {code}"
            
        coupon_id = coupons[0]["id"]
        
        # Map field names to API fields
        field_mapping = {
            "קוד": "code",
            "סוג": "discount_type",
            "סכום": "amount",
            "תיאור": "description",
            "תפוגה": "date_expires",
            "מינימום": "minimum_amount",
            "מקסימום": "maximum_amount"
        }
        
        if field not in field_mapping:
            return f"שדה לא חוקי. אפשרויות: {', '.join(field_mapping.keys())}"
            
        # Prepare update data
        update_data = {
            field_mapping[field]: new_value
        }
        
        # Handle special cases
        if field == "תפוגה":
            update_data["date_expires"] = f"{new_value}T23:59:59"
        elif field in ["מינימום", "מקסימום", "סכום"]:
            update_data[field_mapping[field]] = float(new_value)
        
        # Update coupon
        coupon_handler.edit_coupon(coupon_id, **update_data)
        
        return f"הקופון {code} עודכן בהצלחה"
        
    except Exception as e:
        logger.error(f"Error editing coupon: {e}")
        return f"שגיאה בעריכת הקופון: {str(e)}"

def delete_coupon(code: str) -> str:
    """Delete a coupon"""
    try:
        # Search for coupon by code
        coupons = coupon_handler.search_coupons(code)
        if not coupons:
            return f"לא נמצא קופון עם הקוד {code}"
            
        coupon_id = coupons[0]["id"]
        
        # Delete coupon
        coupon_handler.delete_coupon(coupon_id)
        
        return f"הקופון {code} נמחק בהצלחה"
        
    except Exception as e:
        logger.error(f"Error deleting coupon: {e}")
        return f"שגיאה במחיקת הקופון: {str(e)}"

def list_orders(status: str = "") -> str:
    """Get list of orders with optional status filter"""
    try:
        orders = order_handler.list_orders(status=status if status else None)
        
        if not orders:
            return "אין הזמנות במערכת"
            
        orders_text = []
        for order in orders:
            status_hebrew = {
                'pending': 'ממתין לתשלום',
                'processing': 'בטיפול',
                'on-hold': 'בהמתנה',
                'completed': 'הושלם',
                'cancelled': 'בוטל',
                'refunded': 'זוכה',
                'failed': 'נכשל'
            }.get(order['status'], order['status'])
            
            total = order.get('total', '0')
            date = order.get('date_created', '').split('T')[0]
            order_text = f"#{order['id']}: {status_hebrew} | ₪{total} | {date}"
            
            # Add customer name if available
            if order.get('billing') and order['billing'].get('first_name'):
                customer = f"{order['billing']['first_name']} {order['billing']['last_name']}"
                order_text += f" | {customer}"
            
            orders_text.append(order_text)
            
        return "ההזמנות במערכת:\n" + "\n".join(orders_text)
        
    except Exception as e:
        logger.error(f"Error listing orders: {e}")
        return f"שגיאה בהצגת ההזמנות: {str(e)}"

def get_order_details(order_id: str) -> str:
    """Get detailed information about a specific order"""
    try:
        # Convert order_id to int
        order_id = int(order_id)
        order = order_handler.get_order_details(order_id)
        
        # Format billing details
        billing = order.get('billing', {})
        shipping = order.get('shipping', {})
        
        details = [
            f"הזמנה #{order['id']}",
            f"סטטוס: {order.get('status', 'לא ידוע')}",
            f"תאריך: {order.get('date_created', '').split('T')[0]}",
            f"סה\"כ: ₪{order.get('total', '0')}",
            "\nפרטי לקוח:",
            f"שם: {billing.get('first_name', '')} {billing.get('last_name', '')}",
            f"טלפון: {billing.get('phone', 'לא צוין')}",
            f"אימייל: {billing.get('email', 'לא צוין')}",
            "\nכתובת למשלוח:",
            f"{shipping.get('address_1', '')}",
            f"{shipping.get('city', '')}, {shipping.get('postcode', '')}"
        ]
        
        # Add line items
        details.append("\nפריטים:")
        for item in order.get('line_items', []):
            details.append(f"- {item.get('name', '')}: {item.get('quantity', 0)} יח' × ₪{item.get('price', '0')}")
        
        # Add notes if any
        notes = order_handler.get_order_notes(order_id)
        if notes:
            details.append("\nהערות:")
            for note in notes:
                if not note.get('customer_note', False):  # Show only admin notes
                    details.append(f"- {note.get('note', '')}")
        
        return "\n".join(details)
        
    except Exception as e:
        logger.error(f"Error getting order details: {e}")
        return f"שגיאה בהצגת פרטי ההזמנה: {str(e)}"

def update_order_status(order_info: str) -> str:
    """Update order status"""
    try:
        # Parse order info - format: "order_id status"
        parts = order_info.strip().split()
        if len(parts) < 2:
            return "נדרש מזהה הזמנה וסטטוס חדש"
            
        order_id = int(parts[0])
        status = parts[1].lower()
        
        # Update status
        order = order_handler.update_order_status(order_id, status)
        
        status_hebrew = {
            'pending': 'ממתין לתשלום',
            'processing': 'בטיפול',
            'on-hold': 'בהמתנה',
            'completed': 'הושלם',
            'cancelled': 'בוטל',
            'refunded': 'זוכה',
            'failed': 'נכשל'
        }.get(status, status)
        
        return f"סטטוס ההזמנה #{order_id} עודכן ל-{status_hebrew}"
        
    except ValueError as ve:
        logger.error(f"Invalid order status: {ve}")
        return f"סטטוס לא חוקי: {str(ve)}"
    except Exception as e:
        logger.error(f"Error updating order status: {e}")
        return f"שגיאה בעדכון סטטוס ההזמנה: {str(e)}"

def search_orders(search_info: str) -> str:
    """Search orders by various parameters"""
    try:
        # Parse search info - format: "field:value"
        if ':' not in search_info:
            # Treat as general search term
            orders = order_handler.search_orders(search_term=search_info)
        else:
            field, value = search_info.split(':', 1)
            field = field.strip().lower()
            value = value.strip()
            
            # Prepare search parameters
            search_params = {}
            if field == 'לקוח':
                search_params['customer_id'] = int(value)
            elif field == 'סטטוס':
                search_params['status'] = value.lower()
            elif field == 'תאריך':
                if '-' in value:
                    date_from, date_to = value.split('-')
                    search_params['date_from'] = date_from.strip()
                    search_params['date_to'] = date_to.strip()
                else:
                    search_params['date_from'] = value
                    search_params['date_to'] = value
            else:
                return "שדה חיפוש לא חוקי. אפשרויות: לקוח, סטטוס, תאריך"
            
            orders = order_handler.search_orders(**search_params)
        
        if not orders:
            return "לא נמצאו הזמנות מתאימות"
            
        # Format results similar to list_orders
        orders_text = []
        for order in orders:
            status_hebrew = {
                'pending': 'ממתין לתשלום',
                'processing': 'בטיפול',
                'on-hold': 'בהמתנה',
                'completed': 'הושלם',
                'cancelled': 'בוטל',
                'refunded': 'זוכה',
                'failed': 'נכשל'
            }.get(order['status'], order['status'])
            
            total = order.get('total', '0')
            date = order.get('date_created', '').split('T')[0]
            customer = f"{order['billing']['first_name']} {order['billing']['last_name']}" if order.get('billing') else "לא צוין"
            
            orders_text.append(f"#{order['id']}: {status_hebrew} | ₪{total} | {date} | {customer}")
            
        return "תוצאות החיפוש:\n" + "\n".join(orders_text)
        
    except Exception as e:
        logger.error(f"Error searching orders: {e}")
        return f"שגיאה בחיפוש הזמנות: {str(e)}"

def create_order(order_info: str) -> str:
    """Create a new order"""
    try:
        # Parse order info from string format
        # Expected format: first_name | last_name | email | phone | address | city | postcode | product_id:quantity,product_id:quantity
        parts = order_info.strip().split("|")
        if len(parts) < 8:
            return "נדרשים כל הפרטים: שם פרטי | שם משפחה | אימייל | טלפון | כתובת | עיר | מיקוד | מוצרים"
            
        # Parse customer data
        customer_data = {
            "first_name": parts[0].strip(),
            "last_name": parts[1].strip(),
            "email": parts[2].strip(),
            "phone": parts[3].strip(),
            "address_1": parts[4].strip(),
            "city": parts[5].strip(),
            "postcode": parts[6].strip()
        }
        
        # Parse items
        items_str = parts[7].strip()
        items = []
        for item in items_str.split(","):
            if ":" not in item:
                return "פורמט מוצרים לא תקין. נדרש: מזהה_מוצר:כמות,מזהה_מוצר:כמות"
            product_id, quantity = item.split(":")
            items.append({
                "product_id": int(product_id),
                "quantity": int(quantity)
            })
        
        # Add shipping method if specified
        shipping_method = parts[8].strip() if len(parts) > 8 else None
        
        # Create order
        order = order_handler.create_order(customer_data, items, shipping_method)
        
        return f"ההזמנה נוצרה בהצלחה! מספר הזמנה: #{order['id']}"
        
    except ValueError as ve:
        logger.error(f"Invalid value in create_order: {str(ve)}")
        return f"ערך לא תקין: {str(ve)}"
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        return f"שגיאה ביצירת ההזמנה: {str(e)}"

# Define tools
tools = [
    Tool(
        name="list_products",
        func=list_products,
        description="מציג את רשימת המוצרים בחנות עם המחירים שלהם"
    ),
    Tool(
        name="create_product",
        func=create_product,
        description="יוצר מוצר חדש. פורמט: שם | תיאור | מחיר | [כמות במלאי]"
    ),
    Tool(
        name="edit_product",
        func=edit_product,
        description="עורך פרטי מוצר. פורמט: שם מוצר | שדה לעריכה | ערך חדש. שדות אפשריים: שם, תיאור, מחיר, כמות"
    ),
    Tool(
        name="delete_product",
        func=delete_product,
        description="מוחק מוצר מהחנות. מקבל את שם המוצר"
    ),
    Tool(
        name="get_product_details",
        func=get_product_details,
        description="מציג את כל הפרטים של מוצר. מקבל את שם המוצר"
    ),
    Tool(
        name="update_price",
        func=update_price,
        description="משנה את המחיר של מוצר. מקבל שם מוצר ומחיר חדש או אחוז שינוי (לדוגמה: 'מוצר א 100' או 'מוצר א -10%')"
    ),
    Tool(
        name="remove_discount",
        func=remove_discount,
        description="מסיר מבצע/הנחה ממוצר. מקבל את שם המוצר"
    ),
    Tool(
        name="get_sales",
        func=get_sales,
        description="מציג את נתוני המכירות בחנות"
    ),
    Tool(
        name="create_coupon",
        func=create_coupon,
        description="יוצר קופון חדש. פורמט: קוד | סוג (percent/fixed_cart) | סכום | [תיאור] | [תפוגה YYYY-MM-DD] | [מינימום] | [מקסימום]"
    ),
    Tool(
        name="list_coupons",
        func=list_coupons,
        description="מציג את רשימת הקופונים בחנות"
    ),
    Tool(
        name="edit_coupon",
        func=edit_coupon,
        description="עורך קופון קיים. פורמט: קוד | שדה | ערך חדש. שדות: קוד, סוג, סכום, תיאור, תפוגה, מינימום, מקסימום"
    ),
    Tool(
        name="delete_coupon",
        func=delete_coupon,
        description="מוחק קופון מהחנות. מקבל את קוד הקופון"
    ),
    Tool(
        name="list_orders",
        func=list_orders,
        description="מציג את רשימת ההזמנות. ניתן לסנן לפי סטטוס"
    ),
    Tool(
        name="get_order_details",
        func=get_order_details,
        description="מציג פרטים מלאים על הזמנה ספציפית. מקבל מזהה הזמנה"
    ),
    Tool(
        name="update_order_status",
        func=update_order_status,
        description="מעדכן סטטוס הזמנה. פורמט: מזהה_הזמנה סטטוס_חדש"
    ),
    Tool(
        name="search_orders",
        func=search_orders,
        description="מחפש הזמנות לפי פרמטרים שונים. פורמט: שדה:ערך (למשל: סטטוס:completed, לקוח:123, תאריך:2024-03-01)"
    ),
    Tool(
        name="create_order",
        func=create_order,
        description="יוצר הזמנה חדשה. פורמט: שם_פרטי | שם_משפחה | אימייל | טלפון | כתובת | עיר | מיקוד | מזהה_מוצר:כמות,מזהה_מוצר:כמות | [שיטת_משלוח]"
    )
]

# הגדרת לוגר ייעודי ל-agent
agent_logger = logging.getLogger('agent')
agent_logger.setLevel(logging.INFO)
agent_logger.addHandler(file_handler)
agent_logger.propagate = False

class AgentCallbackHandler(BaseCallbackHandler):
    """Handler for logging agent events to file."""
    
    def on_chain_start(self, serialized: dict, inputs: dict, **kwargs) -> None:
        """Log when chain starts running."""
        agent_logger.info(f"Starting chain with inputs: {inputs}")

    def on_chain_end(self, outputs: dict, **kwargs) -> None:
        """Log when chain ends running."""
        agent_logger.info(f"Chain finished with outputs: {outputs}")

    def on_chain_error(self, error: Exception, **kwargs) -> None:
        """Log when chain errors."""
        agent_logger.error(f"Chain error: {str(error)}")

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        """Log when tool starts running."""
        agent_logger.info(f"Starting tool {serialized.get('name', 'unknown')} with input: {input_str}")

    def on_tool_end(self, output: str, **kwargs) -> None:
        """Log when tool ends running."""
        agent_logger.info(f"Tool finished with output: {output}")

    def on_tool_error(self, error: Exception, **kwargs) -> None:
        """Log when tool errors."""
        agent_logger.error(f"Tool error: {str(error)}")

    def on_text(self, text: str, **kwargs) -> None:
        """Log any text."""
        agent_logger.info(text)

# Initialize agent with proper callback handler
agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
    memory=memory,
    verbose=False,
    handle_parsing_errors=True,
    callbacks=[AgentCallbackHandler()],
    system_message=SystemMessage(content="""אתה עוזר וירטואלי שמנהל חנות וורדפרס. 
    אתה יכול לעזור למשתמש בכל הקשור לניהול החנות - הצגת מוצרים, שינוי מחירים, הורדת מבצעים ובדיקת נתוני מכירות.
    אתה מבין עברית ויכול לבצע פעולות מורכבות כמו שינוי מחירים באחוזים.
    
    כשמשתמש מבקש לשנות מחיר:
    - אם הוא מציין מחיר ספציפי (למשל "שנה ל-100 שקל") - השתמש במחיר שצוין
    - אם הוא מבקש להוריד/להעלות באחוזים - חשב את המחיר החדש לפי האחוז
    
    תמיד ענה בעברית ובצורה ידידותית.""")
)

# הסרת callback מיותר
agent.callbacks = None

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photos."""
    chat_id = update.message.chat_id
    logger.info(f"=== New Photo ===")
    logger.info(f"Chat ID: {chat_id}")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Get the largest photo size
        photo = update.message.photo[-1]
        logger.info(f"Photo details - File ID: {photo.file_id}, Size: {photo.file_size} bytes")
        
        # Send processing message
        processing_message = await context.bot.send_message(
            chat_id=chat_id,
            text="🔄 מעבד את התמונה...\nאנא המתן"
        )
        
        try:
            # Download photo
            photo_file = await context.bot.get_file(photo.file_id)
            photo_bytes = await photo_file.download_as_bytearray()
            logger.debug("Photo downloaded successfully")
            
            # Store photo data temporarily
            if 'temp_photos' not in context.user_data:
                context.user_data['temp_photos'] = []
            # Keep only the latest photo
            context.user_data['temp_photos'] = [photo_bytes]
            
            # Delete processing message
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=processing_message.message_id
            )
            
            # Get product list
            products_list = list_products()
            if products_list.startswith("שגיאה") or products_list == "לא נמצאו מוצרים בחנות":
                raise Exception(products_list)
            
            # Show product list and ask which product this is for
            await update.message.reply_text(
                "קיבלתי את התמונה! 📸\n\n"
                "לאיזה מוצר להוסיף את התמונה?\n"
                "אנא העתק את השם המדויק מהרשימה:\n\n"
                f"{products_list}"
            )
            
        except Exception as e:
            # Clean up on error
            context.user_data.pop('temp_photos', None)
            logger.error(f"Error processing photo: {e}")
            error_msg = str(e)
            
            if "Failed to download" in error_msg:
                error_msg = "שגיאה בהורדת התמונה. אנא נסה שוב."
            elif "לא נמצאו מוצרים" in error_msg:
                error_msg = "לא נמצאו מוצרים בחנות. אנא צור מוצר חדש לפני הוספת תמונה."
            else:
                error_msg = "שגיאה בטיפול בתמונה. אנא נסה שוב."
            
            # Delete processing message if it exists
            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=processing_message.message_id
                )
            except:
                pass
                
            await update.message.reply_text(error_msg)
            
    except Exception as e:
        logger.error(f"Error handling photo: {e}")
        await update.message.reply_text(
            "מצטער, הייתה שגיאה בטיפול בתמונה.\n"
            "אנא ודא שהתמונה תקינה ונסה שוב."
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages."""
    chat_id = update.message.chat_id
    user_message = update.message.text
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    logger.info("="*50)
    logger.info(f"New Message Received at {current_time}")
    logger.info(f"Chat ID: {chat_id}")
    logger.info(f"User: {update.message.from_user.first_name} {update.message.from_user.last_name}")
    logger.info(f"Message: {user_message}")
    logger.info("="*50)
    logger.info("Processing message...")

    try:
        # Check if we have a pending photo to attach
        if 'temp_photos' in context.user_data and context.user_data['temp_photos']:
            logger.info("Found pending photo to attach")
            # Send processing message
            processing_message = await context.bot.send_message(
                chat_id=chat_id,
                text="🔄 מעבד את התמונה...\nאנא המתן מספר שניות"
            )
            logger.info("Sent processing message")

            try:
                # First verify the product exists
                auth_params = {
                    'consumer_key': os.getenv('WC_CONSUMER_KEY'),
                    'consumer_secret': os.getenv('WC_CONSUMER_SECRET')
                }
                
                # Clean up and normalize the product name
                clean_name = user_message.strip()
                # Remove any extra whitespace
                clean_name = ' '.join(clean_name.split())
                logger.debug(f"Searching for product with normalized name: {clean_name}")
                
                # First try exact match
                search_response = requests.get(
                    f"{WP_URL}/wp-json/wc/v3/products",
                    params={**auth_params, "search": clean_name},
                    verify=False
                )
                search_response.raise_for_status()
                products = search_response.json()
                
                # If no exact match, try case-insensitive search
                if not products:
                    logger.debug("No exact match found, trying case-insensitive search")
                    all_products_response = requests.get(
                        f"{WP_URL}/wp-json/wc/v3/products",
                        params={**auth_params, "per_page": 100},
                        verify=False
                    )
                    all_products_response.raise_for_status()
                    all_products = all_products_response.json()
                    
                    # Try to find a case-insensitive match
                    products = [p for p in all_products if p['name'].lower() == clean_name.lower()]
                    
                    if not products:
                        # Try partial match
                        products = [p for p in all_products if clean_name.lower() in p['name'].lower()]
                
                if not products:
                    await context.bot.delete_message(
                        chat_id=chat_id,
                        message_id=processing_message.message_id
                    )
                    await update.message.reply_text(
                        f"לא נמצא מוצר בשם '{user_message}'.\n"
                        "אנא בחר את השם המדויק מהרשימה:\n\n"
                        f"{list_products()}"
                    )
                    return

                product_id = products[0]["id"]
                product_name = products[0]["name"]
                logger.debug(f"Found product ID: {product_id} for '{product_name}'")
                
                try:
                    # Now handle the photo attachment
                    logger.debug("Attaching photo to product")
                    
                    # Set the image directly using base64
                    updated_product = media_handler.set_product_image(product_id, context.user_data['temp_photos'][-1])
                    
                    # Clear the temporary photo storage
                    context.user_data.pop('temp_photos', None)
                    
                    # Delete processing message
                    await context.bot.delete_message(
                        chat_id=chat_id,
                        message_id=processing_message.message_id
                    )
                    
                    # Show success message
                    await update.message.reply_text(f"✅ התמונה הועלתה בהצלחה למוצר '{product_name}'")
                    
                    # Show image preview
                    if updated_product.get('images'):
                        latest_image = updated_product['images'][0]  # The one we just added
                        await update.message.reply_text(
                            f"תצוגה מקדימה של התמונה החדשה:\n{latest_image['src']}\n\n"
                            f"סך הכל {len(updated_product['images'])} תמונות למוצר זה."
                        )
                    
                    logger.debug("Photo attachment process completed successfully")
                    return
                    
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error in photo attachment process: {error_msg}")
                    
                    if "Failed to verify image attachment" in error_msg:
                        error_msg = "לא הצלחתי לאמת את שיוך התמונה למוצר. אנא נסה שוב."
                    elif "Failed to upload image" in error_msg:
                        error_msg = "שגיאה בהעלאת התמונה. אנא ודא שהתמונה תקינה ונסה שוב."
                    elif "Failed to update product" in error_msg:
                        error_msg = "שגיאה בעדכון המוצר. אנא נסה שוב."
                    elif "Connection" in error_msg:
                        error_msg = "שגיאה בתקשורת עם השרת. אנא ודא שיש חיבור לאינטרנט ונסה שוב."
                    elif "Timeout" in error_msg:
                        error_msg = "השרת לא הגיב בזמן. אנא נסה שוב."
                    else:
                        error_msg = "שגיאה בשיוך התמונה למוצר. אנא נסה שוב."
                    
                    # Delete processing message
                    await context.bot.delete_message(
                        chat_id=chat_id,
                        message_id=processing_message.message_id
                    )
                    
                    # Show error message with retry option
                    await update.message.reply_text(
                        f"❌ {error_msg}\n\n"
                        "אתה יכול:\n"
                        "1. לנסות שוב עם אותה תמונה - פשוט שלח שוב את שם המוצר\n"
                        "2. לשלוח תמונה חדשה\n"
                        "3. לבטל את התהליך על ידי שליחת הודעת טקסט כלשהי"
                    )
                    return
            
            except Exception as e:
                logger.error(f"Error handling product image: {e}", exc_info=True)
                error_msg = str(e)
                if "Failed to verify image attachment" in error_msg:
                    error_msg = "לא הצלחתי לאמת את שיוך התמונה למוצר. אנא נסה שוב."
                elif "Error uploading image" in error_msg:
                    error_msg = "שגיאה בהעלאת התמונה. אנא ודא שהתמונה תקינה ונסה שוב."
                else:
                    error_msg = "שגיאה בשיוך התמונה למוצר. אנא נסה שוב."
                
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=processing_message.message_id
                )
                await update.message.reply_text(error_msg)
                # Clear the temporary photo storage on error
                context.user_data.pop('temp_photos', None)
                return

        # Send intermediate message
        processing_message = await context.bot.send_message(
            chat_id=chat_id,
            text="🔄 מעבד את הבקשה שלך...\nאנא המתן מספר שניות"
        )
        
        # Send typing action
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        logger.debug("Sent typing action")

        # Get response from agent
        logger.debug("Getting response from agent")
        response = agent.run(input=user_message)
        logger.debug(f"Agent response: {response}")
        
        # Delete processing message
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=processing_message.message_id
        )
        
        # Send response
        await context.bot.send_message(
            chat_id=chat_id,
            text=response
        )
            
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text="מצטער, אירעה שגיאה בעיבוד הבקשה שלך. אנא נסה שוב."
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    logger.info(f"=== New User Started Bot ===")
    logger.info(f"Chat ID: {update.message.chat_id}")
    logger.info(f"User: {update.message.from_user.first_name} {update.message.from_user.last_name}")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    welcome_message = """ברוכים הבאים לבוט ניהול החנות!
אני יכול לעזור לך עם המשימות הבאות:

📦 ניהול מוצרים:
- הצגת רשימת מוצרים
- עדכון מחירים
- הסרת הנחות ממוצרים

🖼️ ניהול תמונות:
- העלאת תמונות למוצרים
- מחיקת תמונות ממוצרים

🎫 ניהול קופונים:
- יצירת קופון חדש
- הצגת רשימת קופונים
- עדכון פרטי קופון
- מחיקת קופון

📋 ניהול הזמנות:
- יצירת הזמנה חדשה
- הצגת רשימת הזמנות
- צפייה בפרטי הזמנה
- עדכון סטטוס הזמנה
- חיפוש הזמנות לפי פרמטרים שונים (תאריך, לקוח, סטטוס)

לדוגמה, ליצירת הזמנה חדשה:
צור הזמנה חדשה: שם_פרטי | שם_משפחה | אימייל | טלפון | כתובת | עיר | מיקוד | מזהה_מוצר:כמות

אשמח לעזור! פשוט תגיד/י לי מה צריך 😊"""
    await update.message.reply_text(welcome_message)

async def test_image_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test image upload functionality"""
    try:
        # בדיקה שה-MediaHandler קיים ועובד
        if not media_handler:
            await update.message.reply_text("שגיאה: MediaHandler לא מאותחל")
            return

        # בדיקת הרשאות לתיקיית temp
        temp_dir = 'temp_media'
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            await update.message.reply_text(f"נוצרה תיקיית {temp_dir}")

        # בדיקת חיבור ל-WooCommerce
        try:
            test_product = media_handler.wcapi.get("products").json()
            await update.message.reply_text(f"חיבור ל-WooCommerce תקין, נמצאו {len(test_product)} מוצרים")
        except Exception as e:
            await update.message.reply_text(f"שגיאה בחיבור ל-WooCommerce: {str(e)}")

    except Exception as e:
        logger.error(f"Error in test_image_upload: {e}")
        await update.message.reply_text(f"שגיאה בבדיקת העלאת תמונות: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Send message to the user
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "מצטער, אירעה שגיאה בעיבוד הבקשה שלך. אנא נסה שוב."
        )

def main() -> None:
    """Start the bot."""
    # הודעה בטרמינל שהבוט התחיל לרוץ
    print("\nBot is running... Press Ctrl+C to stop")
    print(f"Logs are being written to: {log_file_path}\n")
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test_image", test_image_upload))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the Bot
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
