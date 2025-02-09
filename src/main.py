import os
import json
import logging
import requests
import pytz
import asyncio
import warnings
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, ConversationHandler
from handlers import (
    MediaHandler,
    CouponHandler,
    OrderHandler,
    CategoryHandler,
    CustomerHandler,
    InventoryHandler,
    ProductHandler,
    SettingsHandler
)
from utils import setup_logger, load_config
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain.agents import AgentType, Tool, initialize_agent
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import SystemMessage
import re
from langchain.callbacks.base import BaseCallbackHandler
from typing import List, Dict, Optional
from utils.logger import bot_logger, user_logger, error_logger, debug_logger

# השתקת אזהרות
warnings.filterwarnings("ignore")
# השתקת אזהרות ספציפיות של urllib3
import urllib3
urllib3.disable_warnings()

# טעינת הגדרות
config = load_config()

# הגדרת לוגר
logger = setup_logger(__name__)

# הגדרת לוגר ייעודי לאירועי בוט
bot_logger = setup_logger('bot_events')

# הגדרת לוגר ייעודי לפעולות משתמש
user_logger = setup_logger('user_actions')

# הגדרת לוגר ייעודי לשגיאות
error_logger = setup_logger('errors', level='ERROR')

# הגדרת file handler עבור agent logger
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
file_handler = logging.FileHandler(os.path.join(log_dir, 'agent.log'), encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Initialize handlers
media_handler = MediaHandler(config['WP_URL'], config['WP_USER'], config['WP_PASSWORD'])
coupon_handler = CouponHandler(config['WP_URL'])
order_handler = OrderHandler(config['WP_URL'])
category_handler = CategoryHandler(config['WP_URL'])
customer_handler = CustomerHandler(config['WP_URL'])
inventory_handler = InventoryHandler(config['WP_URL'])
product_handler = ProductHandler(config['WP_URL'])
settings_handler = SettingsHandler(config['WP_URL'])

# Set timezone
timezone = pytz.timezone('Asia/Jerusalem')

# Store temporary product creation state
product_creation_state = {}

# Conversation states
CHOOSING_PRODUCT = 1

def list_products(_: str = "") -> str:
    """Get list of products from WordPress"""
    try:
        products = product_handler.list_products(10)
        
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
        
        # Search for product
        products = product_handler.search_products(product_name)
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product = products[0]
        product_id = product["id"]
        current_price = float(product.get("price", 0))
        
        # Check if it's a percentage change
        percentage_match = re.match(r'^-?(\d+)%$', price_info)
        
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
        
        # Update product price
        product_handler.update_price(product_id, str(new_price))
        
        return f"המחיר של {product_name} עודכן בהצלחה ל-₪{new_price:.2f}"
        
    except Exception as e:
        logger.error(f"Error updating price: {e}")
        return f"שגיאה בעדכון המחיר: {str(e)}"

def remove_discount(product_name: str) -> str:
    """Remove discount from a product"""
    try:
        # Search for product
        products = product_handler.search_products(product_name)
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product = products[0]
        product_id = product["id"]
        
        # Remove discount
        product_handler.remove_discount(product_id)
        
        return f"ההנחה הוסרה בהצלחה מהמוצר {product_name}"
        
    except Exception as e:
        logger.error(f"Error removing discount: {e}")
        return f"שגיאה בהסרת ההנחה: {str(e)}"

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
        
        # Create product using the handler
        product = product_handler.create_product(
            name=name,
            description=description,
            regular_price=regular_price,
            stock_quantity=stock_quantity
        )
        
        return f"המוצר {name} נוצר בהצלחה"
        
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        return f"שגיאה ביצירת המוצר: {str(e)}"

def edit_product(product_info: str) -> str:
    """Edit an existing product in WordPress"""
    try:
        # Parse product info
        lines = product_info.strip().split('\n')
        if len(lines) < 2:
            return "נדרש שם מוצר ולפחות שדה אחד לעדכון"
            
        # Get product name from first line
        product_name = lines[0]
        
        # Search for product
        products = product_handler.search_products(product_name)
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product = products[0]
        product_id = product["id"]
        
        # Parse update fields
        update_data = {}
        for line in lines[1:]:
            if ':' not in line:
                continue
                
            field, value = line.split(':', 1)
            field = field.strip()
            value = value.strip()
            
            if field == 'שם':
                update_data['name'] = value
            elif field == 'תיאור':
                update_data['description'] = value
            elif field == 'מחיר':
                update_data['regular_price'] = value
            elif field == 'מלאי' and value.isdigit():
                update_data['stock_quantity'] = int(value)
                update_data['manage_stock'] = True
                
        if not update_data:
            return "לא נמצאו שדות תקינים לעדכון"
            
        # Update product
        updated_product = product_handler.update_product(product_id, **update_data)
        
        return f"המוצר {updated_product['name']} עודכן בהצלחה"
        
    except Exception as e:
        logger.error(f"Error editing product: {e}")
        return f"שגיאה בעדכון המוצר: {str(e)}"

def delete_product(product_name: str) -> str:
    """Delete a product from WordPress"""
    try:
        # Search for product
        products = product_handler.search_products(product_name)
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product = products[0]
        product_id = product["id"]
        
        # Delete product
        product_handler.delete_product(product_id)
        
        return f"המוצר {product_name} נמחק בהצלחה"
        
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        return f"שגיאה במחיקת המוצר: {str(e)}"

def get_product_details(product_name: str) -> str:
    """Get detailed information about a product"""
    try:
        # Search for product
        products = product_handler.search_products(product_name)
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product = products[0]
        product_id = product["id"]
        
        # Get full product details
        details = product_handler.get_product_details(product_id)
        
        # Format response
        response = [
            f"פרטי המוצר {details['name']}:",
            f"מחיר: ₪{details.get('price', 'לא זמין')}",
            f"תיאור: {details.get('description', 'אין תיאור')}"
        ]
        
        if details.get('manage_stock'):
            stock = details.get('stock_quantity', 0)
            status = "במלאי" if stock > 0 else "אזל מהמלאי"
            response.append(f"מלאי: {status} ({stock} יחידות)")
        else:
            status = "במלאי" if details.get('in_stock', True) else "אזל מהמלאי"
            response.append(f"מלאי: {status}")
            
        if details.get('sale_price'):
            response.append(f"מחיר מבצע: ₪{details['sale_price']}")
            
        return "\n".join(response)
        
    except Exception as e:
        logger.error(f"Error getting product details: {e}")
        return f"שגיאה בקבלת פרטי המוצר: {str(e)}"

def get_sales() -> str:
    """Get sales data from WordPress"""
    try:
        # Get sales data using settings handler
        data = settings_handler.get_sales_data()
        
        total_sales = data.get("total_sales", 0)
        return f"סך המכירות: {total_sales} יחידות"
        
    except Exception as e:
        logger.error(f"Error getting sales data: {e}")
        return f"שגיאה בקבלת נתוני המכירות: {str(e)}"

# Initialize LangChain components
llm = ChatOpenAI(api_key=config['OPENAI_API_KEY'], model="gpt-4-0125-preview")
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

def list_categories(_: str = "") -> str:
    """הצגת רשימת הקטגוריות בחנות"""
    try:
        categories = category_handler.list_categories()
        
        if not categories:
            return "אין קטגוריות בחנות"
            
        categories_text = []
        for cat in categories:
            # הוספת שם הקטגוריה ומזהה
            cat_line = f"- {cat['name']} (ID: {cat['id']})"
            
            # הוספת מספר המוצרים בקטגוריה
            cat_line += f" | {cat['count']} מוצרים"
            
            # אם יש קטגוריית אב, הוספת המידע
            if cat.get('parent'):
                parent = next((c['name'] for c in categories if c['id'] == cat['parent']), None)
                if parent:
                    cat_line += f" | קטגוריית אב: {parent}"
                    
            categories_text.append(cat_line)
            
        return "הקטגוריות בחנות:\n" + "\n".join(categories_text)
        
    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        return f"שגיאה בהצגת הקטגוריות: {str(e)}"

def create_category(category_info: str) -> str:
    """יצירת קטגוריה חדשה"""
    try:
        # Parse category info from string format
        # Expected format: name | description | [parent_category_name]
        parts = category_info.strip().split("|")
        if len(parts) < 1:
            return "נדרש לפחות שם לקטגוריה"
            
        name = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ""
        parent_name = parts[2].strip() if len(parts) > 2 else None
        
        # אם צוינה קטגוריית אב, מציאת המזהה שלה
        parent_id = None
        if parent_name:
            categories = category_handler.list_categories()
            parent = next((cat for cat in categories if cat['name'].lower() == parent_name.lower()), None)
            if parent:
                parent_id = parent['id']
            else:
                return f"לא נמצאה קטגוריית אב בשם {parent_name}"
        
        # יצירת הקטגוריה
        category = category_handler.create_category(name, description, parent_id)
        
        return f"הקטגוריה {name} נוצרה בהצלחה (ID: {category['id']})"
        
    except Exception as e:
        logger.error(f"Error creating category: {e}")
        return f"שגיאה ביצירת הקטגוריה: {str(e)}"

def update_category(category_info: str) -> str:
    """עדכון פרטי קטגוריה"""
    try:
        # Parse category info from string format
        # Expected format: category_name | field | new_value
        parts = category_info.strip().split("|")
        if len(parts) != 3:
            return "נדרש: שם קטגוריה | שדה לעדכון | ערך חדש"
            
        category_name = parts[0].strip()
        field = parts[1].strip()
        new_value = parts[2].strip()
        
        # חיפוש הקטגוריה לפי שם
        categories = category_handler.list_categories()
        category = next((cat for cat in categories if cat['name'].lower() == category_name.lower()), None)
        if not category:
            return f"לא נמצאה קטגוריה בשם {category_name}"
            
        # מיפוי שמות השדות בעברית לאנגלית
        field_mapping = {
            "שם": "name",
            "תיאור": "description",
            "אב": "parent"
        }
        
        if field not in field_mapping:
            return f"שדה לא חוקי. אפשרויות: {', '.join(field_mapping.keys())}"
            
        # אם מעדכנים קטגוריית אב, צריך למצוא את המזהה שלה
        if field == "אב":
            parent = next((cat for cat in categories if cat['name'].lower() == new_value.lower()), None)
            if not parent:
                return f"לא נמצאה קטגוריית אב בשם {new_value}"
            new_value = parent['id']
        
        # עדכון הקטגוריה
        update_data = {field_mapping[field]: new_value}
        category_handler.update_category(category['id'], **update_data)
        
        return f"הקטגוריה {category_name} עודכנה בהצלחה"
        
    except Exception as e:
        logger.error(f"Error updating category: {e}")
        return f"שגיאה בעדכון הקטגוריה: {str(e)}"

def delete_category(category_name: str) -> str:
    """מחיקת קטגוריה"""
    try:
        # חיפוש הקטגוריה לפי שם
        categories = category_handler.list_categories()
        category = next((cat for cat in categories if cat['name'].lower() == category_name.lower()), None)
        if not category:
            return f"לא נמצאה קטגוריה בשם {category_name}"
            
        # בדיקה אם יש מוצרים בקטגוריה
        if category['count'] > 0:
            return f"לא ניתן למחוק את הקטגוריה {category_name} כי יש בה {category['count']} מוצרים"
            
        # מחיקת הקטגוריה
        category_handler.delete_category(category['id'])
        
        return f"הקטגוריה {category_name} נמחקה בהצלחה"
        
    except Exception as e:
        logger.error(f"Error deleting category: {e}")
        return f"שגיאה במחיקת הקטגוריה: {str(e)}"

def assign_product_to_categories(product_info: str) -> str:
    """שיוך מוצר לקטגוריות"""
    try:
        # Parse product info from string format
        # Expected format: product_name | category_name1,category_name2,...
        parts = product_info.strip().split("|")
        if len(parts) != 2:
            return "נדרש: שם מוצר | שמות קטגוריות (מופרדים בפסיקים)"
            
        product_name = parts[0].strip()
        category_names = [name.strip() for name in parts[1].split(",")]
        
        # חיפוש המוצר
        products = product_handler.search_products(product_name)
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product_id = products[0]["id"]
        
        # חיפוש הקטגוריות
        categories = category_handler.list_categories()
        category_ids = []
        not_found = []
        
        for name in category_names:
            category = next((cat for cat in categories if cat['name'].lower() == name.lower()), None)
            if category:
                category_ids.append(category['id'])
            else:
                not_found.append(name)
                
        if not_found:
            return f"לא נמצאו הקטגוריות הבאות: {', '.join(not_found)}"
            
        # שיוך המוצר לקטגוריות
        category_handler.assign_product_to_category(product_id, category_ids)
        
        return f"המוצר {product_name} שויך בהצלחה לקטגוריות: {', '.join(category_names)}"
        
    except Exception as e:
        logger.error(f"Error assigning product to categories: {e}")
        return f"שגיאה בשיוך המוצר לקטגוריות: {str(e)}"

def list_customers(_: str = "") -> str:
    """הצגת רשימת הלקוחות בחנות"""
    try:
        customers = customer_handler.list_customers(per_page=20)
        
        if not customers:
            return "אין לקוחות בחנות"
            
        customers_text = []
        for customer in customers:
            # חישוב סך הרכישות של הלקוח
            total_spent = customer_handler.get_customer_total_spent(customer['id'])
            
            customer_line = [
                f"- {customer['first_name']} {customer['last_name']}",
                f"אימייל: {customer.get('email', 'לא צוין')}",
                f"טלפון: {customer.get('billing', {}).get('phone', 'לא צוין')}",
                f"סה\"כ רכישות: ₪{total_spent:.2f}"
            ]
            customers_text.append(" | ".join(customer_line))
            
        return "הלקוחות בחנות:\n" + "\n".join(customers_text)
        
    except Exception as e:
        logger.error(f"Error listing customers: {e}")
        return f"שגיאה בהצגת הלקוחות: {str(e)}"

def get_customer_details(customer_info: str) -> str:
    """הצגת פרטים מלאים על לקוח ספציפי"""
    try:
        # חיפוש לקוח לפי שם או אימייל
        customers = customer_handler.search_customers(customer_info)
        
        if not customers:
            return f"לא נמצא לקוח התואם ל-'{customer_info}'"
            
        customer = customers[0]
        total_spent = customer_handler.get_customer_total_spent(customer['id'])
        orders = customer_handler.get_customer_orders(customer['id'])
        
        details = [
            f"פרטי הלקוח {customer['first_name']} {customer['last_name']}:",
            f"אימייל: {customer.get('email', 'לא צוין')}",
            f"טלפון: {customer.get('billing', {}).get('phone', 'לא צוין')}",
            f"כתובת: {customer.get('billing', {}).get('address_1', 'לא צוינה')}",
            f"עיר: {customer.get('billing', {}).get('city', 'לא צוינה')}",
            f"מיקוד: {customer.get('billing', {}).get('postcode', 'לא צוין')}",
            f"סה\"כ רכישות: ₪{total_spent:.2f}",
            f"מספר הזמנות: {len(orders)}",
            "\nהזמנות אחרונות:"
        ]
        
        # הוספת 5 ההזמנות האחרונות
        for order in orders[:5]:
            order_line = f"- הזמנה #{order['id']} | {order['date_created']} | סטטוס: {order['status']} | סכום: ₪{order['total']}"
            details.append(order_line)
            
        return "\n".join(details)
        
    except Exception as e:
        logger.error(f"Error getting customer details: {e}")
        return f"שגיאה בקבלת פרטי הלקוח: {str(e)}"

def update_customer(customer_info: str) -> str:
    """עדכון פרטי לקוח"""
    try:
        # Parse customer info from string format
        # Expected format: customer_id/email | field | new_value
        parts = customer_info.strip().split("|")
        if len(parts) != 3:
            return "נדרש: מזהה/אימייל לקוח | שדה לעדכון | ערך חדש"
            
        customer_identifier = parts[0].strip()
        field = parts[1].strip()
        new_value = parts[2].strip()
        
        # חיפוש הלקוח
        customers = customer_handler.search_customers(customer_identifier)
        if not customers:
            return f"לא נמצא לקוח התואם ל-'{customer_identifier}'"
            
        customer_id = customers[0]['id']
        
        # מיפוי שמות השדות בעברית לאנגלית
        field_mapping = {
            "שם פרטי": "first_name",
            "שם משפחה": "last_name",
            "אימייל": "email",
            "טלפון": "billing.phone",
            "כתובת": "billing.address_1",
            "עיר": "billing.city",
            "מיקוד": "billing.postcode"
        }
        
        if field not in field_mapping:
            return f"שדה לא חוקי. אפשרויות: {', '.join(field_mapping.keys())}"
            
        # בניית אובייקט העדכון
        update_data = {}
        if "." in field_mapping[field]:
            parent, child = field_mapping[field].split(".")
            if parent not in update_data:
                update_data[parent] = {}
            update_data[parent][child] = new_value
        else:
            update_data[field_mapping[field]] = new_value
        
        # עדכון הלקוח
        customer_handler.update_customer(customer_id, **update_data)
        
        return f"פרטי הלקוח עודכנו בהצלחה"
        
    except Exception as e:
        logger.error(f"Error updating customer: {e}")
        return f"שגיאה בעדכון פרטי הלקוח: {str(e)}"

def search_customers(search_query: str) -> str:
    """חיפוש לקוחות"""
    try:
        customers = customer_handler.search_customers(search_query)
        
        if not customers:
            return f"לא נמצאו לקוחות התואמים לחיפוש '{search_query}'"
            
        results = []
        for customer in customers:
            customer_line = [
                f"- {customer['first_name']} {customer['last_name']}",
                f"אימייל: {customer.get('email', 'לא צוין')}",
                f"טלפון: {customer.get('billing', {}).get('phone', 'לא צוין')}"
            ]
            results.append(" | ".join(customer_line))
            
        return f"תוצאות חיפוש עבור '{search_query}':\n" + "\n".join(results)
        
    except Exception as e:
        logger.error(f"Error searching customers: {e}")
        return f"שגיאה בחיפוש לקוחות: {str(e)}"

def create_customer(customer_info: str) -> str:
    """יצירת לקוח חדש"""
    try:
        # ניקוי והכנת הטקסט
        customer_info = customer_info.replace('שם פרטי', '').replace('שם משפחה', '')
        customer_info = customer_info.replace('אימייל', '').replace('מייל', '')
        customer_info = customer_info.replace('טלפון', '').replace('כתובת', '')
        customer_info = customer_info.replace('עיר', '').replace('מיקוד', '')
        customer_info = customer_info.replace(':', '')  # הסרת נקודתיים
        
        # חיפוש אימייל בטקסט
        import re
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', customer_info)
        if not email_match:
            return "לא מצאתי כתובת אימייל תקינה בבקשה. אנא ספק אימייל בפורמט user@domain.com"
        
        email = email_match.group()
        # הסרת האימייל מהטקסט לעיבוד שאר הפרטים
        customer_info = customer_info.replace(email, '')
        
        # פיצול הטקסט לחלקים
        parts = [p.strip() for p in re.split(r'[|,\n]|(?:ו(?:ה)?(?:שם|מייל|טלפון|כתובת|עיר|מיקוד))|(?:הוא|היא|שלו|שלה)', customer_info) if p.strip()]
        
        # חיפוש שם פרטי ושם משפחה
        names = [p for p in parts if p and p not in [email]]
        if len(names) < 2:
            return "לא הצלחתי לזהות שם פרטי ושם משפחה. אנא ספק את הפרטים בצורה ברורה יותר"
        
        first_name = names[0].strip()
        last_name = names[1].strip()
        
        logger.info(f"Creating customer with name: {first_name} {last_name}, email: {email}")
        
        # יצירת מילון עם הפרטים הבסיסיים
        customer_data = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "username": email  # משתמש באימייל כשם משתמש
        }
        
        # חיפוש מספר טלפון
        phone_match = re.search(r'0\d{8,9}', customer_info)
        if phone_match:
            customer_data["billing_phone"] = phone_match.group()
        
        # חיפוש כתובת (אם יש)
        address_parts = [p for p in parts[2:] if p and p not in [first_name, last_name, email]]
        if len(address_parts) >= 1:
            customer_data["billing_address_1"] = address_parts[0]
        if len(address_parts) >= 2:
            customer_data["billing_city"] = address_parts[1]
        if len(address_parts) >= 3:
            customer_data["billing_postcode"] = address_parts[2]
        
        # יצירת הלקוח
        customer = customer_handler.create_customer(**customer_data)
        
        success_msg = f"לקוח חדש נוצר בהצלחה!\n"
        success_msg += f"מזהה: {customer['id']}\n"
        success_msg += f"שם: {customer['first_name']} {customer['last_name']}\n"
        success_msg += f"אימייל: {customer['email']}"
        
        if 'billing' in customer and 'phone' in customer['billing']:
            success_msg += f"\nטלפון: {customer['billing']['phone']}"
        
        return success_msg
        
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        error_msg = str(e)
        if "email already exists" in error_msg.lower():
            return f"כתובת האימייל {email} כבר קיימת במערכת. אנא נסה כתובת אימייל אחרת."
        return f"שגיאה ביצירת הלקוח: {error_msg}"

