# Bump House — نظام إدارة أعضاء الجيم

## تشغيل المشروع محلياً

```bash
# 1. إنشاء البيئة الافتراضية
python -m venv venv
source venv/bin/activate       # Mac/Linux
# venv\Scripts\activate        # Windows

# 2. تثبيت المكتبات
pip install -r requirements.txt

# 3. نسخ ملف الإعدادات
cp .env.example .env
# عدّل .env وحط SECRET_KEY قوي

# 4. تشغيل التطبيق
python app.py
# افتح المتصفح على http://localhost:5000
```

> ملاحظة: بدون DATABASE_URL في .env، التطبيق هيشتغل على SQLite تلقائياً (مناسب للتطوير)

---

## الرفع على Render (مجاناً)

### 1. أنشئ حساب على Supabase (للداتابيز)
- اذهب إلى https://supabase.com وأنشئ مشروع جديد
- من Project Settings → Database → اضغط "Connect"
- انسخ الـ Connection String (URI)
- في الـ URI استبدل `[YOUR-PASSWORD]` بكلمة السر

### 2. ارفع الكود على GitHub
```bash
git init
git add .
git commit -m "first commit"
git remote add origin https://github.com/USERNAME/bump-house.git
git push -u origin main
```

### 3. ارفع على Render
- اذهب إلى https://render.com
- New → Web Service → اربط الـ GitHub repo
- Environment Variables أضف:
  - `DATABASE_URL` = الـ connection string من Supabase
  - `SECRET_KEY` = أي كلمة سر طويلة

### 4. UptimeRobot (عشان الموقع ميناموش)
- اذهب إلى https://uptimerobot.com
- New Monitor → HTTP
- الرابط = رابط موقعك على Render
- Interval = كل 14 دقيقة

---

## الصفحات
- `/` — الداشبورد الرئيسي
- `/add` — إضافة عضو جديد
- `/member/<id>` — تفاصيل العضو + تجديد + حذف
- `/api/expiring` — API بيرجع الأعضاء القرب اشتراكهم ينتهي

## ألوان الحالة
- 🟢 **تمام** — باقي أكتر من 7 أيام
- 🟡 **قرب يخلص** — باقي 7 أيام أو أقل
- 🔴 **خلص** — اشتراك منتهي
