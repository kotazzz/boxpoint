from django.db import models
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.generic import TemplateView, ListView, DetailView, UpdateView
from django.contrib import messages
from django.db.models import Q
from faker import Faker
import random
from datetime import timedelta

from .models import (
    Customer,
    StorageCell,
    Order,
    ReturnReason,
    OrderReturn,
    PickupSession
)


class HomeView(ListView):
    model = PickupSession
    template_name = 'core/home.html'
    context_object_name = 'active_sessions'

    def get_queryset(self):
        # Оптимизируем запрос, чтобы сразу получить связанные заказы
        return PickupSession.objects.filter(is_active=True).prefetch_related('orders').order_by('-started_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Общее количество заказов ожидающих приемки
        context['total_pending_orders'] = Order.objects.filter(reception_status='pending').count()
        
        # Получаем статистику о складе для домашней страницы
        context['total_cells_count'] = StorageCell.objects.count()
        context['occupied_cells_count'] = StorageCell.objects.filter(is_occupied=True).count()
        context['free_cells_count'] = StorageCell.objects.filter(is_occupied=False).count()
        
        # Добавляем информацию о наличии постоплаты для каждой сессии
        active_sessions_with_postpaid_info = []
        for session in context['active_sessions']:
            # Проверяем все заказы клиента, которые в процессе выдачи (pending + received)
            has_postpaid = Order.objects.filter(
                customer=session.customer,
                status='pending',
                reception_status='received',
                payment_status='postpaid'
            ).exists()
            
            session.has_postpaid = has_postpaid
            active_sessions_with_postpaid_info.append(session)
        
        context['active_sessions'] = active_sessions_with_postpaid_info
        return context


class CustomerSearchView(ListView):
    model = Customer
    template_name = 'core/customer_search.html'
    context_object_name = 'customers'
    paginate_by = 10

    def get_queryset(self):
        query = self.request.GET.get('q', '')
        
        # Base queryset - only show customers with at least one pending order ready for pickup
        base_queryset = Customer.objects.filter(
            orders__status='pending',
            orders__reception_status='received'
        ).distinct()
        
        if query:
            # Filter the already filtered customers by name or phone
            return base_queryset.filter(
                Q(name__icontains=query) | Q(phone__icontains=query)
            ).order_by('name')
        
        return base_queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '')
        context['search_query'] = query if query else ''
        
        # Add pending order counts for each customer
        customers_with_counts = []
        for customer in context['customers']:
            pending_count = Order.objects.filter(
                customer=customer,
                status='pending',
                reception_status='received'
            ).count()
            customer.pending_count = pending_count
            customers_with_counts.append(customer)
        
        context['customers'] = customers_with_counts
        return context


class PickupProcessView(DetailView):
    model = Customer
    template_name = 'core/pickup_process.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.get_object()
        
        # Check if the customer has any pending orders
        has_pending_orders = Order.objects.filter(
            customer=customer,
            status='pending',
            reception_status='received'
        ).exists()
        
        if not has_pending_orders:
            context['no_pending_orders'] = True
            messages.warning(self.request, f'У клиента {customer.name} нет заказов, ожидающих выдачи.')
            return context
        
        # Get or create a pickup session for this customer
        session, created = PickupSession.objects.get_or_create(
            customer=customer,
            is_active=True,
            defaults={'started_at': timezone.now()}
        )
        
        # Get pending orders for this customer
        pending_orders = Order.objects.filter(
            customer=customer,
            status='pending',
            reception_status='received'
        ).select_related('storage_cell')
        
        # Count prepaid and postpaid orders
        prepaid_count = pending_orders.filter(payment_status='prepaid').count()
        postpaid_count = pending_orders.filter(payment_status='postpaid').count()
        marked_for_return_count = pending_orders.filter(marked_for_return=True).count()
        
        # Add session to the context
        context['session'] = session
        context['pending_orders'] = pending_orders
        context['prepaid_count'] = prepaid_count
        context['postpaid_count'] = postpaid_count
        context['marked_for_return_count'] = marked_for_return_count
        
        return context
    
    def post(self, request, *args, **kwargs):
        customer = self.get_object()
        
        # Get session for this customer
        session, created = PickupSession.objects.get_or_create(
            customer=customer,
            is_active=True,
            defaults={'started_at': timezone.now()}
        )
        
        # Get selected orders
        order_ids = request.POST.getlist('deliver_orders')
        
        # Проверяем наличие товаров, отмеченных на возврат
        marked_for_return_exist = Order.objects.filter(
            customer=customer,
            status='pending',
            reception_status='received',
            marked_for_return=True
        ).exists()
        
        # Redirect to confirmation page with selected orders
        if order_ids:
            # Store selected orders in session
            request.session['selected_order_ids'] = order_ids
            return redirect('pickup_confirmation', pk=session.id)
        elif marked_for_return_exist:
            # Если нет выбранных заказов, но есть отмеченные на возврат - всё равно направляем на страницу подтверждения
            request.session['selected_order_ids'] = []
            messages.info(request, 'Нет заказов для выдачи, но обнаружены заказы, отмеченные на возврат.')
            return redirect('pickup_confirmation', pk=session.id)
        else:
            messages.warning(request, 'Не выбрано ни одного заказа для выдачи.')
            return redirect('pickup_process', pk=customer.id)