def get_low_stock_products(_: str = "") -> str:
    """הצגת מוצרים במלאי נמוך
    
    דוגמאות:
    - הצג מוצרים במלאי נמוך
    - אילו מוצרים עומדים להיגמר
    - מה המצב של המלאי
    """
    try:
        products = inventory_handler.get_low_stock_products()
        
        if not products:
            return "לא נמצאו מוצרים במלאי נמוך"
            
        products_text = []
        for p in products:
            stock = p.get('stock_quantity', 0)
            threshold = p.get('low_stock_amount', 5)
            products_text.append(
                f"- {p['name']}: נשארו {stock} יחידות (סף התראה: {threshold})"
            )
            
        return "מוצרים במלאי נמוך:\n" + "\n".join(products_text)
        
    except Exception as e:
        logger.error(f"Error getting low stock products: {e}")
        return f"שגיאה בקבלת מוצרים במלאי נמוך: {str(e)}"

def update_product_stock(product_info: str) -> str:
    """עדכון כמות מלאי למוצר
    
    דוגמאות:
    - חולצה כחולה | set | 50
    - מכנסיים שחורים | add | 20
    - נעלי ספורט | subtract | 5
    
    פורמט: שם מוצר | פעולה | כמות
    פעולות אפשריות:
    - set: קביעת כמות מדויקת
    - add: הוספת כמות למלאי הקיים
    - subtract: הורדת כמות מהמלאי הקיים
    """
    try:
        # Parse product info: product_name | operation | quantity
        parts = [p.strip() for p in product_info.split("|")]
        if len(parts) != 3:
            return "נדרש: שם מוצר | פעולה (set/add/subtract) | כמות"
            
        product_name, operation, quantity = parts
        
        try:
            quantity = int(quantity)
        except ValueError:
            return "הכמות חייבת להיות מספר שלם"
            
        # Find product using product handler
        products = product_handler.search_products(product_name)
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product_id = products[0]["id"]
        
        # Update stock
        result = inventory_handler.update_stock_quantity(product_id, quantity, operation)
        new_stock = result.get('stock_quantity', 0)
        
        operation_text = {
            'set': 'עודכן ל',
            'add': 'נוספו',
            'subtract': 'הורדו'
        }.get(operation, 'עודכן ל')
        
        return f"המלאי של {product_name} {operation_text} {quantity} יחידות (מלאי נוכחי: {new_stock})"
        
    except Exception as e:
        logger.error(f"Error updating stock: {e}")
        return f"שגיאה בעדכון המלאי: {str(e)}"

