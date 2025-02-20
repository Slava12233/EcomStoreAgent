# יכולות סוכן ניהול החנות

## סקירה כללית
הסוכן הוא בוט טלגרם המאפשר ניהול חנות WooCommerce באמצעות שפה טבעית בעברית. הסוכן משתמש ב-OpenAI GPT-4 כדי להבין את בקשות המשתמש ולבצע פעולות מתאימות בחנות.

## יכולות נוכחיות

### 1. ניהול מוצרים
#### הצגת מוצרים
- הצגת רשימת כל המוצרים בחנות
- הצגת פרטים מלאים על מוצר ספציפי
- הצגת תמונות של מוצר

#### עריכת מוצרים
- יצירת מוצר חדש עם:
  - שם
  - תיאור
  - מחיר
  - כמות במלאי (אופציונלי)
- עריכת פרטי מוצר קיים:
  - שם
  - תיאור
  - מחיר
  - כמות במלאי
- מחיקת מוצר מהחנות

### 2. ניהול מחירים ומבצעים
- עדכון מחיר מוצר למחיר ספציפי
- שינוי מחיר באחוזים (הנחה או העלאה)
- הסרת מבצעים/הנחות ממוצר

### 3. ניהול תמונות
- העלאת תמונות חדשות למוצר
- תמיכה במגוון פורמטים של תמונות
- אופטימיזציה אוטומטית של תמונות לפני העלאה
- מחיקת תמונות מוצר

### 4. מעקב מכירות
- הצגת נתוני מכירות כלליים
- הצגת סך המכירות

### 5. ניהול קופונים
- יצירת קופון חדש עם:
  - קוד קופון
  - סוג הנחה (אחוזים או סכום קבוע)
  - סכום ההנחה
  - תיאור (אופציונלי)
  - תאריך תפוגה (אופציונלי)
  - סכום מינימלי להזמנה (אופציונלי)
  - סכום מקסימלי להנחה (אופציונלי)
- הצגת כל הקופונים הפעילים
- עריכת קופונים קיימים
- מחיקת קופונים

### 6. תכונות נוספות
- תמיכה מלאה בעברית
- הודעות שגיאה ידידותיות למשתמש
- לוגים מפורטים לצורכי דיבוג
- טיפול בשגיאות חכם

### 7. ניהול קטגוריות
- הצגת רשימת כל הקטגוריות בחנות
- יצירת קטגוריה חדשה עם:
  - שם
  - תיאור
  - קטגוריית אב (אופציונלי)
- עריכת פרטי קטגוריה קיימת:
  - שם
  - תיאור
  - קטגוריית אב
- מחיקת קטגוריה
- שיוך מוצרים לקטגוריות

## 4. ניהול הזמנות
הבוט מאפשר ניהול מלא של הזמנות בחנות, כולל:

### 4.1 הצגת רשימת הזמנות
- הצגת כל ההזמנות במערכת
- אפשרות לסינון לפי סטטוס
- מוצג: מספר הזמנה, סטטוס, סכום, תאריך ושם הלקוח

דוגמאות:
```
הצג את כל ההזמנות
הצג הזמנות בסטטוס בטיפול
```

### 4.2 צפייה בפרטי הזמנה
- הצגת פרטים מלאים על הזמנה ספציפית
- כולל: פרטי לקוח, כתובת למשלוח, פריטים, הערות מנהל

דוגמאות:
```
הצג פרטים על הזמנה 123
מה הפרטים של הזמנה 456
```

