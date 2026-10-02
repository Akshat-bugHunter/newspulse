from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render

from . import ai
from .models import Blog, Category, Comment


def _paginate(request, queryset):
    return Paginator(queryset, settings.POSTS_PER_PAGE).get_page(request.GET.get('page'))


def posts_by_category(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    posts = Blog.objects.filter(status='Published', category=category).select_related('category', 'author')
    context = {
        'page_obj': _paginate(request, posts),
        'category': category,
    }
    return render(request, 'posts_by_category.html', context)


def blogs(request, slug):
    single_blog = get_object_or_404(Blog.objects.select_related('category', 'author'), slug=slug, status='Published')

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        text = request.POST.get('comment', '').strip()
        if not text:
            messages.error(request, 'Comment cannot be empty.')
        elif len(text) > 250:
            messages.error(request, 'Comment is limited to 250 characters.')
        else:
            comment = Comment.objects.create(user=request.user, blog=single_blog, comment=text)
            if comment.is_flagged:
                messages.warning(request, 'Your comment was held for moderator review.')
            else:
                messages.success(request, 'Comment posted.')
        return HttpResponseRedirect(request.path_info)

    # Count a view once per session per article
    seen = request.session.setdefault('seen_posts', [])
    if single_blog.pk not in seen:
        Blog.objects.filter(pk=single_blog.pk).update(views=F('views') + 1)
        single_blog.views += 1
        seen.append(single_blog.pk)
        request.session.modified = True

    comments = Comment.objects.filter(blog=single_blog, is_flagged=False).select_related('user')
    pool = Blog.objects.filter(status='Published').select_related('category')
    context = {
        'single_blog': single_blog,
        'comments': comments,
        'comment_count': comments.count(),
        'related_posts': ai.similar_posts(single_blog, pool, n=3),
    }
    return render(request, 'blogs.html', context)


def search(request):
    keyword = (request.GET.get('keyword') or '').strip()
    results = []
    if keyword:
        qs = Blog.objects.filter(
            Q(title__icontains=keyword) | Q(short_description__icontains=keyword)
            | Q(blog_body__icontains=keyword) | Q(ai_keywords__icontains=keyword),
            status='Published',
        ).select_related('category', 'author')
        results = sorted(qs, key=lambda p: ai.relevance_score(p, keyword), reverse=True)
    context = {
        'page_obj': _paginate(request, results),
        'keyword': keyword,
        'total': len(results),
    }
    return render(request, 'search.html', context)
