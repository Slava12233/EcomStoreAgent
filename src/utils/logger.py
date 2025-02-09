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
    
    # Create handlers for different log types
    handlers = {
        'bot': RotatingFileHandler(
            'logs/bot.log',
            maxBytes=5*1024*1024,  # 5MB
            backupCount=5,
            encoding='utf-8'
        ),
        'debug': RotatingFileHandler(
            'logs/debug.log',
            maxBytes=5*1024*1024,
            backupCount=5,
            encoding='utf-8'
        ),
        'user': RotatingFileHandler(
            'logs/user_actions.log',
            maxBytes=5*1024*1024,
            backupCount=5,
            encoding='utf-8'
        ),
        'error': RotatingFileHandler(
            'logs/errors.log',
            maxBytes=5*1024*1024,
            backupCount=5,
            encoding='utf-8'
        ),
        'console': logging.StreamHandler()
    }
    
    # Configure handlers
    for handler in handlers.values():
        handler.setFormatter(file_formatter if isinstance(handler, RotatingFileHandler) else console_formatter)
    
    # Set levels
    handlers['bot'].setLevel(logging.INFO)
    handlers['debug'].setLevel(logging.DEBUG)
    handlers['user'].setLevel(logging.INFO)
    handlers['error'].setLevel(logging.ERROR)
    handlers['console'].setLevel(logging.WARNING)
    
    # Add handlers
    for handler in handlers.values():
        logger.addHandler(handler)
    
    # Disable other loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('langchain').setLevel(logging.WARNING)
    
    return logger

# Create dedicated loggers
bot_logger = setup_logger('bot_events')
user_logger = setup_logger('user_actions')
error_logger = setup_logger('errors')
debug_logger = setup_logger('debug') 