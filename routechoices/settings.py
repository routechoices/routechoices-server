"""
Django settings for routechoices project.

Generated by 'django-admin startproject' using Django 2.1.5.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "your-secret-key"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]


AUTHENTICATION_BACKENDS = (
    # Needed to login by username in Django admin, regardless of `allauth`
    "django.contrib.auth.backends.ModelBackend",
    # `allauth` specific authentication methods, such as login by e-mail
    "allauth.account.auth_backends.AuthenticationBackend",
)

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Application definition

INSTALLED_APPS = [
    "routechoices",
    "routechoices.core",
    "routechoices.site",
    "routechoices.lib",
    "django_bootstrap5",
    "django_hosts",
    "corsheaders",
    "user_sessions",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "invitations",
    "background_task",
    "admincommand",
    "oauth2_provider",
    "rest_framework",
    "drf_yasg",
    "markdownify.apps.MarkdownifyConfig",
    "django_s3_storage",
    "qr_code",
    "kagi",
    "compressor",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.sitemaps",
]

MIDDLEWARE = [
    "routechoices.core.middleware.SessionMiddleware",
    "routechoices.core.middleware.HostsRequestMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "routechoices.core.middleware.XForwardedForMiddleware",
    "routechoices.core.middleware.FilterCountriesIPsMiddleware",
    "routechoices.core.middleware.CorsMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.middleware.common.CommonMiddleware",
    "routechoices.core.middleware.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


SESSION_ENGINE = "user_sessions.backends.db"

ROOT_URLCONF = "routechoices.urls"
ROOT_HOSTCONF = "routechoices.hosts"
DEFAULT_HOST = "www"
PARENT_HOST = "routechoices.dev"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "routechoices.lib.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "routechoices.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "app_db",
        "USER": "app_user",
        "PASSWORD": "changeme",
        "HOST": "db",
        "PORT": "",
        "OPTIONS": {
            "server_side_binding": True,
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

TIME_ZONE = "UTC"

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

SITE_ID = 1

STATIC_URL = "/static/"

STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static_assets"),
]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

LOGIN_URL = "https://routechoices.dev/login"
REDIRECT_ALLOWED_DOMAINS = ["api.routechoices.dev", "www.routechoices.dev"]
LOGIN_REDIRECT_URL = "/dashboard"
LOGOUT_REDIRECT_URL = "/"

SESSION_COOKIE_DOMAIN = ".routechoices.dev"
SESSION_COOKIE_SAMESITE = None

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "drf_orjson_renderer.renderers.ORJSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "oauth2_provider.contrib.rest_framework.OAuth2Authentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ),
}

SLUG_BLACKLIST = [
    ".htaccess",
    ".htpasswd",
    ".well-known",
    "400",
    "401",
    "403",
    "404",
    "405",
    "406",
    "407",
    "408",
    "409",
    "410",
    "411",
    "412",
    "413",
    "414",
    "415",
    "416",
    "417",
    "421",
    "422",
    "423",
    "424",
    "426",
    "428",
    "429",
    "431",
    "500",
    "501",
    "502",
    "503",
    "504",
    "505",
    "506",
    "507",
    "508",
    "509",
    "510",
    "511",
    "about",
    "about-us",
    "abuse",
    "access",
    "account",
    "accounts",
    "ad",
    "add",
    "address",
    "adm",
    "admin",
    "administration",
    "administrator",
    "ads",
    "adult",
    "advertise",
    "advertising",
    "aes128-ctr",
    "aes128-gcm",
    "aes192-ctr",
    "aes256-ctr",
    "aes256-gcm",
    "affiliate",
    "affiliates",
    "ajax",
    "alert",
    "alerts",
    "all",
    "alpha",
    "amp",
    "analysis",
    "analytics",
    "android",
    "api",
    "app",
    "apple-touch-icon.png",
    "apps",
    "archive",
    "archives",
    "article",
    "articles",
    "asc",
    "asct",
    "asset",
    "assets",
    "atom",
    "auth",
    "authentication",
    "authorize",
    "autoconfig",
    "autodiscover",
    "avatar",
    "backers",
    "backup",
    "banner",
    "banners",
    "beta",
    "billing",
    "billings",
    "bin",
    "blog",
    "blogs",
    "board",
    "bookmark",
    "bookmarks",
    "broadcasthost",
    "business",
    "bug",
    "buy",
    "cache",
    "cadastro",
    "calendar",
    "call",
    "campaign",
    "cancel",
    "captcha",
    "career",
    "careers",
    "cart",
    "cas",
    "categories",
    "category",
    "cdn",
    "cgi",
    "cgi-bin",
    "chacha20-poly1305",
    "change",
    "changelog",
    "channel",
    "channels",
    "chart",
    "chat",
    "checkout",
    "clear",
    "client",
    "cliente",
    "clients",
    "close",
    "cms",
    "code",
    "codereview",
    "com",
    "comercial",
    "comment",
    "comments",
    "communities",
    "community",
    "company",
    "compare",
    "compose",
    "compras",
    "config",
    "configuration",
    "connect",
    "contact",
    "contact-us",
    "contactus",
    "contest",
    "contribute",
    "contributor",
    "contributors",
    "cookies",
    "copy",
    "copyright",
    "corp",
    "corporate",
    "count",
    "create",
    "crossdomain.xml",
    "css",
    "curve25519-sha256",
    "customer",
    "customers",
    "customize",
    "dashboard",
    "data",
    "db",
    "deals",
    "debug",
    "default",
    "delete",
    "desc",
    "design",
    "dev",
    "devel",
    "developer",
    "developers",
    "diffie-hellman-group-exchange-sha256",
    "diffie-hellman-group14-sha1",
    "diagram",
    "diary",
    "dict",
    "dictinnary",
    "die",
    "dir",
    "direct",
    "directory",
    "disconnect",
    "discuss",
    "dist",
    "dns",
    "dns0",
    "dns1",
    "dns2",
    "dns3",
    "dns4",
    "doc",
    "docs",
    "documentation",
    "domain",
    "download",
    "downloads",
    "downvote",
    "draft",
    "drop",
    "ecdh-sha2-nistp256",
    "ecdh-sha2-nistp384",
    "ecdh-sha2-nistp521",
    "ecommerce",
    "edit",
    "editor",
    "edu",
    "email",
    "employment",
    "empty",
    "end",
    "enterprise",
    "entries",
    "entry",
    "error",
    "errors",
    "event",
    "events",
    "everyone",
    "example",
    "exception",
    "exit",
    "explore",
    "export",
    "extensions",
    "facebook",
    "false",
    "family",
    "faq",
    "faqs",
    "favicon.ico",
    "favorite",
    "favorites",
    "features",
    "feed",
    "feedback",
    "feeds",
    "file",
    "files",
    "filter",
    "first",
    "flash",
    "fleet",
    "fleets",
    "flog",
    "follow",
    "follower",
    "followers",
    "following",
    "fonts",
    "forgot",
    "forgot-password",
    "forgotpassword",
    "form",
    "forms",
    "forum",
    "forums",
    "founder",
    "founders",
    "free",
    "friend",
    "friends",
    "ftp",
    "get",
    "ghost",
    "gift",
    "gifts",
    "gist",
    "git",
    "github",
    "go",
    "gokartor-proxy",
    "graph",
    "group",
    "groups",
    "guest",
    "guests",
    "guidelines",
    "guides",
    "head",
    "header",
    "help",
    "hide",
    "hmac-sha",
    "hmac-sha1",
    "hmac-sha1-etm",
    "hmac-sha2-256",
    "hmac-sha2-256-etm",
    "hmac-sha2-512",
    "hmac-sha2-512-etm",
    "home",
    "homepage",
    "host",
    "hosting",
    "hostmaster",
    "how",
    "howto",
    "hpg",
    "html",
    "htpasswd",
    "http",
    "httpd",
    "https",
    "humans.txt",
    "icon",
    "icon-192.png",
    "icon-512.png",
    "icons",
    "id",
    "idea",
    "ideas",
    "image",
    "images",
    "imap",
    "img",
    "import",
    "index",
    "indice",
    "info",
    "information",
    "inquire",
    "inquiry",
    "insert",
    "instagram",
    "intranet",
    "investors",
    "invitation",
    "invitations",
    "invite",
    "invites",
    "invoice",
    "ipad",
    "iphone",
    "irc",
    "is",
    "isatap",
    "issue",
    "issues",
    "it",
    "item",
    "items",
    "java",
    "javascript",
    "job",
    "jobs",
    "join",
    "js",
    "json",
    "jump",
    "keybase.txt",
    "language",
    "languages",
    "last",
    "ldap-status",
    "learn",
    "legal",
    "license",
    "licensing",
    "limit",
    "link",
    "links",
    "linux",
    "list",
    "lists",
    "live",
    "livelox-map",
    "load",
    "local",
    "localdomain",
    "localhost",
    "lock",
    "login",
    "log",
    "logo",
    "log-in",
    "login",
    "log-out",
    "logout",
    "logs",
    "lost-password",
    "mac",
    "mail",
    "mail0",
    "mail1",
    "mail2",
    "mail3",
    "mail4",
    "mail5",
    "mail6",
    "mail7",
    "mail8",
    "mail9",
    "mailer",
    "mailer-daemon",
    "mailerdaemon",
    "mailing",
    "maintenance",
    "manager",
    "manifest.json",
    "manual",
    "map",
    "maps",
    "marketing",
    "marketplace",
    "master",
    "me",
    "media",
    "member",
    "members",
    "message",
    "messages",
    "messenger",
    "metrics",
    "microblog",
    "microblogs",
    "mine",
    "mis",
    "mob",
    "mobile",
    "moderator",
    "modify",
    "more",
    "movie",
    "movies",
    "mp3",
    "msg",
    "msn",
    "music",
    "musicas",
    "mx",
    "my",
    "mysql",
    "name",
    "named",
    "nan",
    "navi",
    "navigation",
    "net",
    "network",
    "new",
    "news",
    "newsletter",
    "newsletters",
    "next",
    "nick",
    "nickname",
    "nil",
    "no-reply",
    "nobody",
    "noc",
    "none",
    "noreply",
    "notes",
    "notification",
    "notifications",
    "notify",
    "ns",
    "ns0",
    "ns1",
    "ns2",
    "ns3",
    "ns4",
    "ns5",
    "ns6",
    "ns7",
    "ns8",
    "ns9",
    "null",
    "oauth",
    "oauth_clients",
    "oauth2",
    "ocad-map",
    "offer",
    "offers",
    "official",
    "old",
    "online",
    "openid",
    "order",
    "orders",
    "organisation",
    "organisations",
    "organization",
    "organizations",
    "overview",
    "owner",
    "owners",
    "page",
    "pager",
    "pages",
    "panel",
    "partner",
    "partners",
    "passwd",
    "password",
    "pay",
    "payment",
    "payments",
    "phone",
    "photo",
    "photos",
    "php",
    "phpmyadmin",
    "phppgadmin",
    "phpredisadmin",
    "pic",
    "pics",
    "ping",
    "pixel",
    "plan",
    "plans",
    "plugins",
    "policies",
    "policy",
    "pop",
    "pop3",
    "popular",
    "portal",
    "portfolio",
    "post",
    "postfix",
    "postmaster",
    "posts",
    "poweruser",
    "pr",
    "preferences",
    "premium",
    "press",
    "previous",
    "price",
    "prices",
    "pricing",
    "print",
    "privacy",
    "privacy-policy",
    "privacypolicy",
    "private",
    "prod",
    "product",
    "products",
    "production",
    "profile",
    "profiles",
    "project",
    "projects",
    "promo",
    "pub",
    "public",
    "purchase",
    "purpose",
    "put",
    "python",
    "query",
    "quota",
    "random",
    "ranking",
    "read",
    "readme",
    "recent",
    "recruit",
    "recruitment",
    "redirect",
    "reduce",
    "refund",
    "refunds",
    "register",
    "registration",
    "release",
    "remove",
    "replies",
    "reply",
    "report",
    "reports",
    "repositories",
    "repository",
    "req",
    "request",
    "requests",
    "request-password",
    "reset",
    "reset-password",
    "response",
    "return",
    "returns",
    "review",
    "reviews",
    "robots.txt",
    "roc",
    "root",
    "rootuser",
    "routegadget-map",
    "rsa-sha2-2",
    "rsa-sha2-512",
    "rss",
    "ruby",
    "rule",
    "rules",
    "sag",
    "sale",
    "sales",
    "sample",
    "samples",
    "save",
    "school",
    "schools",
    "script",
    "scripts",
    "sdk",
    "search",
    "secure",
    "security",
    "select",
    "self",
    "send",
    "server",
    "server-info",
    "server-status",
    "service",
    "services",
    "session",
    "sessions",
    "setting",
    "settings",
    "setup",
    "share",
    "shift",
    "shop",
    "show",
    "sign",
    "sign-in",
    "sign-out",
    "sign-up",
    "signin",
    "signout",
    "signup",
    "site",
    "sitemap",
    "sitemap.xml",
    "sites",
    "smartphone",
    "smtp",
    "soporte",
    "sort",
    "source",
    "sql",
    "src",
    "sse",
    "ssh",
    "ssh-rsa",
    "ssl",
    "ssladmin",
    "ssladministrator",
    "sslwebmaster",
    "staff",
    "stage",
    "staging",
    "start",
    "stat",
    "state",
    "static",
    "statistics",
    "stats",
    "status",
    "store",
    "stores",
    "stories",
    "stripe",
    "style",
    "styleguide",
    "styles",
    "stylesheet",
    "stylesheets",
    "subdomain",
    "subscribe",
    "subscriptions",
    "sudo",
    "super",
    "superuser",
    "suporte",
    "support",
    "survey",
    "svn",
    "swf",
    "sync",
    "sys",
    "sysadmin",
    "sysadministrator",
    "system",
    "tablet",
    "tag",
    "tags",
    "talk",
    "task",
    "tasks",
    "team",
    "teams",
    "tech",
    "telnet",
    "term",
    "terms",
    "terms-of-service",
    "terms-of-use",
    "termsofservice",
    "termsofuse",
    "test",
    "test1",
    "test2",
    "test3",
    "test4",
    "teste",
    "testing",
    "tests",
    "testimonials",
    "theme",
    "themes",
    "thread",
    "threads",
    "tile",
    "tile-proxy",
    "tiles",
    "tiles-proxy",
    "tmp",
    "today",
    "todo",
    "tool",
    "tools",
    "top",
    "top3",
    "top5",
    "top10",
    "top50",
    "top100",
    "topic",
    "topics",
    "tos",
    "tour",
    "traccar",
    "tracker",
    "trackers",
    "training",
    "translate",
    "translations",
    "trending",
    "trends",
    "trial",
    "true",
    "tutorial",
    "tux",
    "tv",
    "twitter",
    "umac-128",
    "umac-128-etm",
    "umac-64",
    "umac-64-etm",
    "undef",
    "undefined",
    "unfollow",
    "unsubscribe",
    "update",
    "upgrade",
    "upload",
    "uploads",
    "url",
    "usage",
    "usenet",
    "user",
    "username",
    "users",
    "usuario",
    "uucp",
    "var",
    "vendas",
    "ver",
    "verify",
    "version",
    "versions",
    "video",
    "videos",
    "view",
    "views",
    "visitor",
    "void",
    "vote",
    "watch",
    "weather",
    "web",
    "webhook",
    "webhooks",
    "webmail",
    "webmaster",
    "website",
    "websites",
    "widget",
    "widgets",
    "wiki",
    "win",
    "window",
    "windows",
    "wms",
    "word",
    "work",
    "works",
    "workshop",
    "workshops",
    "wpad",
    "write",
    "www",
    "www-data",
    "www1",
    "www2",
    "www3",
    "www4",
    "www5",
    "www6",
    "www7",
    "www8",
    "www9",
    "wwws",
    "wwww",
    "xfn",
    "xml",
    "xmpp",
    "xpg",
    "xxx",
    "yaml",
    "year",
    "yml",
    "you",
    "yourname",
    "yourusername",
    "youtube",
    "zlib",
]
ACCOUNT_ADAPTER = "routechoices.lib.account_adapters.SiteAccountAdapter"
ACCOUNT_AUTHENTICATION_METHOD = "username_email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"
ACCOUNT_USERNAME_BLACKLIST = SLUG_BLACKLIST
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_USERNAME_MIN_LENGTH = "2"
ACCOUNT_USERNAME_VALIDATORS = "routechoices.lib.validators.custom_username_validators"
ACCOUNT_FORMS = {"reset_password": "routechoices.site.forms.ResetPasswordForm"}

EMAIL_HOST = "smtp"
EMAIL_PORT = 1025

CACHES = {
    "default": {
        "BACKEND": "diskcache.DjangoCache",
        "LOCATION": os.path.join(BASE_DIR, "cache"),
        "TIMEOUT": 300,
        # ^-- Django setting for default timeout of each key.
        "SHARDS": 4,
        "DATABASE_TIMEOUT": 0.10,  # 10 milliseconds
        # ^-- Timeout for each DjangoCache database transaction.
        "OPTIONS": {"size_limit": 2**30},  # 1 gigabyte
    },
}

CACHE_TILES = True
CACHE_THUMBS = True
CACHE_EVENT_DATA = True

TMT250_PORT = 2000
MICTRACK_PORT = 2001
QUECLINK_PORT = 2002
TRACKTAPE_PORT = 2003

# The AWS access key to use.
AWS_ACCESS_KEY_ID = "minio"
# The AWS secret access key to use.
AWS_SECRET_ACCESS_KEY = "minio123"
# The optional AWS session token to use.
AWS_SESSION_TOKEN = ""
AWS_S3_ENDPOINT_URL = "http://minio:9000"
AWS_S3_BUCKET = "routechoices"

GEOIP_PATH = os.path.join(BASE_DIR, "geoip")

SILENCED_SYSTEM_CHECKS = ["admin.E410"]

PATREON_CREATOR_ID = "xRJAgEV1zma3MfnaVGg9SRTYet-EUTKqn4O2Llz6_lk"

MARKDOWNIFY = {
    "default": {
        "WHITELIST_TAGS": [
            "h1",
            "h2",
            "h3",
            "h4",
            "img",
            "a",
            "abbr",
            "acronym",
            "b",
            "blockquote",
            "em",
            "i",
            "li",
            "ol",
            "p",
            "strong",
            "ul",
        ],
        "WHITELIST_ATTRS": [
            "href",
            "src",
            "alt",
            "style",
        ],
        "WHITELIST_STYLES": [
            "color",
            "width",
            "height",
            "font-weight",
        ],
    }
}

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

OAUTH2_PROVIDER = {
    # this is the list of available scopes
    "SCOPES": {"all": "Read and Write data"}
}

SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {
        "Basic": {"type": "basic"},
        "OAuth2": {
            "type": "oauth2",
            "authorizationUrl": "/oauth2/authorize/",
            "tokenUrl": "/oauth2/token/",
            "flow": "accessCode",
            "scopes": {
                "full": "Read and Write data",
            },
        },
    }
}

EMAIL_CUSTOMER_SERVICE = "support@routechoices.dev"

GPS_SSE_SERVER = "data.routechoices.dev"
LIVESTREAM_INTERNAL_SECRET = "<change-me>"

POST_LOCATION_SECRETS = ["<replace-me>"]

XFF_TRUSTED_PROXY_DEPTH = 1

CSP_DEFAULT_SRC = (
    "'self'",
    "www.routechoices.dev",
    "api.routechoices.dev",
    "data.routechoices.dev",
    "www.routechoices.com",
    "api.routechoices.com",
    "nominatim.openstreetmap.org",
    "data:",
)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = (
    "'self'",
    "*",
    "data:",
    "blob:",
)
CSP_WORKER_SRC = ("'self'", "blob:")
CSP_CHILD_SRC = ("'self'", "blob:")

CSRF_TRUSTED_ORIGINS = [
    "https://*.routechoices.dev",
]
CSRF_USE_SESSIONS = True
CSRF_COOKIE_HTTPONLY = False

COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True

ANALYTICS_API_KEY = ""
ANALYTICS_API_URL = "https://analytics.routechoices.com/api/v1"

REDIS_URL = "redis://redis"

SECURE_CROSS_ORIGIN_OPENER_POLICY = None

RELYING_PARTY_ID = "routechoices.dev"
RELYING_PARTY_NAME = "Routechoices.dev"

try:
    from .local_settings import *  # noqa: F403, F401
except ImportError:
    pass
