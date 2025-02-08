import os
import base64
from PIL import Image
from io import BytesIO
import logging
from datetime import datetime
from woocommerce import API
import time

logger = logging.getLogger(__name__)

class MediaHandler:
    def __init__(self, wp_url, wp_user, wp_password):
        self.wp_url = wp_url
        self.wcapi = API(
            url=wp_url,
            consumer_key=wp_user,
            consumer_secret=wp_password,
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

    def save_temp_image(self, image_data: bytes, filename_prefix: str = "") -> str:
        """Save image to temporary directory"""
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{filename_prefix}_{timestamp}.jpg" if filename_prefix else f"temp_{timestamp}.jpg"
            filepath = os.path.join(self.temp_dir, filename)
            
            # Save optimized image
            optimized_data = self.optimize_image(image_data)
            with open(filepath, 'wb') as f:
                f.write(optimized_data)
                
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving temporary image: {e}")
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

    def set_product_image(self, product_id: int, image_data: bytes) -> dict:
        """Set product image in WooCommerce using base64 encoding"""
        try:
            # Get current product data
            def get_product():
                response = self.wcapi.get(f"products/{product_id}")
                if response.status_code != 200:
                    raise Exception(f"Failed to get product: {response.text}")
                return response.json()
            
            product = self._retry_operation(get_product)
            logger.debug(f"Got product data for ID {product_id}")
            
            # Convert image to base64
            image_base64 = self._encode_image_base64(image_data)
            logger.debug("Image converted to base64")
            
            # Prepare image data
            image_data = {
                "images": [
                    {
                        "base64": f"data:image/jpeg;base64,{image_base64}",
                        "position": 0
                    }
                ]
            }
            
            # If product has existing images, add them after the new image
            if 'images' in product and product['images']:
                image_data['images'].extend([
                    {"id": img["id"]} for img in product['images']
                ])
            
            # Update product with new image
            def update_product():
                response = self.wcapi.put(f"products/{product_id}", image_data)
                if response.status_code != 200:
                    raise Exception(f"Failed to update product: {response.text}")
                return response.json()
            
            updated_product = self._retry_operation(update_product)
            logger.debug("Product updated with new image")
            
            # Verify the image was added
            if not updated_product.get('images'):
                raise Exception("No images found in updated product")
            
            return updated_product
            
        except Exception as e:
            logger.error(f"Error setting product image: {e}")
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
