from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path
from django.views.generic import TemplateView

from products.sitemaps import ProductSitemap, StaticSitemap
from products.views import (
    catalog,
    home,
    order_add,
    order_list,
    order_set,
    product_detail,
)

SITEMAPS = {'static': StaticSitemap, 'products': ProductSitemap}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('catalog/', catalog, name='catalog'),
    path('products/<int:pk>/', product_detail, name='product_detail'),
    path('order/', order_list, name='order_list'),
    path('order/add/<int:pk>/', order_add, name='order_add'),
    path('order/set/<int:pk>/', order_set, name='order_set'),
    path('about/', TemplateView.as_view(template_name='about.html'), name='about'),
    path('wholesale/', TemplateView.as_view(template_name='wholesale.html'), name='wholesale'),
    path('delivery/', TemplateView.as_view(template_name='delivery.html'), name='delivery'),
    path('sitemap.xml', sitemap, {'sitemaps': SITEMAPS}, name='sitemap'),
    path(
        'robots.txt',
        TemplateView.as_view(template_name='robots.txt', content_type='text/plain'),
        name='robots',
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'products.views.page_not_found'
handler500 = 'products.views.server_error'