def get_product_stock_status(product_name: str) -> str:
    """הצגת סטטוס מלאי מפורט למוצר
    
    דוגמאות:
    - מה המצב של חולצה כחולה
    - הראה לי את המלאי של מכנסיים שחורים
    - כמה יש במלאי מנעלי ספורט
    """
    try:
        # Find product using product handler
        products = product_handler.search_products(product_name)
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product_id = products[0]["id"]
        
        # Get stock status
        status = inventory_handler.get_stock_status(product_id)
        
        status_text = []
        status_text.append(f"שם: {status['name']}")
        status_text.append(f"ניהול מלאי: {'פעיל' if status['manage_stock'] else 'לא פעיל'}")
        status_text.append(f"כמות במלאי: {status['stock_quantity']}")
        status_text.append(f"סטטוס: {status['stock_status']}")
        status_text.append(f"הזמנות מראש: {'מותר' if status['backorders_allowed'] else 'לא מותר'}")
        if status['low_stock_amount']:
            status_text.append(f"סף התראת מלאי נמוך: {status['low_stock_amount']}")
            
        return "\n".join(status_text)
        
    except Exception as e:
        logger.error(f"Error getting stock status: {e}")
        return f"שגיאה בקבלת סטטוס מלאי: {str(e)}"

def manage_product_stock_by_attributes(product_info: str) -> str:
    """ניהול מלאי לפי מאפיינים
    
    דוגמאות:
    חולצה כחולה
    צבע: כחול | 20
    מידה: M | 15
    מידה: L | 25
    
    מכנסיים שחורים
    צבע: שחור | 30
    מידה: 32 | 10
    מידה: 34 | 15
    מידה: 36 | 20
    """
    try:
        lines = product_info.strip().split("\n")
        if len(lines) < 2:
            return "נדרש: שם מוצר בשורה ראשונה, ואחריו שורות של מאפיין: ערך | כמות"
            
        product_name = lines[0].strip()
        
        # Find product
        auth_params = {
            'consumer_key': os.getenv('WC_CONSUMER_KEY'),
            'consumer_secret': os.getenv('WC_CONSUMER_SECRET')
        }
        
        search_response = requests.get(
            f"{config['WP_URL']}/wp-json/wc/v3/products",
            params={**auth_params, "search": product_name},
            verify=False
        )
        search_response.raise_for_status()
        products = search_response.json()
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product_id = products[0]["id"]
        
        # Parse attributes and quantities
        attributes = {}
        for line in lines[1:]:
            if ":" not in line or "|" not in line:
                continue
                
            attr_part, quantity_part = line.split("|")
            attr_name, attr_value = [x.strip() for x in attr_part.split(":")]
            
            try:
                quantity = int(quantity_part.strip())
            except ValueError:
                return f"הכמות בשורה '{line}' חייבת להיות מספר שלם"
                
            if attr_name not in attributes:
                attributes[attr_name] = {}
            attributes[attr_name][attr_value] = quantity
        
        if not attributes:
            return "לא נמצאו מאפיינים תקינים"
            
        # Update stock by attributes
        result = inventory_handler.manage_stock_by_attributes(product_id, attributes)
        
        return f"המלאי עודכן בהצלחה עבור {result['variations_updated']} וריאציות"
        
    except Exception as e:
        logger.error(f"Error managing stock by attributes: {e}")
        return f"שגיאה בניהול מלאי לפי מאפיינים: {str(e)}"

