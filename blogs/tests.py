import json
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from . import ai
from .models import Blog, Category, Comment

TMP_MEDIA = tempfile.mkdtemp()

TEXT = ("Solar power is growing quickly across the world. Cheap panels and batteries make solar attractive "
        "for homes and businesses. Grid operators are adapting to handle more solar energy. "
        "Meanwhile, football fans filled the stadium on Sunday.")


class AIHelpersTests(TestCase):
    def test_reading_time_minimum_one(self):
        self.assertEqual(ai.reading_time('short text'), 1)

    def test_keywords_skip_stopwords(self):
        kws = ai.extract_keywords(TEXT, 'Solar growth')
        self.assertIn('solar', kws)
        self.assertNotIn('the', kws)

    def test_summary_is_shorter_and_extractive(self):
        s = ai.summarize(TEXT, 2)
        self.assertLess(len(s), len(TEXT))
        self.assertTrue(all(part.strip() in TEXT for part in s.split('. ') if part))

    def test_sentiment_and_toxicity(self):
        self.assertEqual(ai.sentiment('Great and helpful article')[0], 'positive')
        self.assertEqual(ai.sentiment('This is terrible and useless')[0], 'negative')
        self.assertEqual(ai.sentiment('The council met on Tuesday')[0], 'neutral')
        self.assertTrue(ai.is_toxic('you are an idiot'))
        self.assertFalse(ai.is_toxic('I disagree with this point'))

    def test_ai_assist_falls_back_to_local(self):
        out = ai.ai_assist('Solar', TEXT)
        self.assertEqual(out['source'], 'local')
        self.assertTrue(out['summary'])


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class SiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_news', verbosity=0)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user('reader', password='pw12345!')
        self.post = Blog.objects.filter(status='Published').first()

    def test_public_pages_render(self):
        cat = Category.objects.first()
        for url in [reverse('home'), reverse('home') + '?page=2', reverse('search') + '?keyword=model',
                    reverse('search'), reverse('posts_by_category', args=[cat.id]),
                    reverse('blogs', args=[self.post.slug]), reverse('login'), reverse('register'),
                    reverse('rss_feed')]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_seed_is_idempotent_and_has_content(self):
        n = Blog.objects.count()
        self.assertGreaterEqual(n, 24)
        call_command('seed_news', verbosity=0)
        self.assertEqual(Blog.objects.count(), n)

    def test_slug_unique_and_ai_fields_autofilled(self):
        p = Blog.objects.create(title=self.post.title, category=self.post.category, author=self.user,
                                featured_image=self.post.featured_image, short_description='x', blog_body=TEXT)
        self.assertNotEqual(p.slug, self.post.slug)
        self.assertTrue(p.ai_summary)
        self.assertIn('solar', p.keyword_list)

    def test_view_counted_once_per_session(self):
        before = self.post.views
        url = reverse('blogs', args=[self.post.slug])
        self.client.get(url)
        self.client.get(url)
        self.post.refresh_from_db()
        self.assertEqual(self.post.views, before + 1)

    def test_related_posts_on_article_page(self):
        r = self.client.get(reverse('blogs', args=[self.post.slug]))
        self.assertTrue(len(r.context['related_posts']) > 0)

    def test_comment_requires_login(self):
        r = self.client.post(reverse('blogs', args=[self.post.slug]), {'comment': 'hi'})
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r.url)
        self.assertEqual(Comment.objects.count(), 0)

    def test_toxic_comment_is_held(self):
        self.client.login(username='reader', password='pw12345!')
        url = reverse('blogs', args=[self.post.slug])
        self.client.post(url, {'comment': 'Great article, very helpful'})
        self.client.post(url, {'comment': 'you are an idiot'})
        self.assertEqual(Comment.objects.get(comment__startswith='Great').sentiment, 'positive')
        self.assertTrue(Comment.objects.get(comment__startswith='you').is_flagged)
        self.assertEqual(self.client.get(url).context['comment_count'], 1)


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_news', verbosity=0)

    def setUp(self):
        self.user = User.objects.create_user('editor', password='pw12345!')
        self.admin = User.objects.create_superuser('boss', 'b@x.com', 'pw12345!')
        self.post = Blog.objects.first()

    def test_dashboard_requires_login(self):
        for name in ['dashboard', 'posts', 'categories', 'add_post', 'users']:
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)

    def test_delete_requires_post(self):
        self.client.login(username='editor', password='pw12345!')
        r = self.client.get(reverse('delete_post', args=[self.post.pk]))
        self.assertEqual(r.status_code, 405)
        self.assertTrue(Blog.objects.filter(pk=self.post.pk).exists())

    def test_users_page_needs_permission(self):
        self.client.login(username='editor', password='pw12345!')
        self.assertEqual(self.client.get(reverse('users')).status_code, 403)
        self.client.login(username='boss', password='pw12345!')
        self.assertEqual(self.client.get(reverse('users')).status_code, 200)

    def test_dashboard_pages_render_for_admin(self):
        self.client.login(username='boss', password='pw12345!')
        for name in ['dashboard', 'posts', 'categories', 'add_post', 'add_category', 'users', 'add_user']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get(reverse('edit_post', args=[self.post.pk])).status_code, 200)

    def test_ai_assist_endpoint(self):
        self.client.login(username='editor', password='pw12345!')
        r = self.client.post(reverse('ai_assist'), json.dumps({'title': 'Solar', 'body': TEXT}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('keywords', r.json())
        r = self.client.post(reverse('ai_assist'), json.dumps({'body': 'too short'}), content_type='application/json')
        self.assertEqual(r.status_code, 400)

    def test_ai_assist_requires_login(self):
        r = self.client.post(reverse('ai_assist'), '{}', content_type='application/json')
        self.assertEqual(r.status_code, 302)

    def test_moderation_flow(self):
        c = Comment.objects.create(user=self.user, blog=self.post, comment='what a stupid take')
        self.assertTrue(c.is_flagged)
        self.client.login(username='boss', password='pw12345!')
        self.client.post(reverse('approve_comment', args=[c.pk]))
        c.refresh_from_db()
        self.assertFalse(c.is_flagged)
