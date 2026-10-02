# NewsPulse — AI-assisted news platform (Django)

A multi-role news/blogging platform with an editorial dashboard and built-in AI features.
Foundation built following the *Tech With Rathan* Django course, then extended with the
features marked **(added)** below.

## Features
- Articles, categories, featured/top stories, drafts vs. published, image uploads
- Role-aware dashboard (Django permissions): posts, categories, users, comment moderation
- Auth, comments (login required), search, RSS feed at `/feed/`
- **(added)** Pagination, trending stories (view counts, once per session), reading time, thumbnails
- **(added)** Dashboard analytics: posts/drafts, total views, top posts, comment sentiment
- **(added)** Security fixes: login required on all dashboard views, permission checks on user admin,
  delete actions are POST + CSRF, env-based `SECRET_KEY` / `DEBUG` / `ALLOWED_HOSTS`
- **(added)** 24 sample articles + generated cover images via `seed_news`
- **(added)** 19 automated tests (`python manage.py test`)

## AI features
| Feature | How it works |
|---|---|
| Article TL;DR | Extractive summarizer (sentence scoring by word frequency + lead bias), generated on save |
| Auto keywords / hashtags | Frequency-based with title boost; clickable, feeds search |
| Related articles | TF-IDF vectors + cosine similarity, boosted for same category |
| Smart search | Keyword match ranked by title > description > body |
| Comment sentiment | Lexicon-based positive / neutral / negative, shown in the dashboard |
| Auto-moderation | Toxic comments are held for review; moderators approve or delete |
| Editor "AI Assist" | One click generates summary, card description, keywords, reading time |
| Optional LLM mode | Set `ANTHROPIC_API_KEY` to get Claude-written summaries and headline ideas; falls back to local NLP on any error |

All core AI logic lives in `blogs/ai.py` (pure Python, no ML dependencies).

## Run locally
```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_news          # adds sample articles (use --reset to re-seed)
python manage.py createsuperuser
python manage.py runserver
```
Dashboard: `/dashboard/` · Admin: `/admin/` · Tests: `python manage.py test`

## Tech
Django, SQLite, Bootstrap 4, Pillow, django-crispy-forms. Optional: Anthropic API.
