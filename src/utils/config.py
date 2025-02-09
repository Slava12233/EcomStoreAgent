import os
from typing import Dict, Any
from dotenv import load_dotenv

def load_config() -> Dict[str, Any]:
    """טעינת הגדרות מקובץ .env
    
    Returns:
        מילון עם כל ההגדרות
    """
    # Load .env file
    load_dotenv()
    
    # Required settings
    required_settings = [
        'TELEGRAM_BOT_TOKEN',
        'WP_URL',
        'WP_USER',
        'WP_PASSWORD',
        'WC_CONSUMER_KEY',
        'WC_CONSUMER_SECRET',
        'OPENAI_API_KEY'
    ]
    
    # Check for missing settings
    missing = [key for key in required_settings if not os.getenv(key)]
    if missing:
        raise ValueError(f"Missing required settings: {', '.join(missing)}")
        
    # Return all settings
    return {
        'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
        'WP_URL': os.getenv('WP_URL'),
        'WP_USER': os.getenv('WP_USER'),
        'WP_PASSWORD': os.getenv('WP_PASSWORD'),
        'WC_CONSUMER_KEY': os.getenv('WC_CONSUMER_KEY'),
        'WC_CONSUMER_SECRET': os.getenv('WC_CONSUMER_SECRET'),
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO')
    } 