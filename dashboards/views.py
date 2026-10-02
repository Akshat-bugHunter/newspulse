import json

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from blogs import ai
from blogs.models import Blog, Category, Comment

from .forms import AddUserForm, BlogPostForm, CategoryForm, EditUserForm


@login_required
def dashboard(request):
    comments = Comment.objects.all()
    sentiment = {row['sentiment']: row['n'] for row in comments.values('sentiment').annotate(n=Count('id'))}
    context = {
        'category_count': Category.objects.count(),
        'blogs_count': Blog.objects.count(),
        'published_count': Blog.objects.filter(status='Published').count(),
        'draft_count': Blog.objects.filter(status='Draft').count(),
        'total_views': Blog.objects.aggregate(t=Sum('views'))['t'] or 0,
        'comment_count': comments.count(),
        'top_posts': Blog.objects.order_by('-views')[:5],
        'recent_posts': Blog.objects.select_related('category')[:5],
        'flagged_comments': comments.filter(is_flagged=True).select_related('user', 'blog'),
        'sentiment': {k: sentiment.get(k, 0) for k in ('positive', 'neutral', 'negative')},
    }
    return render(request, 'dashboard/dashboard.html', context)


# ---------------------------------------------------------------- categories

@login_required
def categories(request):
    return render(request, 'dashboard/categories.html')


@login_required
def add_category(request):
    form = CategoryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('categories')
    return render(request, 'dashboard/add_category.html', {'form': form})


@login_required
def edit_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('categories')
    return render(request, 'dashboard/edit_category.html', {'form': form, 'category': category})


@login_required
@require_POST
def delete_category(request, pk):
    get_object_or_404(Category, pk=pk).delete()
    return redirect('categories')


# ---------------------------------------------------------------- posts

@login_required
def posts(request):
    return render(request, 'dashboard/posts.html', {'posts': Blog.objects.select_related('category', 'author')})


@login_required
def add_post(request):
    form = BlogPostForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()  # slug, AI summary and keywords are generated in Blog.save()
        return redirect('posts')
    return render(request, 'dashboard/add_post.html', {'form': form})


@login_required
def edit_post(request, pk):
    post = get_object_or_404(Blog, pk=pk)
    form = BlogPostForm(request.POST or None, request.FILES or None, instance=post)
    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False)
        # regenerate AI fields when the body changed
        post.ai_summary = ''
        post.ai_keywords = ''
        post.save()
        return redirect('posts')
    return render(request, 'dashboard/edit_post.html', {'form': form, 'post': post})


@login_required
@require_POST
def delete_post(request, pk):
    get_object_or_404(Blog, pk=pk).delete()
    return redirect('posts')


@login_required
@require_POST
def ai_assist(request):
    """JSON endpoint used by the 'AI Assist' button in the post editor."""
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    body = (data.get('body') or '').strip()
    if len(body) < 40:
        return JsonResponse({'error': 'Write at least a couple of sentences first.'}, status=400)
    return JsonResponse(ai.ai_assist((data.get('title') or '').strip(), body))


# ---------------------------------------------------------------- comment moderation

@login_required
@permission_required('blogs.change_comment', raise_exception=True)
@require_POST
def approve_comment(request, pk):
    Comment.objects.filter(pk=pk).update(is_flagged=False)
    return redirect('dashboard')


@login_required
@permission_required('blogs.delete_comment', raise_exception=True)
@require_POST
def delete_comment(request, pk):
    get_object_or_404(Comment, pk=pk).delete()
    return redirect('dashboard')


# ---------------------------------------------------------------- users (permission-gated)

@login_required
@permission_required('auth.view_user', raise_exception=True)
def users(request):
    return render(request, 'dashboard/users.html', {'users': User.objects.all()})


@login_required
@permission_required('auth.add_user', raise_exception=True)
def add_user(request):
    form = AddUserForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('users')
    return render(request, 'dashboard/add_user.html', {'form': form})


@login_required
@permission_required('auth.change_user', raise_exception=True)
def edit_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = EditUserForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('users')
    return render(request, 'dashboard/edit_user.html', {'form': form})


@login_required
@permission_required('auth.delete_user', raise_exception=True)
@require_POST
def delete_user(request, pk):
    get_object_or_404(User, pk=pk).delete()
    return redirect('users')
