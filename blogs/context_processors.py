from .models import Category, Blog
from assignments.models import SocialLink, About

def get_categories(request):
    categories = Category.objects.all()
    return dict(categories=categories)


def get_social_links(request):
    social_links = SocialLink.objects.all()
    return dict(social_links=social_links)


def get_sidebar_data(request):
    trending_posts = Blog.objects.filter(status='Published').select_related('category').order_by('-views', '-created_at')[:5]
    about = About.objects.first()
    return dict(trending_posts=trending_posts, site_about=about)