class OrderInspectionView(UpdateView):
    model = Order
    template_name = 'core/order_inspection.html'
    fields = ['is_under_inspection']
    
    def form_valid(self, form):
        order = form.save(commit=False)
        order.is_under_inspection = True
        order.save()
        messages.success(self.request, f'Заказ {order.order_id} поставлен на проверку')
        return redirect('pickup_process', pk=order.customer.pk)


class OrderCancelView(UpdateView):
    model = Order
    template_name = 'core/order_cancel.html'
    fields = []
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.get_object()
        
        # Get reasons based on whether the order was inspected or not
        category = 'opened' if order.is_under_inspection else 'unopened'
        context['reasons'] = ReturnReason.objects.filter(category=category)
        context['order'] = order
        
        return context
    
    def post(self, request, *args, **kwargs):
        order = self.get_object()
        reason_id = request.POST.get('reason')
        notes = request.POST.get('notes', '')
        
        if not reason_id:
            messages.error(request, 'Необходимо указать причину возврата')
            return self.get(request, *args, **kwargs)
            
        # Get the reason to validate it exists
        reason = get_object_or_404(ReturnReason, id=reason_id)
            
        # Use the model method to mark for return
        order.mark_for_return(reason.id, notes)
        
        messages.success(request, f'Заказ {order.order_id} отмечен для возврата. Завершите выдачу, чтобы увидеть финансовый итог.')
        return redirect('pickup_process', pk=order.customer.pk)


