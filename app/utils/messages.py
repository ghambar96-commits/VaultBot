"""User-facing strings (Persian). Kept in one place so a future multi-language
mode only needs another dict like this."""

from __future__ import annotations

HELP = """🤖 <b>VaultBot</b> — صندوقچهٔ هوشمند شما

هر چیزی بفرستید، ذخیره می‌شود: متن، لینک، عکس، فایل، صدا، ویدیو، استیکر و پیام فورواردی.
فایل‌ها روی سرور ذخیره <b>نمی‌شوند</b>؛ فقط مرجع آن‌ها در دیتابیس ثبت می‌شود.

📥 <b>ذخیره:</b> فقط هر پیامی را همینجا بفرستید.
🔎 <code>/search متن</code> — جستجو در همهٔ آیتم‌ها
📁 <code>/folders</code> — پوشه‌ها | <code>/newfolder نام</code> — پوشهٔ جدید
🏷 <code>/tag [آیتم] #تگ…</code> — افزودن تگ | <code>/tags</code> — همهٔ تگ‌ها
📝 <code>/note [آیتم] متن</code> — یادداشت روی آیتم
📦 <code>/move</code> — جابه‌جایی آیتم به پوشه
⏰ <code>/remind +2h</code> یا <code>/remind فردا 08:00</code> — یادآور روی آخرین آیتم
🗑 <code>/delete [آیتم]</code> | ♻️ <code>/restore [آیتم]</code>
📊 <code>/stats</code> — آمار | ⚙️ <code>/settings</code> — تنظیمات
💾 <code>/backup</code> — پشتیبان‌گیری از دیتابیس

عدد آیتم را در صفحهٔ جزئیات هر آیتم می‌بینید."""

START = """👋 سلام! من <b>VaultBot</b> هستم — نسخهٔ پیشرفتهٔ Saved Messages.

هر چیزی بفرستید (متن، لینک، عکس، فایل…) آن را ذخیره، قابل جستجو و قابل مدیریت می‌کنم.

برای شروع /help را ببینید."""

DUPLICATE = "⚠️ این فایل قبلاً ذخیره شده بود (<b>#{id}</b>)؛ نسخهٔ تکراری ذخیره نشد."

FAV_ON = "⭐ به علاقه‌مندی‌ها اضافه شد."
FAV_OFF = "☆ از علاقه‌مندی‌ها حذف شد."
RECENT = "🕓 آخرین آیتم‌های شما ({total} مورد):"
FAVORITES = "⭐ علاقه‌مندی‌های شما ({total} مورد):"
NO_FAVORITES = "هنوز آیتمی را ستاره‌دار نکرده‌اید. از دکمهٔ ⭐ در صفحهٔ هر آیتم استفاده کنید."
RANDOM = "🎲 یک آیتم تصادفی:"

EMPTY_QUERY = "🔎 چه چیزی را جستجو کنم؟ مثال:\n<code>/search linux</code>"
NO_RESULTS = "😕 چیزی پیدا نشد."
RESULTS = "🔎 نتایج «{q}» — {total} مورد:"

TAG_UPDATED = "🏷 تگ‌های آیتم <b>#{id}</b> به‌روز شد:\n{tags}"
TAG_AI_ADDED = "🤖 تگ‌های پیشنهادی برای آیتم <b>#{id}</b> اضافه شد:\n{tags}"
TAG_EMPTY = "تگی مشخص نشد. مثال: <code>/tag 5 #python</code>"
TAGS_LIST = "🏷 تگ‌های شما:\n{tags}"
NO_TAGS = "هنوز تگی ندارید. با <code>/tag</code> اضافه کنید."

