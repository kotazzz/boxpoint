from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('customer-search/', views.CustomerSearchView.as_view(), name='customer_search'),
    path('get-customer/', views.get_customer, name='get_customer'),
    path('pickup-process/<int:pk>/', views.PickupProcessView.as_view(), name='pickup_process'),
    path('pickup-cancel/<int:pk>/', views.PickupCancelView.as_view(), name='pickup_cancel'),
    path('pickup-close/<int:pk>/', views.PickupCloseView.as_view(), name='pickup_close'),
    path('order-inspection/<int:pk>/', views.OrderInspectionView.as_view(), name='order_inspection'),
    path('order-cancel/<int:pk>/', views.OrderCancelView.as_view(), name='order_cancel'),
    path('order-return-cancel/<int:pk>/', views.OrderReturnCancelView.as_view(), name='order_return_cancel'),
    path('pickup-confirmation/<int:pk>/', views.PickupConfirmationView.as_view(), name='pickup_confirmation'),
    path('order-search/', views.OrderSearchView.as_view(), name='order_search'),
    path('order-receiving/', views.OrderReceivingView.as_view(), name='order_receiving'),
    path('system/', views.SystemView.as_view(), name='system'),
    # Add the delivery summary URL
    path('delivery-summary/<int:order_id>/', views.delivery_summary, name='delivery_summary'),
    path('storage-visualization/', views.StorageVisualizationView.as_view(), name='storage_visualization'),
    path('customer-detail/<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
]