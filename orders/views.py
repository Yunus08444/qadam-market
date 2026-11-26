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
        f'{n}. {i["product"].name} (арт. {i["product"].article}) — {i["qty"]} шт.'
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
    get_object_or_404(Product, pk=pk, is_active=True, category__is_active=True)
    try:
        qty = max(1, min(int(request.POST.get('qty', 1)), cart.MAX_QTY))
    except ValueError:
        qty = 1
    items = cart.get_cart(request.session)
    items[str(pk)] = min(items.get(str(pk), 0) + qty, cart.MAX_QTY)
    cart.save_cart(request.session, items)

    back = request.META.get('HTTP_REFERER', '')
    if back and url_has_allowed_host_and_scheme(back, {request.get_host()}):
        return redirect(back)
    return redirect('order_list')


@require_POST
def order_set(request, pk):
    items = cart.get_cart(request.session)
    try:
        qty = max(0, min(int(request.POST.get('qty', 0)), cart.MAX_QTY))
    except ValueError:
        qty = 0
    if str(pk) in items:
        if qty:
            items[str(pk)] = qty
        else:
            del items[str(pk)]
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

    order = create_order(
        customer_name=form.cleaned_data['customer_name'],
        phone=form.cleaned_data['phone'],
        comment=form.cleaned_data['comment'],
        items=items,
    )
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
