from django.contrib import admin, messages

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    autocomplete_fields = ('product',)
    fields = ('product', 'product_name', 'article', 'size', 'quantity', 'unit_price', 'line_total')
    readonly_fields = ('line_total',)


def _status_action(status):
    """Build an admin action that moves selected orders to `status`."""

    def action(modeladmin, request, queryset):
        changed, skipped = 0, 0
        for order in queryset:
            if order.can_change_to(status):
                order.change_status(status)
                changed += 1
            else:
                skipped += 1
        if changed:
            modeladmin.message_user(request, f'Обновлено заказов: {changed}', messages.SUCCESS)
        if skipped:
            modeladmin.message_user(
                request,
                f'Пропущено: {skipped} — из их текущего статуса так перевести нельзя',
                messages.WARNING,
            )

    label = Order.Status(status).label
    action.__name__ = f'mark_{status}'
    action.short_description = f'Отметить как «{label}»'
    return action


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = (
        '__str__', 'phone', 'region', 'locality', 'status', 'total', 'deposit',
        'amount_due_display', 'source', 'created_at',
    )
    list_filter = ('status', 'source', 'region', 'created_at')
    search_fields = (
        'customer_name', 'phone', 'extra_phone', 'locality', 'address',
        'items__article', 'items__product_name',
    )
    date_hierarchy = 'created_at'
    list_per_page = 50
    # Status changes only through actions, so the allowed transitions are always respected
    readonly_fields = (
        'status', 'total', 'amount_due_display', 'public_id', 'created_at', 'updated_at',
    )
    fieldsets = (
        ('Клиент', {'fields': (('customer_name', 'source'), ('phone', 'extra_phone'))}),
        ('Доставка', {'fields': ('region', ('locality', 'address'), 'comment')}),
        ('Оплата и статус', {
            'fields': (('total', 'deposit', 'amount_due_display'), 'status'),
        }),
        ('Служебное', {
            'classes': ('collapse',),
            'fields': (('created_at', 'updated_at'), 'public_id'),
        }),
    )
    actions = [
        _status_action(Order.Status.CONFIRMED),
        _status_action(Order.Status.SHIPPED),
        _status_action(Order.Status.COMPLETED),
        _status_action(Order.Status.CANCELLED),
    ]

    def get_changeform_initial_data(self, request):
        # Orders added by hand usually come from the WhatsApp group
        return {'source': Order.Source.WHATSAPP, **super().get_changeform_initial_data(request)}

    @admin.display(description='Остаток к оплате')
    def amount_due_display(self, obj):
        return obj.amount_due if obj.pk else '—'

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.recalculate_total()
