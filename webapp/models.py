from django.db import models
from django.utils import timezone

class Storage(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название")
    capacity = models.PositiveIntegerField(verbose_name="Вместимость")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Ячейка хранения"
        verbose_name_plural = "Ячейки хранения"

class Item(models.Model):
    STATUS_CHOICES = [
        ('in_stock', 'На складе'),
        ('issued', 'Выдан'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Название")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество")
    storage = models.ForeignKey(Storage, on_delete=models.SET_NULL, null=True, blank=True, related_name='items', verbose_name="Ячейка хранения")
    arrival_date = models.DateField(default=timezone.now, verbose_name="Дата поступления")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_stock', verbose_name="Статус")
    
    def __str__(self):
        return f"{self.name} ({self.quantity})"
    
    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

class ItemIssue(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='issues', verbose_name="Товар")
    employee = models.CharField(max_length=100, verbose_name="Сотрудник")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    issue_date = models.DateTimeField(default=timezone.now, verbose_name="Дата выдачи")
    return_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата возврата")
    notes = models.TextField(blank=True, null=True, verbose_name="Примечания")
    
    def __str__(self):
        return f"{self.item.name} - {self.employee}"
    
    class Meta:
        verbose_name = "Выдача"
        verbose_name_plural = "Выдачи"