class PickupConfirmationView(UpdateView):
    model = PickupSession
    template_name = 'core/pickup_confirmation.html'
    fields = ['include_package']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.get_object()
        
        # Get all orders for this session's customer with prefetched storage_cell data
        orders = Order.objects.filter(
            customer=session.customer
        ).select_related('storage_cell')
        
        # Get selected order IDs from the session storage or URL parameters
        selected_order_ids = self.request.session.get('selected_order_ids', [])
        if 'order_ids' in self.request.GET:
            selected_order_ids = self.request.GET.get('order_ids').split(',')
        
        # Count orders marked for return
        marked_for_return_orders = orders.filter(
            status='pending',
            reception_status='received', 
            marked_for_return=True
        )
        marked_for_return_count = marked_for_return_orders.count()
        
        # Calculate summaries for confirmed orders
        delivered_count = len(selected_order_ids)
        returned_count = orders.filter(status='returned').count()
        
        # Only count actually received pending orders that aren't being delivered or marked for return
        pending_count = orders.filter(
            status='pending',
            reception_status='received'
        ).exclude(
            id__in=selected_order_ids
        ).exclude(
            marked_for_return=True
        ).count()
        
        # Calculate financial totals
        prepaid_total = sum(order.price for order in orders.filter(
            id__in=selected_order_ids, 
            payment_status='prepaid'
        ))
        
        postpaid_total = sum(order.price for order in orders.filter(
            id__in=selected_order_ids,
            payment_status='postpaid'
        ))
        
        refund_total = sum(order.price for order in marked_for_return_orders.filter(
            payment_status='prepaid'
        ))
        
        # Calculate totals to display on the confirmation page
        total_to_collect = postpaid_total
        total_to_refund = refund_total
        final_balance = total_to_collect - total_to_refund
        
        context.update({
            'orders': orders,
            'selected_orders': selected_order_ids,
            'delivered_count': delivered_count,
            'returned_count': returned_count + marked_for_return_count,
            'pending_count': pending_count,
            'prepaid_total': prepaid_total,
            'postpaid_total': postpaid_total,
            'refund_total': refund_total,
            'marked_for_return_count': marked_for_return_count,
            'total_to_collect': total_to_collect,
            'total_to_refund': total_to_refund,
            'final_balance': final_balance
        })
        
        return context
    
    def form_valid(self, form):
        session = form.save(commit=False)
        # Get selected order IDs from the current form submission
        selected_order_ids = self.request.POST.getlist('deliver_orders')
        
        # Use the complete() method on the PickupSession model to process orders
        session.complete(selected_order_ids)
                
        # Generate summary information for success message
        customer = session.customer
        delivered_count = Order.objects.filter(
            customer=customer,
            status='delivered'
        ).count()
        
        returned_count = Order.objects.filter(
            customer=customer,
            status='returned'
        ).count()
        
        pending_count = Order.objects.filter(
            customer=customer,
            status='pending',
            reception_status='received'
        ).count()
        
        messages.success(
            self.request, 
            f'Выдача завершена: {delivered_count} выдано, {returned_count} возвращено, {pending_count} оставлено.'
        )

        return redirect('delivery_summary', order_id=customer.id)


class OrderSearchView(TemplateView):
    template_name = 'core/order_search.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        
        if (order_id):
            # Validate that the order_id is valid before trying to query
            try:
                order = Order.objects.get(order_id=order_id)
                context['order'] = order
            except Order.DoesNotExist:
                context['not_found'] = True
                messages.error(self.request, f'Заказ с ID {order_id} не найден')
                
        return context


class OrderReceivingView(TemplateView):
    template_name = 'core/order_receiving.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get available cells and optimize the query with only one database hit
        available_cells = StorageCell.get_available().order_by('number')
        context['available_cells'] = available_cells
        context['available_cell_count'] = available_cells.count()
        
        # Get recent received orders - limit to 15 for better performance
        context['recent_orders'] = Order.objects.filter(
            reception_status='received'
        ).order_by('-received_at')[:15]
        
        # Get pending orders that haven't been received yet
        # Use select_related to reduce database queries
        context['pending_orders'] = Order.objects.filter(
            reception_status='pending',
            status='pending'
        ).select_related('customer').order_by('created_at')[:30]
        
        # Add search form context if there was a search
        order_id = self.request.GET.get('search_order_id')
        if order_id:
            try:
                order = Order.objects.get(order_id=order_id)
                context['searched_order'] = order
            except Order.DoesNotExist:
                context['search_error'] = f'Заказ с ID {order_id} не найден'
        
        return context
    
    def post(self, request, *args, **kwargs):
        order_id = request.POST.get('order_id')
        
        if not order_id:
            messages.error(request, 'Необходимо указать ID заказа')
            return redirect('order_receiving')
            
        try:
            # Get the order
            order = Order.objects.get(order_id=order_id)
            
            # Check if the order is already received
            if order.reception_status == 'received':
                messages.warning(request, f'Заказ {order.order_id} уже был принят ранее (ячейка: {order.storage_cell})')
                return redirect('order_receiving')
                
            # Check if this customer already has a cell assigned
            customer_cell = StorageCell.objects.filter(
                current_customer=order.customer,
                is_occupied=True
            ).first()
            
            if not customer_cell:
                # Find first available cell
                available_cell = StorageCell.get_available().first()
                
                if available_cell:
                    customer_cell = available_cell
                else:
                    messages.error(request, 'Нет свободных ячеек для размещения заказа')
                    return redirect('order_receiving')
            
            # Complete the receipt process using our new helper method
            order.complete_receipt(customer_cell)
            
            messages.success(request, f'Заказ {order.order_id} успешно принят в ячейку {customer_cell.number}')
            
        except Order.DoesNotExist:
            messages.error(request, f'Заказ с ID {order_id} не найден')
        except Exception as e:
            messages.error(request, f'Ошибка при приеме заказа: {str(e)}')
        
        return redirect('order_receiving')