FOLDER_CREATED = "📁 پوشهٔ «{name}» ساخته شد."
FOLDER_EXISTS = "پوشه‌ای با این نام از قبل دارید."
FOLDER_ASK = "نام پوشهٔ جدید را بفرستید (یا /cancel):"
FOLDERS_LIST = "📁 پوشه‌های شما:\n{items}"
NO_FOLDERS = "هنوز پوشه‌ای نساخته‌اید. با /newfolder شروع کنید."
MOVED = "📦 آیتم <b>#{id}</b> به «{folder}» منتقل شد."
MOVED_NONE = "📦 آیتم <b>#{id}</b> از پوشه خارج شد."

NOTE_SAVED = "📝 یادداشت برای آیتم <b>#{id}</b> ذخیره شد."
NOTE_ASK = "یادداشت را برای آیتم <b>#{id}</b> بفرستید (یا /cancel):"
NOTE_EMPTY = "متن یادداشت خالی است."

NO_ITEM = "آیتمی پیدا نشد. اول چیزی بفرستید تا ذخیره شود."
ITEM_NOT_FOUND = "آیتم موردنظر پیدا نشد (شاید مال شما نباشد یا حذف شده باشد)."

DELETE_CONFIRM = "آیتم <b>#{id}</b> حذف شود؟ (قابل بازگشت با /restore)"
DELETED = "🗑 آیتم <b>#{id}</b> حذف شد. برای بازگردانی: <code>/restore {id}</code>"
RESTORED = "♻️ آیتم <b>#{id}</b> بازگردانده شد."
TRASH_EMPTY = "سطل زدمت خالی است."

REMINDER_SET = "⏰ یادآور برای آیتم <b>#{id}</b> در {time} تنظیم شد."
REMINDER_DUE = "⏰ یادآوری شما!"
REMINDER_BAD_TIME = ("زمان قابل فهم نبود. مثال‌ها:\n"
                     "<code>/remind +30m</code> — ۳۰ دقیقه دیگر\n"
                     "<code>/remind 14:30</code> — امروز ساعت ۱۴:۳۰\n"
                     "<code>/remind فردا 08:00</code>\n"
                     "<code>/remind 2026-12-01 09:00</code>")
REMINDERS_LIST = "⏰ یادآورهای فعال شما:\n{items}"
NO_REMINDERS = "یادآور فعالی ندارید."

CANCELLED = "❌ لغو شد."
ERROR = "⚠️ مشکلی پیش آمد. دوباره تلاش کنید."
NO_AI = "🤖 قابلیت هوش مصنوعی فعال نیست (کلید API تنظیم نشده)."
SUMMARY = "🧠 خلاصه:\n{text}"
SUMMARY_FAIL = "خلاصه‌سازی ممکن نشد."

STATS = """📊 <b>آمار شما</b>

📦 کل آیتم‌ها: {total}
{by_type}
💾 حجم منطقی (روی سرور تلگرام): {size}
🗄 حجم دیتابیس شما روی سرور: ناچیز (فقط متادیتا)"""

SETTINGS = """⚙️ <b>تنظیمات</b>

🤖 هوش مصنوعی: {ai}
📄 اندازهٔ صفحه نتایج: {page}
💾 حداکثر دانلود موقت برای AI: {max_mb} مگابایت
🗂 مسیر دیتابیس: <code>{db}</code>

فایل‌ها هرگز به‌صورت دائم روی سرور ذخیره نمی‌شوند."""

BACKUP_DONE = "💾 پشتیبان دیتابیس ساخته شد: <code>{name}</code>"
BACKUP_FAIL = "پشتیبان‌گیری ناموفق بود."

RESENT = "🔗 بفرمایید:"
RESTORE_NO_FILE = "😕 مرجع فایل این آیتم در دسترس نیست (file_id خالی است)."
RESTORE_UNKNOWN = "🤔 نوع محتوای این آیتم برای بازفرستادن ناشناخته است."
RESTORE_API_ERROR = "⚠️ تلگرام این مرجع فایل را نپذیرفت؛ ممکن است فایل سمت تلگرام حذف شده باشد."
