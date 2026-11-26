from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Product


class StaticSitemap(Sitemap):
    def items(self):
        return ['home', 'catalog', 'about', 'wholesale', 'delivery']

    def location(self, item):
        return reverse(item)


class ProductSitemap(Sitemap):
    def items(self):
        return Product.objects.filter(is_active=True, category__is_active=True)

    def location(self, obj):
        return reverse('product_detail', args=[obj.pk])

    def lastmod(self, obj):
        return obj.updated_at