class PickupCancelView(UpdateView):
    model = PickupSession
    template_name = 'core/pickup_cancel.html'
    fields = []
    
    def get_object(self, queryset=None):
        # Get customer ID from URL
        customer_id = self.kwargs.get('pk')
        
        # First try to find an active session
        try:
            session = PickupSession.objects.get(customer_id=customer_id, is_active=True)
            return session
        except PickupSession.DoesNotExist:
            # If no active session, get the latest session by started_at timestamp
            try:
                sessions = PickupSession.objects.filter(customer_id=customer_id).order_by('-started_at')
                if sessions.exists():
                    return sessions[0]  # Get the newest session
                raise PickupSession.DoesNotExist("No sessions found")
            except PickupSession.DoesNotExist:
                raise Http404("No pickup session found for this customer.")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.get_object()
        
        # Get all orders associated with this session
        context['orders'] = Order.objects.filter(
            customer=session.customer,
            status='pending'
        )
        
        # Count orders that have been inspected
        context['inspected_count'] = context['orders'].filter(is_under_inspection=True).count()
        
        return context
    
    def post(self, request, *args, **kwargs):
        session = self.get_object()
        reason = request.POST.get('cancel_reason', '')
        
        # Check if any orders are marked for return
        orders_marked_for_return = Order.objects.filter(
            customer=session.customer,
            status='pending',
            marked_for_return=True
        ).exists()
        
        if orders_marked_for_return:
            messages.error(request, "Нельзя отменить выдачу, если есть товары, отмеченные на возврат. Подтвердите выдачу, чтобы завершить процесс возврата.")
            return redirect('pickup_process', pk=session.customer.pk)
        
        # Reset inspection status for all orders
        Order.objects.filter(
            customer=session.customer,
            is_under_inspection=True,
            status='pending'
        ).update(is_under_inspection=False)
        
        # Use the cancel method from the model instead of manually updating fields
        # This properly handles the cancellation logic
        session.cancel(reason)
        
        messages.success(request, f'Выдача для клиента {session.customer.name} отменена. Причина: {reason}')
        return redirect('home')


