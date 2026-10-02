"""
Fetch real news from NewsAPI.org and store articles with downloaded cover images.

Usage:
    python manage.py fetch_news                     # fetch all categories (5 articles each)
    python manage.py fetch_news --reset             # delete API-fetched posts first, then re-fetch
    python manage.py fetch_news --category sports   # single category only
    python manage.py fetch_news --count 10          # articles per category (max ~100/day free tier)
    python manage.py fetch_news --key YOUR_KEY      # override settings.NEWSAPI_KEY

Free-tier limits: 100 requests / day, content truncated at 200 chars.
Article body is assembled from title + description + content snippet.
Cover images are downloaded directly from the article's urlToImage field.
If the image URL is unavailable a local gradient cover is generated instead.
"""

import io
import json
import random
import re
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from blogs.models import Blog, Category
from PIL import Image, ImageDraw

# ── Gradient-cover fallback ──────────────────────────────────────────────────

PALETTES = {
    'Technology':    ((15, 23, 42),  (30, 58, 138),  (56, 189, 248)),
    'AI':            ((46, 16, 101), (109, 40, 217), (244, 114, 182)),
    'Business':      ((15, 40, 35),  (20, 83, 75),   (52, 211, 153)),
    'Sports':        ((88, 28, 28),  (185, 28, 28),  (251, 146, 60)),
    'Science':       ((15, 30, 50),  (30, 80, 110),  (94, 234, 212)),
    'Health':        ((6, 78, 59),   (13, 148, 136), (110, 231, 183)),
    'World':         ((30, 27, 75),  (67, 56, 202),  (129, 140, 248)),
    'Entertainment': ((76, 29, 149), (190, 24, 93),  (251, 113, 133)),
    'Politics':      ((28, 28, 70),  (70, 70, 160),  (160, 160, 230)),
}


def _make_gradient_cover(category: str, title: str) -> ContentFile:
    """Generate a modern editorial gradient cover when no image is available."""
    c_dark, c_mid, c_accent = PALETTES.get(category, ((20, 25, 35), (50, 60, 80), (140, 160, 190)))
    w, h = 1200, 630
    img = Image.new('RGB', (w, h), c_dark)
    px = img.load()
    for y in range(h):
        for x in range(w):
            f = (x / w) * 0.55 + (y / h) * 0.45
            px[x, y] = tuple(int(c_dark[i] + (c_mid[i] - c_dark[i]) * f) for i in range(3))

    rnd = random.Random(title)
    # Ambient glow
    glow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gx, gy, gr = rnd.randint(int(w * .4), int(w * .85)), rnd.randint(int(h * .2), int(h * .8)), rnd.randint(220, 380)
    for i in range(12):
        r = gr - i * (gr // 12)
        gd.ellipse((gx - r, gy - r, gx + r, gy + r), fill=(*c_accent, 12 + i * 4))
    # Angled beam
    beam = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(beam)
    bx = rnd.randint(int(w * .25), int(w * .7))
    bd.polygon([(bx, 0), (bx + 280, 0), (bx - 120, h), (bx - 400, h)], fill=(*c_accent, 22))
    # Concentric rings + dot grid
    geom = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(geom)
    cx, cy = rnd.randint(int(w * .55), int(w * .9)), rnd.randint(int(h * .2), int(h * .8))
    for r_ring in [120, 200, 300, 420]:
        draw.ellipse((cx - r_ring, cy - r_ring, cx + r_ring, cy + r_ring), outline=(255, 255, 255, 28), width=2)
    dx0, dy0 = rnd.randint(60, 200), rnd.randint(60, 200)
    for xi in range(6):
        for yi in range(5):
            d = (dx0 + xi * 28, dy0 + yi * 28)
            draw.ellipse((d[0] - 2, d[1] - 2, d[0] + 2, d[1] + 2), fill=(255, 255, 255, 45))

    img = Image.alpha_composite(img.convert('RGBA'), glow)
    img = Image.alpha_composite(img, beam)
    img = Image.alpha_composite(img, geom)
    buf = io.BytesIO()
    img.convert('RGB').save(buf, 'JPEG', quality=88)
    return ContentFile(buf.getvalue())


# ── NewsAPI helpers ──────────────────────────────────────────────────────────

NEWSAPI_BASE = 'https://newsapi.org/v2/top-headlines'

# Maps our site categories → (newsapi_category, optional_q_keyword)
CATEGORY_MAP = {
    'AI':            ('technology', 'artificial intelligence OR machine learning OR AI'),
    'Technology':    ('technology', None),
    'Business':      ('business',   None),
    'Entertainment': ('entertainment', None),
    'Health':        ('health',     None),
    'Science':       ('science',    None),
    'Sports':        ('sports',     None),
    'World':         ('general',    None),
    'Politics':      ('general',    'politics OR government OR election'),
}

# Tag stored in ai_keywords so we can identify and reset API-fetched posts
SOURCE_TAG = 'newsapi_fetched'

# Headers sent with every image download attempt
_IMG_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0 Safari/537.36'
    ),
    'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://news.google.com/',
}


