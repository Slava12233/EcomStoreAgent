# WordPress AI Agent

A Telegram bot that enables natural language management of a WooCommerce WordPress store in Hebrew.

## Features

- 🤖 Natural language processing in Hebrew
- 🏪 Complete WooCommerce integration
- 📦 Product management
- 🛍️ Order processing
- 👥 Customer management
- 🏷️ Coupon handling
- 📁 Category organization
- 📊 Inventory tracking
- 🚢 Shipping management (coming soon)
- ⚙️ Store settings (coming soon)

See [CAPABILITIES.md](CAPABILITIES.md) for a detailed feature list.

## Requirements

- Python 3.8+
- WordPress site with WooCommerce
- Telegram Bot Token (from BotFather)
- OpenAI API Key
- WooCommerce API credentials

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/wordpress-ai-agent.git
cd wordpress-ai-agent
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file with your credentials:
```env
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key
WP_URL=your_wordpress_url
WP_USER=your_wordpress_username
WP_PASSWORD=your_wordpress_password
WC_CONSUMER_KEY=your_woocommerce_key
WC_CONSUMER_SECRET=your_woocommerce_secret
```

## Usage

1. Start the bot:
```bash
python src/main.py
```

2. Open Telegram and search for your bot

3. Send `/start` to see available commands

4. Try some example commands:
- "הצג את רשימת המוצרים"
- "עדכן מחיר למוצר X ל-100 שקלים"
- "צור קופון הנחה של 20 אחוז"
- "מה המכירות שלי"

## Project Structure

```
wordpress-ai-agent/
├── src/
│   ├── handlers/
│   │   ├── media_handler.py
│   │   ├── coupon_handler.py
│   │   ├── order_handler.py
│   │   ├── category_handler.py
│   │   ├── customer_handler.py
│   │   ├── inventory_handler.py
│   │   ├── product_handler.py
│   │   └── settings_handler.py
│   ├── utils/
│   │   ├── logger.py
│   │   └── config.py
│   └── main.py
├── logs/
│   ├── bot.log
│   └── debug.log
├── .env
├── requirements.txt
├── README.md
└── CAPABILITIES.md
```

## Logging

The bot uses a comprehensive logging system:
- `logs/bot.log`: General operation logs
- `logs/debug.log`: Detailed debug information, including LLM communication
- `logs/user_actions.log`: User interaction logs
- `logs/errors.log`: Error tracking and debugging
- Console output: Warnings and errors only

Features:
- Automatic log rotation (5MB max size, 5 backup files)
- Detailed LLM communication tracking
- Suppressed external library logs
- Clean console output

## Development

- Follow the guidelines in `.cursorrules`