class SystemView(TemplateView):
    template_name = 'core/system.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer_count'] = Customer.objects.count()
        context['order_count'] = Order.objects.count()
        context['cell_count'] = StorageCell.objects.count()
        return context
    
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        
        if action == 'generate_customers':
            count = int(request.POST.get('count', 10))
            self._generate_customers(count)
            messages.success(request, f'Создано {count} клиентов')
            
        elif action == 'generate_orders':
            count = int(request.POST.get('count', 20))
            self._generate_orders(count)
            messages.success(request, f'Создано {count} заказов со статусом "ожидают приемки"')
            
        elif action == 'generate_cells':
            count = int(request.POST.get('count', 10))
            cells_created = self._generate_cells(count)
            
            if cells_created == 0:
                messages.warning(request, 'Достигнут лимит в 50 ячеек хранения. Новые ячейки не созданы.')
            elif cells_created < count:
                messages.info(request, f'Создано только {cells_created} ячеек хранения (достигнут лимит в 50 ячеек).')
            else:
                messages.success(request, f'Создано {cells_created} ячеек хранения')
            
        elif action == 'clear_data':
            Order.objects.all().delete()
            Customer.objects.all().delete()
            StorageCell.objects.all().delete()
            messages.success(request, 'Все данные очищены')
            
        elif action == 'seed_reasons':
            self._seed_return_reasons()
            messages.success(request, 'Причины возврата добавлены (необходимы для категоризации возвратов при оформлении отказа)')
        
        return redirect('system')
    
    def _generate_customers(self, count):
        faker = Faker('ru_RU')
        for _ in range(count):
            Customer.objects.create(
                name=faker.name(),
                phone=faker.phone_number(),
                email=faker.email(),
            )
    
    def _generate_orders(self, count):
        if Customer.objects.count() == 0:
            self._generate_customers(5)
            
        faker = Faker('ru_RU')
        customers = list(Customer.objects.all())
        
        # Generate some predefined product data
        products = [
            {'name': 'Смартфон Samsung Galaxy S23', 'sizes': ['128GB', '256GB'], 'colors': ['Черный', 'Белый', 'Синий']},
            {'name': 'Ноутбук HP Pavilion', 'sizes': ['14"', '15.6"'], 'colors': ['Серебристый', 'Черный']},
            {'name': 'Кроссовки Nike Air Max', 'sizes': ['39', '40', '41', '42', '43'], 'colors': ['Черные', 'Белые', 'Красные']},
            {'name': 'Платье летнее', 'sizes': ['XS', 'S', 'M', 'L', 'XL'], 'colors': ['Синее', 'Черное', 'Красное', 'Зеленое']},
            {'name': 'Наушники JBL Tune', 'sizes': ['One size'], 'colors': ['Черные', 'Белые', 'Красные']},
            {'name': 'Книга "Мастер и Маргарита"', 'sizes': ['Твердый переплет'], 'colors': ['Стандарт']},
            {'name': 'Часы Casio', 'sizes': ['40 мм', '44 мм'], 'colors': ['Серебристый', 'Золотой', 'Черный']},
            {'name': 'Утюг Philips', 'sizes': ['Стандарт'], 'colors': ['Голубой', 'Белый']},
            {'name': 'Фен Rowenta', 'sizes': ['1800W', '2100W'], 'colors': ['Черный', 'Розовый']},
            {'name': 'Игрушка мягкая "Медведь"', 'sizes': ['Маленький', 'Средний', 'Большой'], 'colors': ['Коричневый', 'Белый']},
        ]
        
        for _ in range(count):
            customer = random.choice(customers)
            product = random.choice(products)
            
            # Create order with pending reception status and no cell assignment
            Order.objects.create(
                name=product['name'],
                customer=customer,
                description=faker.text(max_nb_chars=100),
                size=random.choice(product['sizes']),
                color=random.choice(product['colors']),
                price=round(random.uniform(500, 15000), 2),
                payment_status=random.choice(['prepaid', 'postpaid']),
                status='pending',
                reception_status='pending',  # All orders are now pending reception
                barcode=faker.ean(length=13),
                storage_cell=None,  # No cell assignment on creation
                received_at=None    # Not received yet
            )
    
    def _generate_cells(self, count):
        # Prevent creating more than 50 cells total
        existing_count = StorageCell.objects.count()
        if (existing_count >= 50):
            return 0  # Return 0 cells created
        
        # Limit the count to not exceed 50 total cells
        if (existing_count + count > 50):
            count = 50 - existing_count
            
        # Get existing cell numbers to avoid duplicates
        existing_numbers = set(StorageCell.objects.values_list('number', flat=True))
        
        # Create cells with different section prefixes
        sections = ['A', 'B', 'C', 'D', 'E']
        cells_created = 0
        
        for section in sections:
            for i in range(1, 50):  # Try numbers 1-49 in each section
                if (cells_created >= count):
                    break
                    
                number = f"{section}{i:03d}"
                if (number not in existing_numbers):
                    StorageCell.objects.create(
                        number=number,
                        is_occupied=False
                    )
                    existing_numbers.add(number)
                    cells_created += 1
        
        return cells_created
    
    def _seed_return_reasons(self):
        """
        Эта функция создает причины для возврата товаров.
        
        Причины возврата необходимы для:
        1. Категоризации возвратов (нераспакованные vs распакованные товары)
        2. Аналитики возвратов для улучшения сервиса
        3. Корректного финансового учета возвратов
        4. Информирования поставщиков о причинах возврата
        """
        # Remove existing reasons
        ReturnReason.objects.all().delete()
        
        # Create unopened reasons
        ReturnReason.objects.create(name='Поврежденная упаковка', category='unopened')
        ReturnReason.objects.create(name='Отказ до получения', category='unopened')
        
        # Create opened reasons
        ReturnReason.objects.create(name='Поломка товара', category='opened')
        ReturnReason.objects.create(name='Не подошел товар', category='opened')
        ReturnReason.objects.create(name='Не хватает части товара', category='opened')
        ReturnReason.objects.create(name='Изменил решение', category='opened')
        ReturnReason.objects.create(name='Прислали другой товар', category='opened')


