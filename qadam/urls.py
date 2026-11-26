"""
URL configuration for qadam project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap

from products.sitemaps import ProductSitemap, StaticSitemap
from products.views import (
    catalog, home, order_add, order_list, order_set, product_detail,
)


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
    path('sitemap.xml', sitemap, {'sitemaps': {'static': StaticSitemap, 'products': ProductSitemap}}, name='sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain'), name='robots'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'products.views.page_not_found'
handler500 = 'products.views.server_error'
