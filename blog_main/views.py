
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from blogs.models import Blog, Category
from assignments.models import About
from .forms import RegistrationForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import auth

def home(request):
    published = Blog.objects.filter(status='Published').select_related('category', 'author')
    featured_posts = published.filter(is_featured=True)[:4]
    posts = Paginator(published.filter(is_featured=False), settings.POSTS_PER_PAGE).get_page(request.GET.get('page'))
    trending = published.order_by('-views', '-created_at')[:5]
    context = {
        'featured_posts': featured_posts,
        'page_obj': posts,
        'trending': trending,
        'about': About.objects.first(),
    }
    return render(request, 'home.html', context)


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created. Please log in.')
            return redirect('login')
    else:
        form = RegistrationForm()
    context = {
        'form': form,
    }
    return render(request, 'register.html', context)


def login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, request.POST)
        if form.is_valid():
            auth.login(request, form.get_user())
            return redirect(request.GET.get('next') or 'dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})


def logout(request):
    auth.logout(request)
    return redirect('home')