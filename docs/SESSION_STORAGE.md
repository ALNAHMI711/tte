# تخزين جلسات تسجيل الدخول

## اختيار المخزن وقت التشغيل

أصبح إنشاء خدمة المصادقة يمر عبر `trading.runtime.create_authentication_service`، التي تختار مخزن الجلسات من الإعدادات بدلاً من إنشاء مخزن ذاكرة ضمني في كود التشغيل:

- التطوير: `SESSION_STORE_BACKEND=memory` افتراضياً.
- مضيف إنتاج واحد: `SESSION_STORE_BACKEND=sqlite` مع مسار مطلق ودائم مثل `/var/lib/tte/sessions.sqlite3`.
- عند استخدام SQLite، يجب أن يكون المجلد مملوكاً لمستخدم التطبيق وبصلاحيات مقيدة، وعلى قرص محلي دائم؛ لا تضعه في Git أو مجلد الملفات الثابتة أو NFS.

مثال بناء خدمة المصادقة بعد تحميل بيانات الاعتماد من مزود الأسرار/الهوية:

```python
from trading.auth import UserCredential
from trading.runtime import create_authentication_service

credentials: dict[str, UserCredential] = load_credentials_from_secret_provider()
auth = create_authentication_service(credentials)
```

لا ينشئ المصنع حساب مدير افتراضياً ولا يقرأ كلمات مرور من ملفات عامة. مسؤولية تحميل بيانات الاعتماد تقع على موفر الهوية أو إعداد النشر.

## إعداد الإنتاج

اضبط في بيئة التشغيل:

```dotenv
APP_ENV=production
SESSION_STORE_BACKEND=sqlite
SESSION_STORE_PATH=/var/lib/tte/sessions.sqlite3
SESSION_TTL_SECONDS=3600
SESSION_STEP_UP_SECONDS=300
```

يرفض التحقق إعداد الإنتاج إذا اختير مخزن الذاكرة أو كان مسار SQLite نسبياً/مفقوداً. يلزم تركيب volume دائم للمسار قبل تشغيل التطبيق.

## الحدود المعروفة

- SQLite مناسب لمضيف واحد فقط؛ لا تشارك الملف بين عدة خوادم. عند التوسع إلى عدة مضيفين، يلزم تنفيذ مخزن PostgreSQL/Redis مشترك مع TTL وإبطال ذري.
- محدد محاولات تسجيل الدخول الحالي لا يزال داخل ذاكرة كل عملية؛ لا تعتبره حماية موزعة ضد التخمين حتى نقله إلى مخزن مشترك.
- لا يوجد حالياً ملف تشغيل ASGI يحمّل بيانات اعتماد فعلية أو ينشئ التطبيق تلقائياً؛ يجب أن يستدعي bootstrap النشر المصنع بعد تحميل بيانات الاعتماد من مصدر آمن.
- يلزم إعداد النسخ الاحتياطي والتشفير على مستوى القرص وإدارة الأسرار ومراقبة الوصول قبل الإنتاج.
- لا تفعّل LIVE اعتماداً على نجاح اختبارات الجلسات وحدها.
