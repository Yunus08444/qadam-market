from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from products.models import Product

from . import cart
from .forms import CheckoutForm
from .models import Order
from .services import create_order

LAST_ORDER_KEY = 'last_order'


def _whatsapp_text(items):
    lines = [
        f'{n}. {i["product"].name} (арт. {i["product"].article})'
        f'{", размер " + i["size"] if i["size"] else ""} — {i["qty"]} шт.'
        for n, i in enumerate(items, 1)
    ]
    return ('Здравствуйте! Хочу заказать:\n' + '\n'.join(lines)) if lines else ''


def order_list(request, form=None):
    items, total = cart.get_items(request.session)
    return render(request, 'order_list.html', {
        'items': items,
        'total': total,
        'wa_text': _whatsapp_text(items),
        'form': form or CheckoutForm(),
    })


@require_POST
def order_add(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True, category__is_active=True)

    size = request.POST.get('size', '').strip()
    options = product.size_options
    if options and size not in options:
        # The size must be chosen on the product page
        messages.error(request, 'Выберите размер')
        return redirect('product_detail', pk=pk)
    if not options:
        size = ''

    try:
        qty = max(1, min(int(request.POST.get('qty', 1)), cart.MAX_QTY))
    except ValueError:
        qty = 1
    key = cart.make_key(pk, size)
    items = cart.get_cart(request.session)
    items[key] = min(items.get(key, 0) + qty, cart.MAX_QTY)
    cart.save_cart(request.session, items)

    back = request.META.get('HTTP_REFERER', '')
    if back and url_has_allowed_host_and_scheme(back, {request.get_host()}):
        return redirect(back)
    return redirect('order_list')


@require_POST
def order_set(request, pk):
    key = cart.make_key(pk, request.POST.get('size', '').strip())
    items = cart.get_cart(request.session)
    try:
        qty = max(0, min(int(request.POST.get('qty', 0)), cart.MAX_QTY))
    except ValueError:
        qty = 0
    if key in items:
        if qty:
            items[key] = qty
        else:
            del items[key]
        cart.save_cart(request.session, items)
    return redirect('order_list')


@require_POST
def checkout(request):
    items, _ = cart.get_items(request.session)
    if not items:
        return redirect('order_list')

    form = CheckoutForm(request.POST)
    if not form.is_valid():
        return order_list(request, form=form)

    if form.is_spam():
        # Pretend everything is fine so the bot doesn't adapt
        cart.clear_cart(request.session)
        return redirect('catalog')

    order = create_order(items=items, **form.customer_data())
    cart.clear_cart(request.session)
    request.session[LAST_ORDER_KEY] = str(order.public_id)
    return redirect('order_done', public_id=order.public_id)


def order_done(request, public_id):
    # The page shows the customer's name and phone, so only the browser
    # that placed the order may open it.
    if request.session.get(LAST_ORDER_KEY) != str(public_id):
        raise Http404
    order = get_object_or_404(Order.objects.prefetch_related('items'), public_id=public_id)
    wa_text = f'Здравствуйте! Я оформил(а) заказ №{order.number} на сайте.'
    return render(request, 'orders/order_done.html', {'order': order, 'wa_text': wa_text})