def get_customer(request):
    customer_id = request.GET.get('customer_id')
    
    if (customer_id):
        # Validate that customer_id is numeric before attempting to retrieve the customer
        if (customer_id.isdigit()):
            try:
                customer = Customer.objects.get(id=customer_id)
                return redirect('pickup_process', pk=customer.id)
            except Customer.DoesNotExist:
                messages.error(request, f'Клиент с ID {customer_id} не найден')
                return redirect('customer_search')
        else:
            # Search by name if input is not numeric
            customers = Customer.objects.filter(name__icontains=customer_id)
            if (customers.count() == 1):
                # If exactly one match, go directly to that customer
                customer = customers.first()
                return redirect('pickup_process', pk=customer.id)
            elif (customers.count() > 1):
                # If multiple matches, pass them to the template for selection
                messages.info(request, f'Найдено {customers.count()} клиента с этим именем. Пожалуйста, выберите нужного клиента.')
                return render(request, 'core/customer_search.html', {'customers': customers})
            else:
                messages.error(request, f'Клиент с именем "{customer_id}" не найден')
                return redirect('customer_search')
    
    return redirect('customer_search')


class PickupCloseView(UpdateView):
    model = PickupSession
    template_name = 'core/pickup_close.html'
    fields = []
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.get_object()
        
        # Get all orders associated with this session
        context['orders'] = Order.objects.filter(
            customer=session.customer,
            status='pending'
        )
        
        return context
    
    def post(self, request, *args, **kwargs):
        session = self.get_object()
        cancel_reason = request.POST.get('cancel_reason', '')
        
        # Mark session as inactive
        session.is_active = False
        session.completed_at = timezone.now()
        
        # Store the cancel reason if provided
        if (cancel_reason):
            session.notes = f"Closed with reason: {cancel_reason}"
        
        session.save()
        
        messages.success(request, f'Выдача для клиента {session.customer.name} закрыта.')
        return redirect('home')


def delivery_summary(request, order_id):
    """
    Подробный итог выдачи заказа с финансовой информацией и статистикой по товарам
    """
    # Вместо поиска заказа, получаем клиента для отображения статистики
    customer = get_object_or_404(Customer, id=order_id)
    
    # Получаем заказы этого клиента
    orders = Order.objects.filter(customer=customer)
    
    # Счетчики для товаров
    total_delivered = orders.filter(status='delivered').count()
    total_returned = orders.filter(status='returned').count()
    total_retained = orders.filter(status='pending').count()
    
    # Финансовые расчеты
    delivered_total = sum(order.price for order in orders.filter(status='delivered'))
    returned_total = sum(order.price for order in orders.filter(status='returned'))
    retained_total = sum(order.price for order in orders.filter(status='pending'))
    
    # Суммы по предоплаченным товарам
    prepaid_total = sum(order.price for order in orders.filter(status='delivered', payment_status='prepaid'))
    returned_prepaid_total = sum(order.price for order in orders.filter(status='returned', payment_status='prepaid'))
    retained_prepaid_total = sum(order.price for order in orders.filter(status='pending', payment_status='prepaid'))
    
    # Расчет сумм к оплате/возврату
    to_pay_total = delivered_total - prepaid_total
    refund_total = returned_prepaid_total
    
    # Итоговый расчет
    total_due = to_pay_total - refund_total
    
    context = {
        'customer': customer,
        'orders': orders,
        'total_delivered': total_delivered,
        'total_returned': total_returned,
        'total_retained': total_retained,
        'delivered_total': delivered_total,
        'returned_total': returned_total,
        'retained_total': retained_total,
        'prepaid_total': prepaid_total,
        'returned_prepaid_total': returned_prepaid_total,
        'retained_prepaid_total': retained_prepaid_total,
        'to_pay_total': to_pay_total,
        'refund_total': refund_total,
        'total_due': total_due,
    }
    
    return render(request, 'core/delivery_summary.html', context)


