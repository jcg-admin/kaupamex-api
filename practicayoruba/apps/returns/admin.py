"""Django admin registration for apps.returns."""
from django.contrib import admin
from .models import ReturnHistoryEntry, ReturnItem, ReturnRequest



@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'order_id', 'status', 'reason', 'created_at')
    list_filter = ('status', 'reason')
    search_fields = ('id', 'user__email', 'order_id')


@admin.register(ReturnItem)
class ReturnItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'return_request', 'product_id', 'quantity', 'product_condition')


@admin.register(ReturnHistoryEntry)
class ReturnHistoryEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'return_request', 'status_to', 'actor', 'created_at')
