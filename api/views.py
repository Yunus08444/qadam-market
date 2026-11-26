import django_filters
from django.db.models import Count, F, Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from orders.models import Order
from products.models import Category, Product

from .serializers import (
    CategorySerializer,
    OrderCreateSerializer,
    OrderManagerSerializer,
    OrderPublicSerializer,
    OrderStatusSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)

# --- Catalog -----------------------------------------------------------------


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Active categories with the number of available products."""

    serializer_class = CategorySerializer
    lookup_field = 'slug'
    pagination_class = None

    def get_queryset(self):
        return (
            Category.objects.filter(is_active=True)
            .annotate(product_count=Count('products', filter=Q(products__is_active=True)))
            .order_by('name')
        )


class ProductFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name='category__slug')
    in_stock = django_filters.BooleanFilter(method='filter_in_stock')
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')

    class Meta:
        model = Product
        fields = ('category', 'is_featured')

    def filter_in_stock(self, queryset, name, value):
        return queryset.filter(stock__gt=0) if value else queryset.filter(stock=0)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """Catalog: search by name or article, filter, sort.

    Products without a price are always listed last when sorting by price.
    """

    filterset_class = ProductFilter
    search_fields = ('name', 'article')
    ordering_fields = ('price', 'created_at', 'name')
    ordering = ('-created_at', '-pk')

    def get_queryset(self):
        queryset = Product.objects.filter(
            is_active=True, category__is_active=True
        ).select_related('category')
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related('extra_images')
        return queryset

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        ordering = self.request.query_params.get('ordering', '')
        if ordering in ('price', '-price'):
            price = F('price').desc if ordering == '-price' else F('price').asc
            queryset = queryset.order_by(price(nulls_last=True), '-pk')
        return queryset

    def get_serializer_class(self):
        return ProductDetailSerializer if self.action == 'retrieve' else ProductListSerializer


# --- Orders ------------------------------------------------------------------


class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Placing orders and checking their status — no account needed.

    The order is looked up by its `public_id` (a random UUID returned on
    creation), so nobody can enumerate other people's orders.
    """

    queryset = Order.objects.prefetch_related('items')
    lookup_field = 'public_id'
    throttle_scope = 'order_create'

    def get_throttles(self):
        return [ScopedRateThrottle()] if self.action == 'create' else []

    def get_serializer_class(self):
        return OrderCreateSerializer if self.action == 'create' else OrderPublicSerializer

    @extend_schema(responses={201: OrderPublicSerializer})
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


class ManagerOrderViewSet(viewsets.ReadOnlyModelViewSet):
    """All orders for managers. Requires a staff user (token or session)."""

    serializer_class = OrderManagerSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ('status', 'source', 'region')
    search_fields = ('customer_name', 'phone', 'extra_phone', 'locality', 'items__article')
    ordering_fields = ('created_at', 'total')
    ordering = ('-created_at',)

    def get_queryset(self):
        return Order.objects.prefetch_related('items').distinct()

    @extend_schema(request=OrderStatusSerializer, responses={200: OrderManagerSerializer})
    @action(detail=True, methods=['post'])
    def status(self, request, pk=None):
        """Move the order to the next status (new → confirmed → shipped → completed)."""
        order = self.get_object()
        serializer = OrderStatusSerializer(data=request.data, context={'order': order})
        serializer.is_valid(raise_exception=True)
        order.change_status(serializer.validated_data['status'])
        return Response(self.get_serializer(order).data, status=status.HTTP_200_OK)
