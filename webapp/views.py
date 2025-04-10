from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum
from django.utils import timezone
from django.contrib import messages
from .models import Item, ItemIssue, Storage
from .forms import ItemIssueForm, ItemReturnForm

def index(request):
    total_cells = Storage.objects.aggregate(Sum('capacity'))['capacity__sum'] or 0
    occupied_cells = Item.objects.filter(status='in_stock').aggregate(Sum('quantity'))['quantity__sum'] or 0
    occupied_percentage = int((occupied_cells / total_cells * 100)) if total_cells > 0 else 0
    
    context = {
        'total_cells': total_cells,
        'occupied_cells': occupied_cells,
        'occupied_percentage': occupied_percentage,
        'items_count': Item.objects.filter(status='in_stock').count(),
        'issued_items_count': ItemIssue.objects.filter(return_date__isnull=True).aggregate(Sum('quantity'))['quantity__sum'] or 0,
        'recent_arrivals': Item.objects.order_by('-arrival_date')[:5],
        'recent_issues': ItemIssue.objects.order_by('-issue_date')[:5]
    }
    return render(request, 'webapp/index.html', context)

def issue_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.method == 'POST':
        form = ItemIssueForm(request.POST)
        if form.is_valid():
            quantity = form.cleaned_data['quantity']
            if quantity <= item.quantity:
                issue = form.save(commit=False)
                issue.item = item
                issue.save()
                
                # Уменьшаем количество товара на складе
                item.quantity -= quantity
                
                # Если все товары выданы, меняем статус
                if item.quantity == 0:
                    item.status = 'issued'
                
                item.save()
                
                messages.success(request, f'{quantity} {item.name} выдано {issue.employee}')
                return redirect('item_detail', item_id=item_id)
            else:
                messages.error(request, f'Недостаточно {item.name} на складе')
    else:
        form = ItemIssueForm()
    
    context = {
        'form': form,
        'item': item,
    }
    return render(request, 'webapp/issue_item.html', context)

def return_item(request, issue_id):
    issue = get_object_or_404(ItemIssue, id=issue_id)
    if request.method == 'POST':
        form = ItemReturnForm(request.POST, instance=issue)
        if form.is_valid():
            issue = form.save()
            issue.return_date = timezone.now()
            issue.save()
            
            # Возвращаем товар на склад
            item = issue.item
            item.quantity += issue.quantity
            item.status = 'in_stock'
            item.save()
            
            messages.success(request, f'{issue.quantity} {issue.item.name} возвращено на склад')
            return redirect('item_detail', item_id=issue.item.id)
    else:
        form = ItemReturnForm(instance=issue)
    
    context = {
        'form': form,
        'issue': issue,
    }
    return render(request, 'webapp/return_item.html', context)