class OrderReturnCancelView(UpdateView):
    model = Order
    template_name = 'core/order_return_cancel.html'
    fields = []
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.get_object()
        context['order'] = order
        return context
    
    def post(self, request, *args, **kwargs):
        order = self.get_object()
        
        # Use the model method to cancel return
        order.cancel_return()
        
        messages.success(request, f'Возврат заказа {order.order_id} отменен')
        return redirect('pickup_process', pk=order.customer.pk)
        
    def get(self, request, *args, **kwargs):
        order = self.get_object()
        
        # Если товар не отмечен для возврата, перенаправляем обратно
        if not order.marked_for_return:
            messages.warning(request, f'Заказ {order.order_id} не отмечен для возврата')
            return redirect('pickup_process', pk=order.customer.pk)
            
        return super().get(request, *args, **kwargs)


class StorageVisualizationView(TemplateView):
    template_name = 'core/storage/visualization.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Поиск по номеру ячейки
        search_query = self.request.GET.get('search', '')
        if (search_query):
            cells = StorageCell.objects.filter(number__icontains=search_query).order_by('number')
        else:
            cells = StorageCell.objects.all().order_by('number')
            
        # Добавляем метрики
        context['cells'] = cells
        context['total_cells_count'] = cells.count()
        context['occupied_cells_count'] = cells.filter(is_occupied=True).count()
        context['free_cells_count'] = cells.filter(is_occupied=False).count()
        context['search_query'] = search_query
        
        # Предзагружаем связанные заказы для снижения количества запросов к БД
        # Убедимся, что мы предварительно загружаем все заказы, а затем отфильтруем их в шаблоне
        # или с помощью аннотации, поскольку filter в prefetch не работает согласно ожиданиям
        cells = cells.prefetch_related('orders')
        
        return context


class CustomerDetailView(DetailView):
    model = Customer
    template_name = 'core/customers/customer_detail.html'
    context_object_name = 'customer'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.get_object()
        
        # Получаем заказы клиента по разным статусам
        orders = Order.objects.filter(customer=customer)
        
        # Доступные к выдаче заказы (получены на склад)
        context['available_orders'] = orders.filter(
            status='pending',
            reception_status='received'
        ).select_related('storage_cell').order_by('-received_at')
        
        # Заказы в пути (еще не получены на склад)
        context['in_transit_orders'] = orders.filter(
            status='pending',
            reception_status='pending'
        ).order_by('-created_at')
        
        # История выданных заказов
        context['delivered_orders'] = orders.filter(
            status='delivered'
        ).order_by('-delivered_at')
        
        # Возвращенные заказы
        context['returned_orders'] = orders.filter(
            status='returned'
        ).order_by('-updated_at')
        
        # Статистика по заказам
        context['total_orders'] = orders.count()
        context['available_count'] = context['available_orders'].count()
        context['in_transit_count'] = context['in_transit_orders'].count()
        context['delivered_count'] = context['delivered_orders'].count()
        context['returned_count'] = context['returned_orders'].count()
        
        # Финансовая статистика
        context['total_pending_amount'] = sum(order.price for order in context['available_orders'])
        context['total_in_transit_amount'] = sum(order.price for order in context['in_transit_orders'])
        
        # Сессии выдачи для этого клиента
        context['pickup_sessions'] = PickupSession.objects.filter(
            customer=customer
        ).order_by('-started_at')[:10]  # Показываем только последние 10
        
        return context
