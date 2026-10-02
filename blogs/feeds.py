from django.contrib.syndication.views import Feed
from django.urls import reverse

from .models import Blog


class LatestPostsFeed(Feed):
    title = 'NewsPulse - Latest stories'
    link = '/'
    description = 'The latest published stories on NewsPulse.'

    def items(self):
        return Blog.objects.filter(status='Published')[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.short_description

    def item_link(self, item):
        return reverse('blogs', args=[item.slug])

    def item_pubdate(self, item):
        return item.created_at
