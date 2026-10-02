from django.db import models
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify

from . import ai


class Category(models.Model):
    category_name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['category_name']

    def __str__(self):
        return self.category_name
    

STATUS_CHOICES = (
    ("Draft", "Draft"),
    ("Published", "Published")
)

class Blog(models.Model):
    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=150, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    featured_image = models.ImageField(upload_to='uploads/%Y/%m/%d')
    short_description = models.TextField(max_length=500)
    blog_body = models.TextField(max_length=10000)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    is_featured = models.BooleanField(default=False)
    views = models.PositiveIntegerField(default=0)
    # AI-generated fields (filled automatically on save if left blank)
    ai_summary = models.TextField(blank=True)
    ai_keywords = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', '-created_at'])]

    def __str__(self):
        return self.title

    def _unique_slug(self):
        base = slugify(self.title)[:130] or 'post'
        slug, n = base, 2
        while Blog.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f'{base}-{n}'
            n += 1
        return slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        if self.blog_body:
            if not self.ai_summary:
                self.ai_summary = ai.summarize(self.blog_body, 2)
            if not self.ai_keywords:
                self.ai_keywords = ','.join(ai.extract_keywords(self.blog_body, self.title))
        super().save(*args, **kwargs)

    @property
    def reading_time(self):
        return ai.reading_time(self.blog_body)

    @property
    def keyword_list(self):
        return [k for k in self.ai_keywords.split(',') if k]


class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE)
    comment = models.TextField(max_length=250)
    sentiment = models.CharField(max_length=10, default='neutral')
    is_flagged = models.BooleanField(default=False)  # auto-flagged by toxicity check; hidden until approved
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.comment

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.sentiment = ai.sentiment(self.comment)[0]
            self.is_flagged = ai.is_toxic(self.comment)
        super().save(*args, **kwargs)
