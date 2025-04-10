from django.db import models
import shortuuid
from django.utils import timezone
from django.core.exceptions import ValidationError


def generate_order_id():
    """Generate a unique order ID with BP prefix"""
    return f"BP-{shortuuid.uuid()[:8].upper()}"


class Customer(models.Model):
    name = models.CharField(max_length=100, verbose_name="Имя клиента")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    
    def __str__(self):
        return f"{self.name} ({self.phone})"
    
    def get_pending_orders(self):
        """Return orders ready for pickup"""
        if hasattr(self, 'orders'):
            return self.orders.filter(
                status='pending',
                reception_status='received'
            )
        return Order.objects.none()
        
    def get_total_orders_count(self):
        """Return the total count of all customer orders"""
        if hasattr(self, 'orders'):
            return self.orders.count()
        return 0 # Return 0 if accessed before orders relation is established

    def has_active_pickup_session(self):
        """Check if customer has an active pickup session"""
        if hasattr(self, 'pickup_sessions'):
            return self.pickup_sessions.filter(is_active=True).exists()
        return False

    
    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"


class StorageCell(models.Model):
    number = models.CharField(max_length=10, unique=True, verbose_name="Номер ячейки")
    is_occupied = models.BooleanField(default=False, verbose_name="Занята")
    current_customer = models.ForeignKey(
        Customer, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="storage_cells",
        verbose_name="Текущий клиент"
    )
    
    def __str__(self):
        status = "Занята" if self.is_occupied else "Свободна"
        return f"Ячейка {self.number} ({status})"
    
    def assign_to_customer(self, customer):
        """Assign cell to a customer"""
        self.is_occupied = True
        self.current_customer = customer
        self.save()
    
    def release(self):
        """Release cell (mark as unoccupied)"""
        self.is_occupied = False
        self.current_customer = None
        self.save()
    
    @classmethod
    def get_available(cls):
        """Get all available cells"""
        return cls.objects.filter(is_occupied=False)
    
    class Meta:
        verbose_name = "Ячейка хранения"
        verbose_name_plural = "Ячейки хранения"
        ordering = ['number']  # Sort cells by number


class Order(models.Model):
    RECEPTION_STATUS_CHOICES = [
        ('pending', 'В обработке'),
        ('received', 'Принят'),
        ('cancelled', 'Отменен'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'В ожидании'),
        ('delivered', 'Доставлен'),
        ('returned', 'Возвращен'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('prepaid', 'Предоплата'),
        ('postpaid', 'Наложенный платеж'),
    ]
    
    order_id = models.CharField(max_length=50, unique=True, default=generate_order_id, verbose_name="ID заказа")
    barcode = models.CharField(max_length=100, blank=True, null=True, verbose_name="Штрихкод")
    name = models.CharField(max_length=255, verbose_name="Наименование")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    size = models.CharField(max_length=20, blank=True, null=True, verbose_name="Размер")
    color = models.CharField(max_length=50, blank=True, null=True, verbose_name="Цвет")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Цена")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='postpaid', verbose_name="Статус оплаты")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус заказа")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="orders", verbose_name="Клиент")
    storage_cell = models.ForeignKey("StorageCell", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders", verbose_name="Ячейка хранения")
    is_picked_up = models.BooleanField(default=False, verbose_name="Выдан")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    reception_status = models.CharField(max_length=20, choices=RECEPTION_STATUS_CHOICES, default='pending', verbose_name="Статус приемки")
    reception_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата приемки")
    received_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата получения")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата выдачи")
    is_under_inspection = models.BooleanField(default=False, verbose_name="На проверке")
    notes = models.TextField(blank=True, null=True, verbose_name="Примечания")
    # Возвратные поля
    marked_for_return = models.BooleanField(default=False, verbose_name="Отмечен для возврата")
    return_reason_id = models.IntegerField(blank=True, null=True, verbose_name="ID причины возврата")
    return_notes = models.TextField(blank=True, null=True, verbose_name="Примечания к возврату")

    def __str__(self):
        return f"{self.order_id} - {self.name} ({self.customer.name})"
    
    def is_available_for_pickup(self):
        """Check if this order is available for pickup"""
        return self.reception_status == 'received' and not self.is_picked_up and self.status == 'pending'
    
    def complete_receipt(self, storage_cell=None):
        """Mark order as received and assign to storage cell"""
        now = timezone.now()
        
        self.reception_status = 'received'
        self.reception_date = now
        self.received_at = now
        
        if storage_cell:
            self.storage_cell = storage_cell
            storage_cell.assign_to_customer(self.customer)
            
        self.save()
        return True
        
    def mark_delivered(self):
        """Mark order as delivered"""
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        self.is_picked_up = True
        self.save()
        
    def mark_for_return(self, reason_id, notes=None):
        """Mark order for return"""
        self.marked_for_return = True
        self.return_reason_id = reason_id
        if notes:
            self.return_notes = notes
        self.save()
        
    def cancel_return(self):
        """Cancel return"""
        self.marked_for_return = False
        self.return_reason_id = None
        self.return_notes = None
        self.save()
        
    def process_return(self):
        """Process return and update order status"""
        if not self.marked_for_return or not self.return_reason_id:
            return False
            
        self.status = 'returned'
        self.save()
        
        # Create return record
        reason = ReturnReason.objects.get(id=self.return_reason_id)
        OrderReturn.objects.create(
            order=self,
            reason=reason,
            notes=self.return_notes or ''
        )
        return True
    
    def clean(self):
        """Validate model instance"""
        # Ensure consistency between status and dates
        if self.status == 'delivered' and not self.delivered_at:
            raise ValidationError('Delivered orders must have a delivery date')
            
        # Check return consistency
        if self.status == 'returned' and not self.return_reason_id:
            raise ValidationError('Returned orders must have a return reason')
    
    def save(self, *args, **kwargs):
        if self.reception_status == 'received' and not self.reception_date:
            self.reception_date = timezone.now()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-created_at']


