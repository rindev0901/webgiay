from pathlib import Path
import os
import sys
from django.templatetags.static import static

BASE_DIR = Path(__file__).resolve().parent.parent

# ====================== CẤU HÌNH ĐƯỜNG DẪN ======================
# Cho phép Django tìm app bên trong thư mục apps/
sys.path.insert(0, str(BASE_DIR / "apps"))

SECRET_KEY = "django-insecure-=mmz4)=)554^3v%*-+6@thv$--e1e23wounpwrt1f*h=)$mr0f"

DEBUG = True

ALLOWED_HOSTS = [
    "webgiay-gsyh.onrender.com",
    "localhost",
    "127.0.0.1",
]

# ====================== APPLICATIONS ======================
INSTALLED_APPS = [
    "unfold",  # DefaultAppConfig — replaces admin.site with UnfoldAdminSite
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "corsheaders",
    "import_export",
    "rest_framework",
    "django_filters",
    # App của bạn
    "apps.products.apps.ProductsConfig",
    "apps.cart.apps.CartConfig",
    "apps.accounts.apps.AccountsConfig",
]

# ====================== MIDDLEWARE ======================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "config.middleware.SupplyRedirectMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.cart.context_processors.cart_count",
                "apps.products.context_processors.navigation_data",
                "apps.products.context_processors.supply_nav",
            ],
        },
    },
]

LOGIN_REDIRECT_URL = "products:product_list"
LOGOUT_REDIRECT_URL = "products:product_list"
LOGIN_URL = "accounts:login"

WSGI_APPLICATION = "config.wsgi.application"

# ====================== DATABASE ======================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ====================== AUTHENTICATION ======================
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ====================== INTERNATIONALIZATION ======================
LANGUAGE_CODE = "vi"  # Đổi sang tiếng Việt
TIME_ZONE = "Asia/Ho_Chi_Minh"  # Múi giờ Việt Nam

USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ====================== STATIC & MEDIA ======================
STATIC_URL = "static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# This production code might break development mode, so we check whether we're in DEBUG mode
if not DEBUG:
    # Tell Django to copy static assets into a path called `staticfiles` (this is specific to Render)
    STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

    # Enable the WhiteNoise storage backend, which compresses static files to reduce disk use
    # and renames the files with unique names for each version to support long-term caching
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ====================== EMAIL (SMTP) ======================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "nguyenduc09012003@gmail.com")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "scnnaqpnbpketarq")

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")
# Nếu là production (deploy) thì lấy URL từ biến môi trường
if not DEBUG:
    SITE_URL = os.getenv("SITE_URL", "https://webgiay-gsyh.onrender.com")

# ====================== MOMO PAYMENT ======================
MOMO_PARTNER_CODE = os.getenv("MOMO_PARTNER_CODE", "MOMO")
MOMO_ACCESS_KEY = os.getenv("MOMO_ACCESS_KEY", "F8BBA842ECF85")
MOMO_SECRET_KEY = os.getenv("MOMO_SECRET_KEY", "K951B6PE1waDMi640xX08PD3vg6EkVlz")
MOMO_ENDPOINT = os.getenv(
    "MOMO_ENDPOINT", "https://test-payment.momo.vn/v2/gateway/api/create"
)
MOMO_RETURN_URL = os.getenv(
    "MOMO_RETURN_URL", "http://127.0.0.1:8000/cart/momo/return/"
)
MOMO_IPN_URL = os.getenv("MOMO_IPN_URL", "http://127.0.0.1:8000/cart/momo/ipn/")
MOMO_REQUEST_TYPE = os.getenv("MOMO_REQUEST_TYPE", "captureWallet")

# ====================== UNFOLD ADMIN ======================
from config.admin_sidebar import SIDEBAR_NAVIGATION

UNFOLD = {
    "SITE_TITLE": "Quản trị Dat Shoes",
    "SITE_HEADER": "Dat Shoes Admin",
    "SHOW_HEADER": True,
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "DASHBOARD_CALLBACK": "apps.cart.dashboard.dashboard_callback",
    "STYLES": [
        lambda request: static("css/main.css"),
    ],
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": SIDEBAR_NAVIGATION,
    },
}

# ====================== CORS ======================
CORS_ALLOW_ALL_ORIGINS = True

# ====================== SEPAY PAYMENT ======================
SEPAY_MERCHANT = os.getenv("SEPAY_MERCHANT", "SP-TEST-TG4A5563")
SEPAY_SECRET_KEY = os.getenv(
    "SEPAY_SECRET_KEY", "spsk_test_CKR4oRGaGEx78QA9JUT1UyQu6hxtLiSw"
)
# Sandbox: https://pgapi-sandbox.sepay.vn/v1/checkout/init
# Production: https://pgapi.sepay.vn/v1/checkout/init
SEPAY_CHECKOUT_URL = os.getenv(
    "SEPAY_CHECKOUT_URL", "https://pay-sandbox.sepay.vn/v1/checkout/init"
)

# ====================== REST FRAMEWORK CONFIG ======================
REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,  # Mỗi trang hiển thị 12 sản phẩm
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

# ====================== LOGGING ======================
LOG_DIR = BASE_DIR / "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "email_file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "email.log",
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "apps.cart.email_service": {
            "handlers": ["console", "email_file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