def set_product_low_stock_threshold(product_info: str) -> str:
    """הגדרת סף התראה למלאי נמוך
    
    דוגמאות:
    - חולצה כחולה | 10
    - מכנסיים שחורים | 15
    - נעלי ספורט | 5
    
    פורמט: שם מוצר | סף התראה
    """
    try:
        # Parse product info: product_name | threshold
        parts = [p.strip() for p in product_info.split("|")]
        if len(parts) != 2:
            return "נדרש: שם מוצר | סף התראה"
            
        product_name, threshold = parts
        
        try:
            threshold = int(threshold)
        except ValueError:
            return "סף ההתראה חייב להיות מספר שלם"
            
        # Find product
        auth_params = {
            'consumer_key': os.getenv('WC_CONSUMER_KEY'),
            'consumer_secret': os.getenv('WC_CONSUMER_SECRET')
        }
        
        search_response = requests.get(
            f"{config['WP_URL']}/wp-json/wc/v3/products",
            params={**auth_params, "search": product_name},
            verify=False
        )
        search_response.raise_for_status()
        products = search_response.json()
        
        if not products:
            return f"לא נמצא מוצר בשם {product_name}"
            
        product_id = products[0]["id"]
        
        # Set threshold
        inventory_handler.set_low_stock_threshold(product_id, threshold)
        
        return f"סף ההתראה למלאי נמוך עבור {product_name} נקבע ל-{threshold} יחידות"
        
    except Exception as e:
        logger.error(f"Error setting low stock threshold: {e}")
        return f"שגיאה בהגדרת סף התראה למלאי נמוך: {str(e)}"

