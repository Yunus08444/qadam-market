"""Order list ("cart") stored in the session as {product_id: quantity}."""

from decimal import Decimal

from products.models import Product

SESSION_KEY = 'order_list'
MAX_QTY = 9999


def get_cart(session):
    return session.get(SESSION_KEY, {})


def save_cart(session, cart):
    session[SESSION_KEY] = cart


def clear_cart(session):
    session.pop(SESSION_KEY, None)


def unit_price(product, qty):
    """Retail price, or wholesale price when the quantity reaches the minimum."""
    if (
        product.wholesale_price is not None
        and product.wholesale_min_qty
        and qty >= product.wholesale_min_qty
    ):
        return product.wholesale_price
    return product.price


def get_items(session):
    """Return (items, total) for the products that are still available."""
    cart = get_cart(session)
    products = Product.objects.filter(
        pk__in=[int(key) for key in cart if key.isdigit()],
        is_active=True,
        category__is_active=True,
    ).order_by('name')

    items, total = [], Decimal('0')
    for product in products:
        qty = cart[str(product.pk)]
        unit = unit_price(product, qty)
        line = unit * qty if unit is not None else None
        if line is not None:
            total += line
        items.append({'product': product, 'qty': qty, 'unit': unit, 'line': line})
    return items, total
