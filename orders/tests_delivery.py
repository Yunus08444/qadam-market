from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

from products.models import Product

from .models import Order
from .notifications import format_order_message
from .tests import VALID_CUSTOMER, OrderTestCase


class SizesTests(OrderTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.kerzy = Product.objects.create(
            category=cls.boots.category,
            name='Керзы',
            article='KERZ-1',
            sizes='40-44',
            price=Decimal('3500'),
            wholesale_price=Decimal('2800'),
            wholesale_min_qty=10,
        )

    def test_size_options_parsing(self):
        cases = {
            '40-44': ['40', '41', '42', '43', '44'],
            '39 – 41': ['39', '40', '41'],
            'S, M, L': ['S', 'M', 'L'],
            '42/43': ['42', '43'],
            '': [],
        }
        for sizes, expected in cases.items():
            self.assertEqual(Product(sizes=sizes).size_options, expected, sizes)

    def test_product_with_sizes_requires_a_valid_size(self):
        for size in ('', '99'):
            response = self.client.post(
                reverse('order_add', args=[self.kerzy.pk]), {'qty': '1', 'size': size}
            )
            self.assertRedirects(response, reverse('product_detail', args=[self.kerzy.pk]))
        self.assertEqual(self.client.get(reverse('order_list')).context['items'], [])

    def test_same_product_in_two_sizes_is_two_lines_with_wholesale_for_total_qty(self):
        url = reverse('order_add', args=[self.kerzy.pk])
        self.client.post(url, {'qty': '6', 'size': '41'})
        self.client.post(url, {'qty': '4', 'size': '43'})

        items = self.client.get(reverse('order_list')).context['items']

        self.assertEqual([(i['size'], i['qty']) for i in items], [('41', 6), ('43', 4)])
        # 6 + 4 = 10 pairs reach the wholesale minimum
        self.assertTrue(all(i['unit'] == Decimal('2800') for i in items))

    def test_removing_one_size_keeps_the_other(self):
        url = reverse('order_add', args=[self.kerzy.pk])
        self.client.post(url, {'qty': '1', 'size': '41'})
        self.client.post(url, {'qty': '1', 'size': '43'})

        self.client.post(reverse('order_set', args=[self.kerzy.pk]), {'qty': '0', 'size': '41'})

        items = self.client.get(reverse('order_list')).context['items']
        self.assertEqual([i['size'] for i in items], ['43'])

    def test_size_is_saved_in_order_and_notification(self):
        self.client.post(reverse('order_add', args=[self.kerzy.pk]), {'qty': '1', 'size': '43'})
        self.client.post(reverse('checkout'), VALID_CUSTOMER)

        order = Order.objects.get()
        self.assertEqual(order.items.get().size, '43')
        self.assertIn('Керзы (арт. KERZ-1), размер 43 × 1', format_order_message(order))


class DeliveryTests(OrderTestCase):
    def test_delivery_requires_locality(self):
        self.add_to_cart(self.boots, 1)

        response = self.client.post(
            reverse('checkout'), {**VALID_CUSTOMER, 'region': 'batken', 'locality': ''}
        )

        self.assertContains(response, 'Укажите район, город или село')
        self.assertEqual(Order.objects.count(), 0)

    def test_delivery_address_and_extra_phone_are_saved_and_sent(self):
        self.add_to_cart(self.boots, 1)

        self.client.post(reverse('checkout'), {
            **VALID_CUSTOMER,
            'extra_phone': '0700 123 456',
            'region': 'batken',
            'locality': 'Кызыл-Кия',
            'address': 'ул. Ленина 1',
        })

        order = Order.objects.get()
        self.assertEqual(order.source, Order.Source.SITE)
        self.assertEqual(order.full_address, 'Баткенская обл., Кызыл-Кия, ул. Ленина 1')
        text = format_order_message(order)
        self.assertIn('Телефон: +996 555 12 34 56, 0700 123 456', text)
        self.assertIn('Адрес: Баткенская обл., Кызыл-Кия, ул. Ленина 1', text)

    def test_pickup_order_does_not_need_address(self):
        self.add_to_cart(self.boots, 1)
        self.client.post(reverse('checkout'), VALID_CUSTOMER)

        order = Order.objects.get()
        self.assertFalse(order.is_delivery)
        self.assertIn('Получение: Самовывоз', format_order_message(order))

    def test_amount_due_subtracts_deposit(self):
        order = Order(total=Decimal('3500'), deposit=Decimal('1000'))
        self.assertEqual(order.amount_due, Decimal('2500'))
        order.deposit = Decimal('5000')
        self.assertEqual(order.amount_due, 0)


class ManualOrderAdminTests(OrderTestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser('admin', 'a@example.com', 'pass')
        self.client.force_login(admin)

    def post_order(self, items):
        data = {
            'customer_name': '',
            'source': 'whatsapp',
            'phone': '0777 000 000',
            'extra_phone': '',
            'region': 'naryn',
            'locality': 'Ат-Башы',
            'address': '',
            'comment': '',
            'deposit': '1000',
            'items-TOTAL_FORMS': str(len(items)),
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
        }
        for n, item in enumerate(items):
            for field, value in item.items():
                data[f'items-{n}-{field}'] = value
        return self.client.post(reverse('admin:orders_order_add'), data)

    def test_manager_adds_whatsapp_order_with_auto_prices(self):
        response = self.post_order([
            {'product': str(self.boots.pk), 'size': '42', 'quantity': '2'},
            {'product_name': 'Тёплые стельки', 'quantity': '1', 'unit_price': '300'},
        ])

        self.assertEqual(response.status_code, 302)
        order = Order.objects.get()
        self.assertEqual(order.source, Order.Source.WHATSAPP)
        self.assertEqual(order.customer_name, '')

        boots = order.items.get(product=self.boots)
        self.assertEqual(boots.product_name, 'Рабочие ботинки')
        self.assertEqual(boots.article, 'BOT-101')
        self.assertEqual(boots.unit_price, Decimal('1250.00'))
        self.assertEqual(boots.line_total, Decimal('2500.00'))

        self.assertEqual(order.total, Decimal('2800.00'))
        self.assertEqual(order.amount_due, Decimal('1800.00'))

    def test_item_needs_product_or_name(self):
        response = self.post_order([{'size': '42', 'quantity': '1'}])

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Выберите товар или впишите название')
        self.assertEqual(Order.objects.count(), 0)


class OrderCounterTests(OrderTestCase):
    def test_counter_ignores_removed_or_hidden_products(self):
        self.add_to_cart(self.boots, 2)
        self.add_to_cart(self.gloves, 3)
        self.assertEqual(self.client.get(reverse('home')).context['order_count'], 5)

        Product.objects.filter(pk=self.gloves.pk).update(is_active=False)
        self.assertEqual(self.client.get(reverse('home')).context['order_count'], 2)

        self.boots.delete()
        self.assertEqual(self.client.get(reverse('home')).context['order_count'], 0)