### 4.3 עדכון סטטוס הזמנה
- עדכון סטטוס הזמנה (בטיפול, הושלם, בוטל וכו')
- תמיכה בכל הסטטוסים הסטנדרטיים של WooCommerce

דוגמאות:
```
עדכן סטטוס הזמנה 123 ל-completed
שנה את הזמנה 456 לסטטוס בטיפול
```

### 4.4 יצירת הזמנה חדשה
- יצירת הזמנה חדשה עם פרטים מלאים:
  - פרטי לקוח (שם, טלפון, אימייל)
  - כתובת למשלוח
  - רשימת מוצרים וכמויות
  - שיטת משלוח (אופציונלי)

דוגמאות:
```
צור הזמנה חדשה: ישראל | ישראלי | israel@example.com | 0501234567 | רחוב הרצל 1 | תל אביב | 6123456 | 123:2,456:1
צור הזמנה: דוד | כהן | david@example.com | 0509876543 | דרך מנחם בגין 132 | תל אביב | 6701101 | 789:1 | משלוח רגיל
```

### 4.5 חיפוש הזמנות
- חיפוש הזמנות לפי פרמטרים שונים:
  - חיפוש לפי מזהה לקוח
  - חיפוש לפי סטטוס
  - חיפוש לפי תאריך או טווח תאריכים
  - חיפוש חופשי

דוגמאות:
```
חפש הזמנות של לקוח:123
חפש הזמנות בסטטוס:completed
חפש הזמנות בתאריך:2024-03-01
חפש הזמנות בתאריך:2024-03-01-2024-03-31
```

## דוגמאות לשימוש

### ניהול מוצרים
```
- "הצג את כל המוצרים בחנות"
- "הראה לי פרטים על המוצר X"
- "צור מוצר חדש: שם | תיאור | 100 שקל | 50 יחידות"
- "ערוך את המוצר X: מחיר | 150"
- "מחק את המוצר X"
```

### מחירים ומבצעים
```
- "שנה את המחיר של X ל-200 שקל"
- "הורד את המחיר של X ב-20%"
- "הסר את המבצע מהמוצר X"
```

### תמונות
```
- שליחת תמונה בצ'אט ובחירת המוצר אליו לשייך אותה
- "מחק את התמונה הראשונה של המוצר X"
```

### מכירות
```
- "כמה מכירות היו החודש?"
- "הצג את נתוני המכירות"
```

### קופונים
```
- "צור קופון חדש: SUMMER2024 | percent | 10 | קופון קיץ 2024 | 2024-09-01"
- "הצג את כל הקופונים"
- "ערוך את הקופון WELCOME: סכום | 50"
- "מחק את הקופון SUMMER2024"
```

### קטגוריות
```
- "הצג את כל הקטגוריות"
- "צור קטגוריה חדשה: בגדי ילדים | בגדים לילדים ותינוקות"
- "צור קטגוריה: אביזרים | אביזרי אופנה | בגדים"
- "עדכן קטגוריה: בגדי ילדים | תיאור | בגדים איכותיים לילדים ותינוקות"
- "מחק קטגוריה: בגדי ילדים"
- "הכנס את המוצר חולצת כותנה לקטגוריה בגדי ילדים"
- "שייך מוצר לקטגוריה: מכנס ארוך נייק | מוצרים לגברים"
```

## אבטחה
- שימוש ב-API keys נפרדים ל-WooCommerce ול-WordPress
- אחסון מאובטח של מפתחות API בקובץ `.env`
- הרשאות מוגבלות לפי סוג הפעולה

## מגבלות ידועות
1. אין תמיכה בניהול הזמנות
2. אין תמיכה בניהול לקוחות
3. אין תמיכה בניהול קטגוריות
4. אין אפשרות לייצא/לייבא מוצרים בכמות
5. אין תמיכה בניהול מלאי מתקדם
6. אין תמיכה בניהול שילוח
7. אין אפשרות לנהל הגדרות חנות 

## ניהול לקוחות בחנות

הבוט מאפשר ניהול מלא של לקוחות החנות, כולל:

### יצירת לקוח חדש
ניתן ליצור לקוח חדש במגוון דרכים:
- `צור לקוח חדש: ישראל | ישראלי | israel@example.com | 0501234567 | רחוב הרצל 1 | תל אביב | 6123456`
- `הוסף לקוח: דוד | כהן | david@example.com`
- `תרשום בבקשה לקוח חדש - שם פרטי הוא דוד שם משפחה כהן ואימייל david@example.com`
- `אני רוצה להוסיף לקוח חדש למערכת. קוראים לו דוד כהן והמייל שלו הוא david@example.com`

הבוט יזהה אוטומטית את הפרטים הנדרשים מהטקסט החופשי:
- שם פרטי ושם משפחה (חובה)
- אימייל (חובה)
- טלפון (אופציונלי)
- כתובת מלאה (אופציונלי)

### הצגת רשימת לקוחות
- `הצג את כל הלקוחות`
- `מי הלקוחות שלי?`
- `תראה לי את רשימת הלקוחות`

### הצגת פרטי לקוח
- `הצג פרטים על הלקוח דוד כהן`
- `מה הפרטים של david@example.com`
- `תראה לי את כל המידע על הלקוח ישראל ישראלי`

### עדכון פרטי לקוח
- `עדכן את הטלפון של דוד כהן ל-0501234567`
- `שנה את הכתובת של david@example.com לרחוב הרצל 1 תל אביב`
- `עדכן את האימייל של ישראל ישראלי ל-new.email@example.com`

### חיפוש לקוחות
- `חפש לקוח לפי אימייל david@example.com`
- `מצא את כל הלקוחות עם השם דוד`
- `חפש לקוחות מתל אביב`

## ניהול מלאי מתקדם

הבוט מאפשר ניהול מלאי מתקדם עם תכונות מיוחדות:

### התראות מלאי נמוך
- הגדרת סף התראה לכל מוצר
- קבלת רשימת מוצרים עם מלאי נמוך
- התראות אוטומטיות כשמוצר מגיע לסף המלאי

דוגמאות:
```
הגדר סף מלאי נמוך: חולצת כותנה | 5
הצג מוצרים במלאי נמוך
```

### עדכון מלאי
- עדכון כמות מלאי למוצר
- הוספה או הפחתה מהמלאי הקיים
- קבלת סטטוס מלאי מפורט

דוגמאות:
```
עדכן מלאי: חולצת כותנה | 50
הוסף למלאי: חולצת כותנה | 10
הורד מהמלאי: חולצת כותנה | 5
הצג סטטוס מלאי: חולצת כותנה
```

### ניהול מלאי לפי מאפיינים
- ניהול מלאי נפרד לכל וריאציה של המוצר
- תמיכה במאפיינים כמו צבע, מידה וכו'
- מעקב אחר מלאי לכל שילוב של מאפיינים

דוגמאות:
```
עדכן מלאי לפי מאפיינים: חולצת כותנה
צבע: אדום | 5
צבע: כחול | 3
מידה: S | 2
מידה: M | 4
מידה: L | 1
```

### דוחות מלאי
- דוח מלאי כללי
- דוח מוצרים במלאי נמוך
- דוח תנועות מלאי

דוגמאות:
```
הצג דוח מלאי
הצג דוח מלאי נמוך
הצג תנועות מלאי: חולצת כותנה
```

## ניהול מלאי מתקדם

הבוט תומך במגוון פעולות לניהול מלאי מתקדם:

### הצגת מוצרים במלאי נמוך

מציג רשימה של כל המוצרים שכמות המלאי שלהם נמוכה מהסף שהוגדר.

דוגמאות:
```
- הצג מוצרים במלאי נמוך
- אילו מוצרים עומדים להיגמר
- מה המצב של המלאי
```

### עדכון כמות מלאי

מאפשר עדכון כמות המלאי של מוצר בשלוש דרכים:
- קביעת כמות מדויקת
- הוספת כמות למלאי הקיים
- הורדת כמות מהמלאי הקיים

פורמט: `שם מוצר | פעולה | כמות`

דוגמאות:
```
- חולצה כחולה | set | 50
- מכנסיים שחורים | add | 20
- נעלי ספורט | subtract | 5
```

### הצגת סטטוס מלאי מפורט

מציג מידע מפורט על מצב המלאי של מוצר ספציפי, כולל:
- כמות במלאי
- האם ניהול מלאי פעיל
- סטטוס מלאי (במלאי/אזל/בהזמנה מראש)
- האם מותרות הזמנות מראש
- סף התראה למלאי נמוך

דוגמאות:
```
- מה המצב של חולצה כחולה
- הראה לי את המלאי של מכנסיים שחורים
- כמה יש במלאי מנעלי ספורט
```

### ניהול מלאי לפי מאפיינים

מאפשר ניהול מלאי מפורט לפי מאפייני המוצר (כמו צבע, מידה וכו').
יש להזין את שם המוצר בשורה הראשונה, ואחריו את המאפיינים והכמויות בפורמט:
`מאפיין: ערך | כמות`

דוגמאות:
```
חולצה כחולה
צבע: כחול | 20
מידה: M | 15
מידה: L | 25

מכנסיים שחורים
צבע: שחור | 30
מידה: 32 | 10
מידה: 34 | 15
מידה: 36 | 20
```

### הגדרת סף התראה למלאי נמוך

מאפשר להגדיר את הכמות המינימלית במלאי שתגרום להתראה על מלאי נמוך.

פורמט: `שם מוצר | סף התראה`

דוגמאות:
```
- חולצה כחולה | 10
- מכנסיים שחורים | 15
- נעלי ספורט | 5
```

### הערות חשובות

1. **פורמט אחיד**: בפקודות מורכבות נעשה שימוש בתו | (מקף אנכי) כמפריד בין שדות.
2. **תמיכה בעברית**: כל הפקודות תומכות בטקסט חופשי בעברית.
3. **שגיאות**: במקרה של שגיאה, יוצג הסבר מפורט בעברית על הבעיה.
4. **לוגים**: כל פעולות המלאי נרשמות בלוג המערכת לצורך מעקב ובקרה. 

# WordPress AI Agent Capabilities

## Core Features

### Natural Language Processing
- Full Hebrew language support for all commands and responses
- Intelligent parsing of free-text input for customer details
- Flexible command formats with multiple variations
- Context-aware conversations

### Product Management
- List all products with detailed information
- Create new products with multiple attributes
- Update product details (price, stock, description)
- Remove discounts and special offers
- Upload and manage product images
- Search products by name or attributes

### Order Management
- View all orders with filtering options
- Get detailed order information
- Update order status
- Search orders by various parameters
- Create new orders with multiple items

### Customer Management
- List all customers with purchase history
- View detailed customer information
- Update customer details
- Search customers by name or email
- Create new customers with smart detail extraction
- Automatic email and phone number validation

### Coupon Management
- Create new coupons with various conditions
- List active coupons
- Update coupon details
- Delete expired coupons
- Set usage restrictions

### Category Management
- Create new categories and subcategories
- Update category details
- Delete empty categories
- Assign products to categories
- View category hierarchy

### Inventory Management
- Track stock levels
- Set low stock alerts
- Update stock quantities
- Manage stock by attributes (size, color, etc.)
- View detailed stock status

## Technical Features

### Logging System
- Rotating log files with size limits
- Separated logs by severity level
- Detailed debug logging
- Clean console output
- External library log management

### Security
- Secure API credential management
- Input validation and sanitization
- Error handling for sensitive operations
- Audit logging for important actions

### Code Structure
- Modular handler-based architecture
- Clean separation of concerns
- Consistent error handling
- Comprehensive documentation
- Type hints and validation

### Development Tools
- Automated testing support
- Development environment setup
- Debugging capabilities
- Performance monitoring

## Upcoming Features

### Shipping Management
- Define shipping zones
- Set shipping rates
- Track shipments
- Manage shipping methods

### Store Settings
- Update basic store information
- Configure tax settings
- Manage payment options
- Set store preferences 