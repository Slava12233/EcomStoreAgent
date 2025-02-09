import os
import base64
from PIL import Image
from io import BytesIO
import logging
from datetime import datetime
from woocommerce import API
import time
import requests
from dotenv import load_dotenv
import mimetypes

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class MediaHandler:
    def __init__(self, wp_url, wp_user, wp_password):
        self.wp_url = wp_url
        # Store WordPress credentials for media uploads
        self.wp_user = wp_user
        self.wp_password = wp_password
        
        # Initialize WooCommerce API with WooCommerce API keys
        wc_key = os.getenv('WC_CONSUMER_KEY')
        wc_secret = os.getenv('WC_CONSUMER_SECRET')
        
        if not wc_key or not wc_secret:
            raise ValueError("WooCommerce API keys not found in environment")
            
        logger.debug(f"Initializing WooCommerce API with URL: {wp_url}")
        self.wcapi = API(
            url=wp_url,
            consumer_key=wc_key,
            consumer_secret=wc_secret,
            version="wc/v3",
            timeout=30
        )
        
        self.temp_dir = 'temp_media'
        os.makedirs(self.temp_dir, exist_ok=True)
        
    def _retry_operation(self, operation, max_retries=3, delay=1):
        """Retry an operation with exponential backoff"""
        last_error = None
        for attempt in range(max_retries):
            try:
                return operation()
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    sleep_time = delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
        raise last_error

    def optimize_image(self, image_data: bytes, max_size: tuple = (800, 800)) -> bytes:
        """Optimize image size and quality"""
        try:
            # Open image from bytes
            img = Image.open(BytesIO(image_data))
            
            # Convert to RGB if needed
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize if larger than max_size while maintaining aspect ratio
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save optimized image to bytes
            output = BytesIO()
            img.save(output, format='JPEG', quality=85, optimize=True)
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error optimizing image: {e}")
            return image_data

    def save_temp_image(self, image_data: bytes, prefix: str = "temp") -> str:
        """Save image data to a temporary file"""
        try:
            logger.debug(f"Saving temporary image with prefix: {prefix}")
            
            # Create temp directory if it doesn't exist
            if not os.path.exists(self.temp_dir):
                logger.debug(f"Creating temp directory: {self.temp_dir}")
                os.makedirs(self.temp_dir)
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}.jpg"
            temp_path = os.path.join(self.temp_dir, filename)
            
            logger.debug(f"Writing image data to: {temp_path}")
            
            # Write image data to file
            with open(temp_path, 'wb') as f:
                f.write(image_data)
            
            logger.debug(f"Image saved successfully to: {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Error saving temporary image: {str(e)}")
            raise

    def _encode_image_base64(self, image_data: bytes) -> str:
        """Convert image data to base64 string"""
        try:
            # Optimize image first
            optimized_data = self.optimize_image(image_data)
            # Convert to base64
            return base64.b64encode(optimized_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encoding image to base64: {e}")
            raise

    def upload_media(self, file_path: str) -> dict:
        """Upload media to WordPress"""
        try:
            logger.debug(f"Starting media upload for file: {file_path}")
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Get file details
            filename = os.path.basename(file_path)
            mime_type, _ = mimetypes.guess_type(file_path)
            
            if not mime_type:
                mime_type = 'image/jpeg'  # Default to JPEG if can't determine
            
            logger.debug(f"File details - Name: {filename}, MIME: {mime_type}")
            
            # Prepare the files for upload
            with open(file_path, 'rb') as img:
                files = {
                    'file': (filename, img, mime_type)
                }
                
                # Use WordPress credentials for media upload
                auth = (self.wp_user, self.wp_password)
                
                logger.debug("Sending media upload request to WordPress")
                response = requests.post(
                    f"{self.wp_url}/wp-json/wp/v2/media",
                    files=files,
                    auth=auth,
                    verify=False
                )
                
                if response.status_code != 201:
                    logger.error(f"Media upload failed. Status: {response.status_code}, Response: {response.text}")
                    raise Exception(f"Failed to upload media: {response.text}")
                
                logger.debug("Media upload successful")
                return response.json()
                
        except Exception as e:
            logger.error(f"Error in upload_media: {str(e)}")
            raise

    def set_product_image(self, product_id: int, image_data: bytes) -> dict:
        """Set product image using WooCommerce API"""
        try:
            logger.debug(f"Starting image upload process for product {product_id}")
            
            # Save image to temporary file
            temp_path = self.save_temp_image(image_data, f"product_{product_id}")
            logger.debug(f"Image saved to temporary file: {temp_path}")
            
            try:
                # Upload image to WordPress
                logger.debug("Uploading image to WordPress media library")
                media = self.upload_media(temp_path)
                logger.debug(f"Media uploaded successfully: {media}")
                
                if not media or 'id' not in media:
                    raise Exception("Failed to get media ID from upload response")
                
                # Update product with new image using WooCommerce API
                update_data = {
                    "images": [
                        {
                            "id": media.get('id'),
                            "src": media.get('source_url'),
                            "position": 0
                        }
                    ]
                }
                
                logger.debug(f"Updating product {product_id} with image data: {update_data}")
                response = self.wcapi.put(f"products/{product_id}", update_data)
                
                if response.status_code != 200:
                    logger.error(f"Failed to update product. Status: {response.status_code}, Response: {response.text}")
                    raise Exception(f"Failed to update product: {response.text}")
                
                logger.debug("Product updated successfully with new image")
                return response.json()
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.debug(f"Temporary file removed: {temp_path}")
                    
        except Exception as e:
            logger.error(f"Error setting product image: {str(e)}")
            raise

    def get_product_images(self, product_id: int) -> list:
        """Get all images for a product"""
        try:
            def get_product():
                response = self.wcapi.get(f"products/{product_id}")
                if response.status_code != 200:
                    raise Exception(f"Failed to get product: {response.text}")
                return response.json()
            
            product = self._retry_operation(get_product)
            return product.get('images', [])
            
        except Exception as e:
            logger.error(f"Error getting product images: {e}")
            raise

    def delete_product_image(self, product_id: int, image_id: int) -> dict:
        """Delete an image from a product"""
        try:
            # Get current product data
            def get_product():
                response = self.wcapi.get(f"products/{product_id}")
                if response.status_code != 200:
                    raise Exception(f"Failed to get product: {response.text}")
                return response.json()
            
            product = self._retry_operation(get_product)
            
            # Filter out the image to delete
            new_images = [img for img in product.get('images', []) if img['id'] != image_id]
            
            # Update product with new image list
            def update_product():
                response = self.wcapi.put(f"products/{product_id}", {
                    "images": new_images
                })
                if response.status_code != 200:
                    raise Exception(f"Failed to update product: {response.text}")
                return response.json()
            
            updated_product = self._retry_operation(update_product)
            logger.debug(f"Removed image {image_id} from product {product_id}")
            
            return updated_product
            
        except Exception as e:
            logger.error(f"Error deleting product image: {e}")
            raise

    def cleanup_temp_files(self):
        """Clean up temporary media files"""
        try:
            for filename in os.listdir(self.temp_dir):
                filepath = os.path.join(self.temp_dir, filename)
                if os.path.isfile(filepath):
                    os.remove(filepath)
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e}")
