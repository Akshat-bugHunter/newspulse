"""
Lightweight AI / NLP helpers for the news platform.

Everything here runs locally with pure Python (no heavy dependencies), so the
project works out of the box. If ANTHROPIC_API_KEY is set, `ai_assist` upgrades
to an LLM-generated summary/headlines and falls back to local logic on any error.
"""
import json
import math
import re
import urllib.request
from collections import Counter

from django.conf import settings

STOPWORDS = set("""
a about above after again against all also am an and any are as at be because been before being below between
both but by can could did do does doing down during each few for from further had has have having he her here hers
him his how i if in into is it its just may me might more most must my no nor not now of off on once only or other
our out over own said same she should so some such than that the their them then there these they this those through
to too under until up very was we were what when where which while who whom why will with would you your yours
one two three new says say according
""".split())

POSITIVE = set("""
good great excellent amazing awesome love loved helpful useful insightful brilliant best better nice happy win won
success growth improve improved improving strong positive thanks thank informative clear fantastic impressive
""".split())
NEGATIVE = set("""
bad worst terrible awful hate hated useless boring poor wrong fake false misleading weak negative sad angry
disappointing disappointed fail failed failure confusing waste scam broken
""".split())
TOXIC = set("""
idiot idiots stupid moron morons dumb trash garbage scum shut loser losers hell crap
""".split())

_WORD = re.compile(r"[a-zA-Z][a-zA-Z'-]+")
_SENT = re.compile(r"(?<=[.!?])\s+")


def tokenize(text):
    return [w.lower() for w in _WORD.findall(text or "")]


def content_words(text):
    return [w for w in tokenize(text) if w not in STOPWORDS and len(w) > 2]


def reading_time(text, wpm=200):
    """Estimated minutes to read (min 1)."""
    return max(1, round(len(tokenize(text)) / wpm))


def extract_keywords(text, title="", n=6):
    """Frequency-based keywords; title words get a boost."""
    counts = Counter(content_words(text))
    for w in content_words(title):
        counts[w] += 3
    return [w for w, _ in counts.most_common(n)]


def summarize(text, max_sentences=2):
    """Extractive summary: score sentences by word frequency, keep original order."""
    sentences = [s.strip() for s in _SENT.split((text or "").replace("\n", " ")) if len(s.strip()) > 20]
    if len(sentences) <= max_sentences:
        return " ".join(sentences)
    freq = Counter(content_words(text))
    top = max(freq.values()) if freq else 1
    scored = []
    for i, s in enumerate(sentences):
        words = content_words(s)
        if not words:
            continue
        score = sum(freq[w] / top for w in words) / (len(words) ** 0.6)
        if i == 0:
            score *= 1.25  # lead sentence bias, typical for news writing
        scored.append((score, i))
    best = sorted(sorted(scored, reverse=True)[:max_sentences], key=lambda x: x[1])
    return " ".join(sentences[i] for _, i in best)


def sentiment(text):
    """Returns (label, score) where score is in [-1, 1]."""
    words = tokenize(text)
    if not words:
        return "neutral", 0.0
    pos = sum(w in POSITIVE for w in words)
    neg = sum(w in NEGATIVE for w in words)
    score = (pos - neg) / max(1, pos + neg)
    if pos == neg:
        return "neutral", 0.0
    return ("positive" if score > 0 else "negative"), round(score, 2)


def is_toxic(text):
    words = set(tokenize(text))
    return bool(words & TOXIC)


def similar_posts(target, candidates, n=3):
    """Related articles via TF-IDF cosine similarity. `candidates` is an iterable of Blog."""
    candidates = [c for c in candidates if c.pk != target.pk]
    if not candidates:
        return []
    docs = {c.pk: content_words(f"{c.title} {c.title} {c.short_description} {c.blog_body}") for c in candidates}
    t_doc = content_words(f"{target.title} {target.title} {target.short_description} {target.blog_body}")
    all_docs = list(docs.values()) + [t_doc]
    df = Counter(w for d in all_docs for w in set(d))
    N = len(all_docs)

    def vec(words):
        tf = Counter(words)
        return {w: (1 + math.log(c)) * math.log((N + 1) / (df[w] + 0.5)) for w, c in tf.items()}

    def cos(a, b):
        dot = sum(a[w] * b.get(w, 0) for w in a)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    tv = vec(t_doc)
    scored = []
    for c in candidates:
        s = cos(tv, vec(docs[c.pk]))
        if c.category_id == target.category_id:
            s *= 1.15
        scored.append((s, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for s, c in scored[:n] if s > 0]


def relevance_score(post, keyword):
    """Simple ranking for search: title hits weigh more than description, then body."""
    k = keyword.lower()
    return 5 * post.title.lower().count(k) + 3 * post.short_description.lower().count(k) + post.blog_body.lower().count(k)


# ---------------------------------------------------------------- LLM (optional)

def llm_available():
    return bool(getattr(settings, "ANTHROPIC_API_KEY", ""))


def _call_claude(prompt, max_tokens=600):
    body = json.dumps({
        "model": settings.ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def ai_assist(title, body):
    """
    Editor helper. Returns dict(summary, description, keywords, headlines, reading_time, source).
    Uses Claude when ANTHROPIC_API_KEY is configured, otherwise local NLP.
    """
    local = {
        "summary": summarize(body, 2),
        "description": summarize(body, 1)[:480],
        "keywords": extract_keywords(body, title, 6),
        "headlines": [],
        "reading_time": reading_time(body),
        "source": "local",
    }
    if not llm_available() or len(body.strip()) < 80:
        return local
    prompt = (
        "You are a news editor. Given the article below, reply with ONLY a JSON object with keys: "
        '"summary" (2 sentences), "description" (one sentence under 300 chars for a card preview), '
        '"keywords" (array of 5-6 lowercase strings), "headlines" (array of 3 alternative headlines).\n\n'
        f"Title: {title}\n\nBody:\n{body[:6000]}"
    )
    try:
        text = _call_claude(prompt)
        match = re.search(r"\{.*\}", text, re.S)
        data = json.loads(match.group(0))
        local.update({
            "summary": str(data.get("summary", local["summary"])),
            "description": str(data.get("description", local["description"]))[:480],
            "keywords": [str(k).lower() for k in data.get("keywords", local["keywords"])][:6],
            "headlines": [str(h) for h in data.get("headlines", [])][:3],
            "source": "claude",
        })
    except Exception:
        pass  # silently fall back to local result
    return local
