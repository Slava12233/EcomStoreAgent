import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logger(name: str = None, level: str = "INFO") -> logging.Logger:
    """הגדרת לוגר עם רוטציה של קבצים
    
    Args:
        name: שם הלוגר (ברירת מחדל: שם המודול)
        level: רמת הלוג (ברירת מחדל: INFO)
    """
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
        
    # Get logger
    logger = logging.getLogger(name)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Set level
    level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(level)
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    
    # File handler with rotation - for all levels
    file_handler = RotatingFileHandler(
        f'logs/bot.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Debug file handler - for DEBUG level only
    debug_handler = RotatingFileHandler(
        f'logs/debug.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    debug_handler.setFormatter(file_formatter)
    debug_handler.setLevel(logging.DEBUG)
    
    # Console handler - for WARNING and above only
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.WARNING)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(debug_handler)
    logger.addHandler(console_handler)
    
    # Disable other loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    
    return logger 