class ReturnReason(models.Model):
    INSPECTION_CATEGORY = [
        ('unopened', 'Невскрытый товар'),
        ('opened', 'Вскрытый товар'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Причина возврата")
    category = models.CharField(max_length=10, choices=INSPECTION_CATEGORY, verbose_name="Категория")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Причина возврата"
        verbose_name_plural = "Причины возврата"


class OrderReturn(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="return_info", verbose_name="Заказ")
    reason = models.ForeignKey(ReturnReason, on_delete=models.CASCADE, verbose_name="Причина возврата")
    notes = models.TextField(blank=True, verbose_name="Примечания")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата возврата")
    
    def __str__(self):
        return f"Возврат заказа {self.order.order_id}"
    
    class Meta:
        verbose_name = "Возврат заказа"
        verbose_name_plural = "Возвраты заказов"


class PickupSession(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="pickup_sessions", verbose_name="Клиент")
    orders = models.ManyToManyField(Order, related_name="pickup_sessions", verbose_name="Заказы")
    include_package = models.BooleanField(default=False, verbose_name="Добавить пакет")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата начала")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата завершения")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    is_cancelled = models.BooleanField(default=False, verbose_name="Отменена")
    cancel_reason = models.TextField(blank=True, null=True, verbose_name="Причина отмены")
    notes = models.TextField(blank=True, null=True, verbose_name="Примечания") # Add notes field
    
    def __str__(self):
        if self.is_cancelled:
            return f"Выдача {self.customer.name} (Отменена)"
        status = "Активна" if self.is_active else "Завершена"
        return f"Выдача {self.customer.name} ({status})"
    
    def has_received_orders(self):
        """Check if there are any received orders in this pickup session"""
        return self.orders.filter(reception_status='received').exists()
    
    def count_received_orders(self):
        """Count the number of received orders in this pickup session"""
        return self.orders.filter(reception_status='received').count()
    
    def cancel(self, reason=None):
        """Cancel the pickup session and reset all associated orders"""
        self.is_cancelled = True
        self.is_active = False
        self.completed_at = timezone.now()
        
        if reason:
            self.cancel_reason = reason
        
        # Reset all orders that were marked as picked up during this session
        for order in self.orders.all():
            if order.is_picked_up:
                order.is_picked_up = False
                order.save()
        
        self.save()
        return True
        
    def complete(self, selected_order_ids=None):
        """Complete the pickup session and process all orders"""
        now = timezone.now()
        orders = self.orders.all()
        
        # Process orders marked for return
        orders_to_return = orders.filter(marked_for_return=True)
        for order in orders_to_return:
            order.process_return()
            
        # Process orders for delivery
        if selected_order_ids:
            for order in orders.filter(marked_for_return=False):
                if str(order.id) in selected_order_ids:
                    order.mark_delivered()
        
        # Mark session as completed
        self.is_active = False
        self.completed_at = now
        self.save()
        
        # Check if we can release storage cells
        remaining_pending_orders = Order.objects.filter(
            customer=self.customer, 
            status='pending', 
            reception_status='received'
        ).exists()
        
        if not remaining_pending_orders:
            cells = StorageCell.objects.filter(current_customer=self.customer)
            for cell in cells:
                cell.release()
    
    class Meta:
        verbose_name = "Сессия выдачи"
        verbose_name_plural = "Сессии выдачи"
