from django.contrib import admin
from .models import (
    Customer,
    StorageCell,
    Order,
    ReturnReason,
    OrderReturn,
    PickupSession
)

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email')
    search_fields = ('name', 'phone', 'email')


@admin.register(StorageCell)
class StorageCellAdmin(admin.ModelAdmin):
    list_display = ('number', 'is_occupied', 'current_customer')
    list_filter = ('is_occupied',)
    search_fields = ('number',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'name', 'customer', 'price', 'payment_status', 'status', 'storage_cell', 'is_under_inspection')
    list_filter = ('status', 'payment_status', 'is_under_inspection')
    search_fields = ('order_id', 'name', 'customer__name')
    date_hierarchy = 'created_at'


@admin.register(ReturnReason)
class ReturnReasonAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)


@admin.register(OrderReturn)
class OrderReturnAdmin(admin.ModelAdmin):
    list_display = ('order', 'reason', 'created_at')
    list_filter = ('reason',)
    date_hierarchy = 'created_at'


@admin.register(PickupSession)
class PickupSessionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'started_at', 'completed_at', 'is_active', 'include_package')
    list_filter = ('is_active', 'include_package')
    date_hierarchy = 'started_at'
