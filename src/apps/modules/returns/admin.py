"""Django admin registration for apps.modules.returns."""
from django.contrib import admin
from .models import ReturnHistoryEntry, ReturnItem, ReturnRequest



@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'order_id', 'status', 'reason', 'created_at')
    list_filter = ('status', 'reason')
    search_fields = ('id', 'user__email', 'order_id')
    # list_display traverses the `user` FK — select_related prevents N+1 in changelist.
    list_select_related = ('user',)


@admin.register(ReturnItem)
class ReturnItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'return_request', 'product_id', 'quantity', 'product_condition')
    # list_display shows `return_request` (str traverses FK) — select_related avoids N+1.
    list_select_related = ('return_request',)


@admin.register(ReturnHistoryEntry)
class ReturnHistoryEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'return_request', 'status_to', 'actor', 'created_at')
    # list_display traverses `return_request` and nullable `actor` FKs — select_related
    # avoids N+1 in changelist without crashing when actor is None.
    list_select_related = ('return_request', 'actor')
