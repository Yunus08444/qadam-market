
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, render

from .models import Category, Product


def home(request):
    categories = Category.objects.filter(is_active=True).annotate(
        product_count=Count('products', filter=Q(products__is_active=True))
    )
    featured_products = Product.objects.filter(
        is_active=True,
        is_featured=True,
        category__is_active=True,
    ).select_related('category').order_by('-created_at')[:8]
    new_products = Product.objects.filter(
        is_active=True,
        category__is_active=True,
    ).select_related('category').order_by('-created_at')[:8]

    video_products = Product.objects.filter(
        is_active=True,
        category__is_active=True,
    ).exclude(video_url='')[:4]

    return render(request, 'home.html', {
        'video_products': video_products,
        'categories': categories,
        'featured_products': featured_products,
        'new_products': new_products,
    })


def catalog(request):
    categories = Category.objects.filter(is_active=True).order_by('name')
    products = Product.objects.filter(
        is_active=True,
        category__is_active=True,
    ).select_related('category')

    query = request.GET.get('q', '').strip()[:100]
    category_slug = request.GET.get('category', '').strip()[:100]
    sort = request.GET.get('sort', 'newest')
    in_stock = request.GET.get('in_stock') == '1'

    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(article__icontains=query)
        )
    if category_slug:
        products = products.filter(category__slug=category_slug)
    if in_stock:
        products = products.filter(stock__gt=0)

    ordering = {
        'newest': ('-created_at', '-pk'),
        'oldest': ('created_at', 'pk'),
        # Products without a price go last on every database
        # (SQLite and PostgreSQL put NULL on different sides by default).
        'price_asc': (F('price').asc(nulls_last=True), '-created_at', '-pk'),
        'price_desc': (F('price').desc(nulls_last=True), '-created_at', '-pk'),
        'name': ('name', 'pk'),
    }
    if sort not in ordering:
        sort = 'newest'
    products = products.order_by(*ordering[sort])

    page_obj = Paginator(products, 12).get_page(request.GET.get('page'))
    return render(request, 'catalog.html', {
        'categories': categories,
        'page_obj': page_obj,
        'query': query,
        'selected_category': category_slug,
        'sort': sort,
        'in_stock': in_stock,
    })


def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related('extra_images'),
        pk=pk,
        is_active=True,
        category__is_active=True,
    )
    wa_text = f'Здравствуйте! Интересует {product.name} (артикул {product.article}).'
    return render(request, 'product_detail.html', {
        'product': product,
        'wa_text': wa_text,
    })


def page_not_found(request, exception):
    return render(request, '404.html', status=404)


def server_error(request):
    return render(request, '500.html', status=500)