# Define tools
tools = [
    Tool(
        name="list_products",
        func=list_products,
        description="הצגת רשימת המוצרים בחנות"
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
    ),
    Tool(
        name="list_categories",
        func=list_categories,
        description="מציג את רשימת הקטגוריות בחנות"
    ),
    Tool(
        name="create_category",
        func=create_category,
        description="יוצר קטגוריה חדשה. פורמט: שם | תיאור | [קטגוריית אב]"
    ),
    Tool(
        name="update_category",
        func=update_category,
        description="עורך פרטי קטגוריה. פורמט: שם קטגוריה | שדה | ערך חדש"
    ),
    Tool(
        name="delete_category",
        func=delete_category,
        description="מוחק קטגוריה. מקבל את שם הקטגוריה"
    ),
    Tool(
        name="assign_product_to_categories",
        func=assign_product_to_categories,
        description="משייך מוצר לקטגוריות. פורמט: שם מוצר | שמות קטגוריות (מופרדים בפסיקים)"
    ),
    Tool(
        name="list_customers",
        func=list_customers,
        description="""
        הצגת רשימת הלקוחות בחנות. אפשר לבקש בכל מיני דרכים:
        - "הצג את כל הלקוחות"
        - "מי הלקוחות שלי?"
        - "תראה לי את רשימת הלקוחות"
        - "אני רוצה לראות את כל הלקוחות במערכת"
        """
    ),
    Tool(
        name="get_customer_details",
        func=get_customer_details,
        description="מציג פרטים מלאים על לקוח ספציפי. מקבל שם או אימייל של הלקוח"
    ),
    Tool(
        name="update_customer",
        func=update_customer,
        description="עדכון פרטי לקוח. פורמט: מזהה/אימייל | שדה | ערך חדש"
    ),
    Tool(
        name="search_customers",
        func=search_customers,
        description="חיפוש לקוחות לפי טקסט חופשי"
    ),
    Tool(
        name="create_customer",
        func=create_customer,
        description="""
        יצירת לקוח חדש בחנות. הפקודה יכולה להתקבל במגוון צורות:
        - "צור לקוח חדש: שם | שם משפחה | אימייל | טלפון | כתובת | עיר | מיקוד"
        - "הוסף לקוח: שם | שם משפחה | אימייל"
        - "רישום לקוח חדש עם השם X ושם משפחה Y והמייל Z"
        - "תרשום בבקשה לקוח חדש - שם פרטי הוא X שם משפחה Y ואימייל Z"
        - "אני רוצה להוסיף לקוח חדש למערכת. קוראים לו X X והמייל שלו הוא Y"
        - כל וריאציה דומה בשפה טבעית שכוללת את פרטי הלקוח הבסיסיים
        """
    ),
    Tool(
        name="get_low_stock_products",
        func=get_low_stock_products,
        description="מציג את רשימת המוצרים במלאי נמוך"
    ),
    Tool(
        name="update_product_stock",
        func=update_product_stock,
        description="עדכון כמות מלאי למוצר"
    ),
    Tool(
        name="get_product_stock_status",
        func=get_product_stock_status,
        description="מציג את סטטוס מלאי מפורט למוצר"
    ),
    Tool(
        name="manage_product_stock_by_attributes",
        func=manage_product_stock_by_attributes,
        description="ניהול מלאי לפי מאפיינים"
    ),
    Tool(
        name="set_product_low_stock_threshold",
        func=set_product_low_stock_threshold,
        description="הגדרת סף התראה למלאי נמוך"
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
            
            # Get product list using product handler
            products = product_handler.list_products(10)
            if not products:
                raise Exception("לא נמצאו מוצרים בחנות")
                
            # Format product list
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
            
            # Show product list and ask which product this is for
            await update.message.reply_text(
                "קיבלתי את התמונה! 📸\n\n"
                "לאיזה מוצר להוסיף את התמונה?\n"
                "אנא העתק את השם המדויק מהרשימה:\n\n"
                + "\n".join(products_text)
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
    current_time = datetime.now(timezone).strftime('%Y-%m-%d %H:%M:%S')
    
    user_logger.info(
        f"New message from {update.message.from_user.first_name} "
        f"(ID: {chat_id}): {user_message}"
    )

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
                    f"{config['WP_URL']}/wp-json/wc/v3/products",
                    params={**auth_params, "search": clean_name},
                    verify=False
                )
                search_response.raise_for_status()
                products = search_response.json()
                
                # If no exact match, try case-insensitive search
                if not products:
                    logger.debug("No exact match found, trying case-insensitive search")
                    all_products_response = requests.get(
                        f"{config['WP_URL']}/wp-json/wc/v3/products",
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
        error_logger.error(
            f"Error processing message: {str(e)}", 
            exc_info=True
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text="מצטער, אירעה שגיאה בעיבוד הבקשה שלך. אנא נסה שוב."
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """שליחת הודעת פתיחה כשמשתמש מתחיל להשתמש בבוט"""
    bot_logger.info("=== New User Started Bot ===")
    user = update.effective_user
    bot_logger.info(f"Chat ID: {update.effective_chat.id}")
    bot_logger.info(f"User: {user.first_name} {user.last_name}")
    bot_logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    await update.message.reply_text(
        f"שלום {user.first_name}! אני הבוט לניהול חנות WooCommerce שלך.\n"
        "אני יכול לעזור לך בניהול מוצרים, הזמנות, לקוחות ועוד.\n"
        "פשוט כתוב/י לי מה את/ה רוצה לעשות בשפה טבעית."
    )

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
    error_logger.error(
        "Exception while handling an update:",
        exc_info=context.error
    )

    # Send message to the user
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "מצטער, אירעה שגיאה בעיבוד הבקשה שלך. אנא נסה שוב."
        )

async def handle_product_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """טיפול בבחירת מוצר לאחר העלאת תמונה"""
    try:
        if not update.message or not update.message.text:
            await update.message.reply_text("אנא שלח את שם המוצר כטקסט")
            return CHOOSING_PRODUCT
            
        product_name = update.message.text.strip()
        
        # Get the temporary photo path from context
        if not context.user_data.get('temp_photo_path'):
            await update.message.reply_text("לא נמצאה תמונה להעלאה. אנא שלח תמונה חדשה")
            return ConversationHandler.END
            
        # Search for the product
        auth_params = {
            'consumer_key': os.getenv('WC_CONSUMER_KEY'),
            'consumer_secret': os.getenv('WC_CONSUMER_SECRET')
        }
        
        search_response = requests.get(
            f"{config['WP_URL']}/wp-json/wc/v3/products",
            params={**auth_params, "search": product_name},
            verify=False
        )
        search_response.raise_for_status()
        products = search_response.json()
        
        if not products:
            await update.message.reply_text(f"לא נמצא מוצר בשם {product_name}")
            return ConversationHandler.END
            
        product = products[0]
        product_id = product["id"]
        
        # Upload the image
        try:
            result = media_handler.upload_product_image(
                product_id,
                context.user_data['temp_photo_path']
            )
            await update.message.reply_text(f"התמונה הועלתה בהצלחה למוצר {product_name}")
        except Exception as e:
            logger.error(f"Error uploading image: {e}")
            await update.message.reply_text(f"שגיאה בהעלאת התמונה: {str(e)}")
        finally:
            # Clean up temporary file
            if os.path.exists(context.user_data['temp_photo_path']):
                os.remove(context.user_data['temp_photo_path'])
            del context.user_data['temp_photo_path']
            
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in handle_product_choice: {e}")
        await update.message.reply_text(f"שגיאה בטיפול בבחירת המוצר: {str(e)}")
        return ConversationHandler.END

def main() -> None:
    """Start the bot."""
    try:
        # Create the Application and pass it your bot's token.
        application = Application.builder().token(config['TELEGRAM_BOT_TOKEN']).build()
        
        # Initialize handlers
        global media_handler, coupon_handler, order_handler, category_handler, customer_handler, inventory_handler
        
        media_handler = MediaHandler(config['WP_URL'], config['WP_USER'], config['WP_PASSWORD'])
        coupon_handler = CouponHandler(config['WP_URL'])
        order_handler = OrderHandler(config['WP_URL'])
        category_handler = CategoryHandler(config['WP_URL'])
        customer_handler = CustomerHandler(config['WP_URL'])
        inventory_handler = InventoryHandler(config['WP_URL'])
        product_handler = ProductHandler(config['WP_URL'])
        settings_handler = SettingsHandler(config['WP_URL'])
        
        bot_logger.info("All handlers initialized successfully")
        
        # Add conversation handler
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", start),
                MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            ],
            states={
                CHOOSING_PRODUCT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_choice)
                ],
            },
            fallbacks=[],
        )
        
        application.add_handler(conv_handler)
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        # Start the Bot
        bot_logger.info("Starting bot...")
        application.run_polling()
        
    except Exception as e:
        error_logger.error(f"Critical error in main: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
