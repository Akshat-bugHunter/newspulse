from django.db import migrations

from blogs import ai


def backfill(apps, schema_editor):
    Blog = apps.get_model('blogs', 'Blog')
    for post in Blog.objects.filter(ai_summary=''):
        post.ai_summary = ai.summarize(post.blog_body, 2)
        post.ai_keywords = ','.join(ai.extract_keywords(post.blog_body, post.title))
        post.save(update_fields=['ai_summary', 'ai_keywords'])


class Migration(migrations.Migration):
    dependencies = [('blogs', '0005_alter_blog_options_alter_category_options_and_more')]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
