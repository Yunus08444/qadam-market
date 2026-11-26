from django.urls import path

from . import views

urlpatterns = [
    path('', views.order_list, name='order_list'),
    path('add/<int:pk>/', views.order_add, name='order_add'),
    path('set/<int:pk>/', views.order_set, name='order_set'),
    path('checkout/', views.checkout, name='checkout'),
    path('done/<uuid:public_id>/', views.order_done, name='order_done'),
]
