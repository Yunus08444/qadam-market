
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

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
        'price_asc': ('price', '-created_at', '-pk'),
        'price_desc': ('-price', '-created_at', '-pk'),
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


SESSION_KEY = 'order_list'


def _order_items(request):
    cart = request.session.get(SESSION_KEY, {})
    products = Product.objects.filter(
        pk__in=[int(k) for k in cart if k.isdigit()],
        is_active=True,
        category__is_active=True,
    ).order_by('name')
    items, total = [], 0
    for product in products:
        qty = cart[str(product.pk)]
        unit = product.price
        if (
            product.wholesale_price is not None
            and product.wholesale_min_qty
            and qty >= product.wholesale_min_qty
        ):
            unit = product.wholesale_price
        line = unit * qty if unit is not None else None
        if line is not None:
            total += line
        items.append({'product': product, 'qty': qty, 'unit': unit, 'line': line})
    return items, total


def order_list(request):
    items, total = _order_items(request)
    lines = [
        f'{n}. {i["product"].name} (арт. {i["product"].article}) — {i["qty"]} шт.'
        for n, i in enumerate(items, 1)
    ]
    wa_text = ('Здравствуйте! Хочу заказать:\n' + '\n'.join(lines)) if lines else ''
    return render(request, 'order_list.html', {
        'items': items,
        'total': total,
        'wa_text': wa_text,
    })


@require_POST
def order_add(request, pk):
    get_object_or_404(Product, pk=pk, is_active=True, category__is_active=True)
    try:
        qty = max(1, min(int(request.POST.get('qty', 1)), 9999))
    except ValueError:
        qty = 1
    cart = request.session.get(SESSION_KEY, {})
    cart[str(pk)] = min(cart.get(str(pk), 0) + qty, 9999)
    request.session[SESSION_KEY] = cart
    back = request.META.get('HTTP_REFERER', '')
    if back and url_has_allowed_host_and_scheme(back, {request.get_host()}):
        return redirect(back)
    return redirect('order_list')


@require_POST
def order_set(request, pk):
    cart = request.session.get(SESSION_KEY, {})
    try:
        qty = max(0, min(int(request.POST.get('qty', 0)), 9999))
    except ValueError:
        qty = 0
    if str(pk) in cart:
        if qty:
            cart[str(pk)] = qty
        else:
            del cart[str(pk)]
        request.session[SESSION_KEY] = cart
    return redirect('order_list')
