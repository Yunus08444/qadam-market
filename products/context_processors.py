import re

from django.conf import settings

from orders.cart import get_cart


def seller_contacts(request):
    phone = settings.SELLER_PHONE
    digits = re.sub(r'\D', '', phone)
    valid_whatsapp_number = 8 <= len(digits) <= 15 and not digits.startswith('0')

    return {
        'seller_phone': phone,
        'order_count': sum(get_cart(getattr(request, 'session', {})).values()),
        'seller_address': getattr(settings, 'SELLER_ADDRESS', ''),
        'seller_hours': getattr(settings, 'SELLER_HOURS', ''),
        'seller_instagram': getattr(settings, 'SELLER_INSTAGRAM', ''),
        'seller_phone_url': f'+{digits}' if valid_whatsapp_number else '',
        'seller_whatsapp_url': (
            f'https://wa.me/{digits}' if valid_whatsapp_number else ''
        ),
    }
