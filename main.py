import os
import json
import logging
import requests
import pytz
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from media_handler import MediaHandler
from dotenv import load_dotenv
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain.agents import AgentType, Tool, initialize_agent
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import SystemMessage
import re

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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

# Set timezone
timezone = pytz.timezone('Asia/Jerusalem')

# Store temporary product creation state
product_creation_state = {}

def list_products(_: str = "") -> str:
    """Get list of products from WordPress"""
    try:
        auth_params = {
            'consumer_key': WP_USER,
            'consumer_secret': WP_PASSWORD
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
            
        products_text = "\n".join([f"- {p['name']}: ₪{p.get('price', 'לא זמין')}" for p in products])
        return f"המוצרים בחנות:\n{products_text}"
        
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
            'consumer_key': WP_USER,
            'consumer_secret': WP_PASSWORD
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
            'consumer_key': WP_USER,
            'consumer_secret': WP_PASSWORD
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
            'consumer_key': WP_USER,
            'consumer_secret': WP_PASSWORD
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
            'consumer_key': WP_USER,
            'consumer_secret': WP_PASSWORD
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
            'consumer_key': WP_USER,
            'consumer_secret': WP_PASSWORD
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
            'consumer_key': WP_USER,
            'consumer_secret': WP_PASSWORD
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
llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4")
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
    )
]

# Initialize agent
agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
    memory=memory,
    verbose=True,
    handle_parsing_errors=True,
    system_message=SystemMessage(content="""אתה עוזר וירטואלי שמנהל חנות וורדפרס. 
    אתה יכול לעזור למשתמש בכל הקשור לניהול החנות - הצגת מוצרים, שינוי מחירים, הורדת מבצעים ובדיקת נתוני מכירות.
    אתה מבין עברית ויכול לבצע פעולות מורכבות כמו שינוי מחירים באחוזים.
    
    כשמשתמש מבקש לשנות מחיר:
    - אם הוא מציין מחיר ספציפי (למשל "שנה ל-100 שקל") - השתמש במחיר שצוין
    - אם הוא מבקש להוריד/להעלות באחוזים - חשב את המחיר החדש לפי האחוז
    
    תמיד ענה בעברית ובצורה ידידותית.""")
)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photos."""
    chat_id = update.message.chat_id
    
    try:
        # Get the largest photo size
        photo = update.message.photo[-1]
        logger.debug(f"Received photo with file_id: {photo.file_id}")
        
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
    logger.info(f"Received message from {chat_id}: {user_message}")

    try:
        # Check if we have a pending photo to attach
        if 'temp_photos' in context.user_data and context.user_data['temp_photos']:
            logger.debug("Processing photo attachment request")
            # Send processing message
            processing_message = await context.bot.send_message(
                chat_id=chat_id,
                text="🔄 מעבד את התמונה...\nאנא המתן מספר שניות"
            )

            try:
                # First verify the product exists
                auth_params = {
                    'consumer_key': WP_USER,
                    'consumer_secret': WP_PASSWORD
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
    welcome_message = (
        "שלום! אני בוט שיכול לעזור לך לנהל את אתר הוורדפרס שלך.\n"
        "אתה יכול לבקש ממני דברים כמו:\n\n"
        "ניהול מוצרים:\n"
        "- הצג את רשימת המוצרים\n"
        "- הצג פרטים מלאים על מוצר\n"
        "- צור מוצר חדש (שם | תיאור | מחיר | כמות במלאי)\n"
        "- ערוך פרטי מוצר (שם | שדה לעריכה | ערך חדש)\n"
        "- מחק מוצר\n\n"
        "מחירים ומבצעים:\n"
        "- שנה את המחיר של מוצר\n"
        "- הורד/העלה מחיר באחוזים\n"
        "- הסר מבצע ממוצר\n\n"
        "מידע:\n"
        "- הצג נתוני מכירות"
    )
    await update.message.reply_text(welcome_message)

def main() -> None:
    """Start the bot."""
    logger.info("Initializing bot...")
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the Bot
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
