from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from orders.models import Order
from products.models import Category, Product


class ApiTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.shoes = Category.objects.create(name='Обувь', slug='obuv')
        cls.hidden = Category.objects.create(name='Скрытая', slug='hidden', is_active=False)
        cls.kerzy = Product.objects.create(
            category=cls.shoes, name='Керзы', article='KERZ-1', sizes='40-44',
            price=Decimal('3500'), wholesale_price=Decimal('2800'), wholesale_min_qty=10,
            stock=5,
        )
        cls.gloves = Product.objects.create(
            category=cls.shoes, name='Перчатки', article='GLOVE-1', price=None,
        )
        cls.secret = Product.objects.create(
            category=cls.hidden, name='Секрет', article='SECRET-1', price=Decimal('1'),
        )

    def setUp(self):
        cache.clear()  # throttling counters live in the cache


class CatalogApiTests(ApiTestCase):
    def test_categories_list_only_active_with_counts(self):
        response = self.client.get(reverse('category-list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(c['slug'], c['product_count']) for c in response.data], [('obuv', 2)]
        )

    def test_products_list_hides_inactive_and_is_paginated(self):
        response = self.client.get(reverse('product-list'))

        self.assertEqual(response.data['count'], 2)
        articles = {p['article'] for p in response.data['results']}
        self.assertEqual(articles, {'KERZ-1', 'GLOVE-1'})

    def test_search_filter_and_ordering(self):
        url = reverse('product-list')

        by_article = self.client.get(url, {'search': 'kerz'})
        self.assertEqual([p['article'] for p in by_article.data['results']], ['KERZ-1'])

        in_stock = self.client.get(url, {'in_stock': 'true'})
        self.assertEqual([p['article'] for p in in_stock.data['results']], ['KERZ-1'])

        by_category = self.client.get(url, {'category': 'hidden'})
        self.assertEqual(by_category.data['count'], 0)

        # Products without a price go last in both directions
        for ordering in ('price', '-price'):
            response = self.client.get(url, {'ordering': ordering})
            self.assertEqual(response.data['results'][-1]['article'], 'GLOVE-1', ordering)

    def test_product_detail(self):
        response = self.client.get(reverse('product-detail', args=[self.kerzy.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['size_options'], ['40', '41', '42', '43', '44'])
        self.assertEqual(response.data['category'], 'obuv')
        self.assertTrue(response.data['in_stock'])
        self.assertEqual(response.data['images'], [])

        hidden = self.client.get(reverse('product-detail', args=[self.secret.pk]))
        self.assertEqual(hidden.status_code, 404)

    def test_catalog_is_read_only(self):
        response = self.client.post(reverse('product-list'), {'name': 'x'})
        self.assertEqual(response.status_code, 405)


class OrderApiTests(ApiTestCase):
    def order_payload(self, **overrides):
        payload = {
            'customer_name': 'Азамат',
            'phone': '+996 555 12 34 56',
            'region': 'batken',
            'locality': 'Кызыл-Кия',
            'items': [
                {'product': self.kerzy.pk, 'size': '41', 'quantity': 6},
                {'product': self.kerzy.pk, 'size': '43', 'quantity': 4},
                {'product': self.gloves.pk, 'quantity': 2},
            ],
        }
        payload.update(overrides)
        return payload

    @mock.patch('orders.services.notify_new_order')
    def test_create_order_prices_like_the_website(self, notify):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('order-list'), self.order_payload(), format='json'
            )

        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get()
        self.assertEqual(response.data['public_id'], str(order.public_id))
        self.assertEqual(response.data['number'], order.number)
        self.assertNotIn('phone', response.data)
        # 6 + 4 pairs reach the wholesale minimum of 10
        self.assertEqual(order.total, Decimal('28000'))
        self.assertEqual(order.source, Order.Source.SITE)
        self.assertEqual(
            sorted(order.items.values_list('size', 'quantity')), [('', 2), ('41', 6), ('43', 4)]
        )
        notify.assert_called_once_with(order.pk)

    def test_create_order_validation_errors(self):
        url = reverse('order-list')
        cases = [
            ({'items': []}, 'items'),
            ({'items': [{'product': self.kerzy.pk, 'size': '99', 'quantity': 1}]}, 'items'),
            ({'items': [{'product': self.secret.pk, 'quantity': 1}]}, 'items'),
            ({'items': [{'product': self.gloves.pk, 'quantity': 0}]}, 'items'),
            ({'locality': ''}, 'locality'),
            ({'customer_name': ''}, 'customer_name'),
            ({'phone': 'abc'}, 'phone'),
        ]
        for overrides, field in cases:
            response = self.client.post(url, self.order_payload(**overrides), format='json')
            self.assertEqual(response.status_code, 400, overrides)
            self.assertIn(field, response.data, overrides)
        self.assertEqual(Order.objects.count(), 0)

    def test_retrieve_order_status_by_public_id(self):
        order = Order.objects.create(phone='+996555000000', customer_name='A')

        response = self.client.get(reverse('order-detail', args=[order.public_id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'new')
        self.assertEqual(response.data['status_display'], 'Новый')
        self.assertNotIn('phone', response.data)

    def test_orders_cannot_be_listed_or_found_by_number(self):
        order = Order.objects.create(phone='+996555000000')

        self.assertEqual(self.client.get(reverse('order-list')).status_code, 405)
        self.assertEqual(self.client.get(f'/api/v1/orders/{order.pk}/').status_code, 404)

    @mock.patch.object(ScopedRateThrottle, 'THROTTLE_RATES', {'order_create': '2/hour'})
    @mock.patch('orders.services.notify_new_order')
    def test_order_creation_is_throttled(self, notify):
        url = reverse('order-list')
        statuses = [
            self.client.post(url, self.order_payload(), format='json').status_code
            for _ in range(3)
        ]

        self.assertEqual(statuses, [201, 201, 429])


class ManagerApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.manager = User.objects.create_user('manager', password='pass', is_staff=True)
        self.customer = User.objects.create_user('customer', password='pass')
        self.order = Order.objects.create(
            phone='+996555000001', customer_name='A', source=Order.Source.WHATSAPP
        )
        Order.objects.create(phone='+996555000002', customer_name='B')

    def auth(self, user):
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_requires_staff_token(self):
        url = reverse('manager-order-list')
        self.assertEqual(self.client.get(url).status_code, 401)

        self.auth(self.customer)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_obtain_token_with_password(self):
        response = self.client.post(
            reverse('api-token'), {'username': 'manager', 'password': 'pass'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['token'], Token.objects.get(user=self.manager).key)

    def test_list_filter_and_full_details(self):
        self.auth(self.manager)

        response = self.client.get(reverse('manager-order-list'), {'source': 'whatsapp'})

        self.assertEqual(response.data['count'], 1)
        result = response.data['results'][0]
        self.assertEqual(result['phone'], '+996555000001')
        self.assertEqual(result['full_address'], 'Самовывоз — рынок Дордой')

    def test_change_status_follows_the_workflow(self):
        self.auth(self.manager)
        url = reverse('manager-order-status', args=[self.order.pk])

        ok = self.client.post(url, {'status': 'confirmed'})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.data['status'], 'confirmed')

        skip = self.client.post(url, {'status': 'completed'})
        self.assertEqual(skip.status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)


class ApiDocsTests(ApiTestCase):
    def test_schema_and_swagger_ui(self):
        schema = self.client.get(reverse('api-schema'))
        self.assertEqual(schema.status_code, 200)
        self.assertIn(b'Qadam Market API', schema.content)

        self.assertEqual(self.client.get(reverse('api-docs')).status_code, 200)