def _fetch_articles(api_key: str, category_name: str, count: int) -> list[dict]:
    """Call NewsAPI and return up to `count` articles for the given site category."""
    newsapi_cat, q = CATEGORY_MAP.get(category_name, ('general', None))
    params = {
        'apiKey': api_key,
        'category': newsapi_cat,
        'language': 'en',
        'pageSize': min(count, 20),
        'country': 'us',
    }
    if q:
        # Use /everything endpoint when a keyword filter is needed
        url = 'https://newsapi.org/v2/everything'
        params.pop('category', None)
        params.pop('country', None)
        params['q'] = q
        params['sortBy'] = 'publishedAt'
    else:
        url = NEWSAPI_BASE

    full_url = url + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(full_url, headers={'User-Agent': 'NewsPulse/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise CommandError(f'NewsAPI HTTP {exc.code} for category "{category_name}": {exc.reason}') from exc
    except Exception as exc:
        raise CommandError(f'NewsAPI request failed: {exc}') from exc

    if data.get('status') != 'ok':
        raise CommandError(f'NewsAPI error: {data.get("message", data)}')

    return [a for a in data.get('articles', []) if a.get('title') and '[Removed]' not in a['title']]


def _download_image(url: str) -> bytes | None:
    """Download image bytes from url; return None on any failure."""
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers=_IMG_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        # Verify it's actually a decodable image
        Image.open(io.BytesIO(raw)).verify()
        return raw
    except Exception:
        return None


def _clean_body(article: dict) -> str:
    """Build a readable article body from the fields NewsAPI provides."""
    parts = []
    desc = (article.get('description') or '').strip()
    content = (article.get('content') or '').strip()
    # NewsAPI free tier truncates content with ' [+NNNN chars]' — strip that
    content = re.sub(r'\s*\[\+\d+ chars\]$', '', content).strip()

    if desc:
        parts.append(desc)
    if content and content != desc:
        parts.append(content)

    source_name = (article.get('source') or {}).get('name', '')
    if source_name:
        parts.append(f'Source: {source_name}')

    body = '\n\n'.join(parts) if parts else (article.get('title', '') + '.')
    # Ensure body fits within the model's max_length=10000
    return body[:9800]


def _safe_slug(title: str, existing_slugs: set) -> str:
    base = re.sub(r'[^\w-]', '-', title.lower())[:110].strip('-')
    slug, n = base, 2
    while slug in existing_slugs:
        slug = f'{base}-{n}'
        n += 1
    existing_slugs.add(slug)
    return slug


# ── Management command ────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Fetch real news from NewsAPI.org and populate the database with live articles + images'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Delete previously API-fetched posts before importing')
        parser.add_argument('--category', default=None,
                            help='Import only this category (e.g. "sports")')
        parser.add_argument('--count', type=int, default=5,
                            help='Articles to import per category (default 5, max 20)')
        parser.add_argument('--key', default=None,
                            help='NewsAPI key (overrides settings.NEWSAPI_KEY)')

    def handle(self, *args, **opts):
        api_key = opts['key'] or getattr(settings, 'NEWSAPI_KEY', '')
        if not api_key:
            raise CommandError(
                'No NewsAPI key found. Set NEWSAPI_KEY in settings.py or pass --key.'
            )

        count = max(1, min(opts['count'], 20))

        # Resolve author
        author = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not author:
            author = User.objects.create_user('newsdesk', password='newsdesk12345')
            self.stdout.write('Created user "newsdesk" (password: newsdesk12345)')

        # Optionally wipe previous API posts
        if opts['reset']:
            deleted, _ = Blog.objects.filter(ai_keywords__contains=SOURCE_TAG).delete()
            self.stdout.write(self.style.WARNING(f'Deleted {deleted} previously fetched articles.'))

        # Determine which categories to process
        target_cats = (
            {opts['category'].title(): CATEGORY_MAP[opts['category'].title()]}
            if opts['category'] and opts['category'].title() in CATEGORY_MAP
            else CATEGORY_MAP
        )

        # Pre-load existing slugs to avoid clashes
        existing_slugs = set(Blog.objects.values_list('slug', flat=True))

        total_created = total_skipped = total_failed = 0

        for cat_name in target_cats:
            cat_obj, _ = Category.objects.get_or_create(category_name=cat_name)
            self.stdout.write(f'\n>>  Fetching {count} articles for [{cat_name}] ...')

            try:
                articles = _fetch_articles(api_key, cat_name, count)
            except CommandError as exc:
                self.stdout.write(self.style.ERROR(f'   [FAIL] {exc}'))
                total_failed += 1
                continue

            self.stdout.write(f'   NewsAPI returned {len(articles)} results.')

            created_this_cat = 0
            for art in articles[:count]:
                title = (art.get('title') or '').strip()
                if not title or title == '[Removed]':
                    continue

                # Skip if a post with this title already exists
                if Blog.objects.filter(title=title).exists():
                    total_skipped += 1
                    continue

                slug = _safe_slug(title, existing_slugs)
                description = (art.get('description') or title)[:490]
                body = _clean_body(art)

                # -- Cover image --
                img_url = art.get('urlToImage', '')
                img_bytes = _download_image(img_url) if img_url else None

                if img_bytes:
                    img_file = ContentFile(img_bytes)
                    img_name = f'newsapi/{cat_name.lower()}-{slug[:40]}.jpg'
                    self.stdout.write(f'   [OK] Downloaded image: {title[:60]}')
                else:
                    img_file = _make_gradient_cover(cat_name, title)
                    img_name = f'newsapi/{cat_name.lower()}-fallback-{slug[:30]}.jpg'
                    self.stdout.write(
                        self.style.WARNING(f'   [IMG] No image, using gradient cover: {title[:60]}')
                    )

                # -- Save post --
                try:
                    post = Blog(
                        title=title[:100],
                        slug=slug,
                        category=cat_obj,
                        author=author,
                        short_description=description,
                        blog_body=body,
                        status='Published',
                        is_featured=(created_this_cat == 0),   # first article per category is featured
                        views=random.randint(10, 400),
                        # Tag so --reset can identify these posts later
                        ai_keywords=SOURCE_TAG,
                    )
                    post.featured_image.save(img_name, img_file, save=False)
                    post.save()                               # triggers AI summary / keyword extraction
                    created_this_cat += 1
                    total_created += 1
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f'   [ERR] Could not save "{title[:50]}": {exc}'))
                    total_failed += 1

            self.stdout.write(
                self.style.SUCCESS(f'   [DONE] {created_this_cat} new articles added for {cat_name}.')
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nFinished -- Created: {total_created} | Skipped (duplicate): {total_skipped} | Failed: {total_failed}'
            )
        )
