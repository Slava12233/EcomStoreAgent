# WordPress AI Agent

בוט טלגרם לניהול חנות WooCommerce בעברית באמצעות בינה מלאכותית.

## תכונות

- ניהול מוצרים (הצגה, עריכה, מחיקה)
- עדכון מחירים וניהול מבצעים
- העלאת וניהול תמונות מוצרים
- ניהול קופונים
- ניהול הזמנות
- ממשק משתמש בעברית
- עיבוד שפה טבעית באמצעות GPT-4

## התקנה

1. שכפל את המאגר:
```bash
git clone https://github.com/yourusername/wordpress-ai-agent.git
cd wordpress-ai-agent
```

2. צור והפעל סביבה וירטואלית:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# או
.\venv\Scripts\activate  # Windows
```

3. התקן את התלויות:
```bash
pip install -r requirements.txt
```

4. העתק את קובץ `.env.example` ל-`.env` ומלא את הפרטים הנדרשים:
```bash
cp .env.example .env
```

## מבנה הפרויקט

```
wordpress-ai-agent/
├── src/                    # קוד המקור
│   ├── handlers/          # מחלקות הטיפול השונות
│   │   ├── media_handler.py
│   │   ├── coupon_handler.py
│   │   └── order_handler.py
│   └── main.py
├── logs/                   # קבצי לוג
├── temp_media/             # קבצי מדיה זמניים
├── tests/                  # בדיקות
├── .env                    # הגדרות
├── .env.example           # דוגמה להגדרות
├── requirements.txt        # תלויות
└── README.md              # תיעוד
```

## הפעלה

```bash
cd src
python main.py
```

## הגדרות נדרשות ב-.env

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token

# WordPress
WP_URL=https://your-store.com
WP_USER=your_username
WP_PASSWORD=your_password

# WooCommerce
WC_CONSUMER_KEY=your_consumer_key
WC_CONSUMER_SECRET=your_consumer_secret

# OpenAI
OPENAI_API_KEY=your_openai_api_key
```

## רישיון

MIT License 