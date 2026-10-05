# تشغيل التطبيق والمصادقة

## نقطة التشغيل

نقطة ASGI هي `trading.bootstrap:application`. تقوم عند بدء التطبيق بـ:

1. قراءة إعدادات التشغيل.
2. قراءة `ADMIN_USER_ID` و`ADMIN_PASSWORD_HASH` من بيئة التشغيل.
3. إنشاء `AuthenticationService` عبر مصنع الجلسات.
4. إنشاء FastAPI control plane.

لا تُقرأ كلمة مرور المدير كنص صريح من البيئة، ولا ينشئ النظام حساباً افتراضياً.

## الإنتاج

يجب توفير:

```dotenv
APP_ENV=production
SESSION_STORE_BACKEND=sqlite
SESSION_STORE_PATH=/var/lib/tte/sessions.sqlite3
ADMIN_USER_ID=admin
ADMIN_PASSWORD_HASH=<argon2id-hash-from-secret-manager>
```

إذا كانت بيانات اعتماد المدير ناقصة في الإنتاج، يفشل bootstrap بدلاً من تشغيل لوحة تحكم بلا هوية إدارية.

## تشغيل ASGI

مثال:

```bash
uvicorn trading.bootstrap:application --host 0.0.0.0 --port 8000
```

في بيئة الإنتاج يجب تشغيله خلف HTTPS reverse proxy، مع volume دائم لـ SQLite، ومصدر أسرار مناسب. لا تضع hash الحقيقي في Git.

لا يزال محدد محاولات تسجيل الدخول داخل ذاكرة العملية، لذلك هذه الخطوة لا تجعل rate limiting موزعاً بين عدة خوادم.
