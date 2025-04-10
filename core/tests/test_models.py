from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta

from core.models import (
    Customer, StorageCell, Order, ReturnReason,
    OrderReturn, PickupSession, generate_order_id
)


class CustomerModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="Иван Иванов",
            phone="+79001234567",
            email="ivan@example.com"
        )
        self.cell = StorageCell.objects.create(
            number="A001",
            is_occupied=False
        )

    def test_customer_creation(self):
        self.assertEqual(str(self.customer), "Иван Иванов (+79001234567)")
        self.assertEqual(self.customer.name, "Иван Иванов")
        self.assertEqual(self.customer.phone, "+79001234567")
        self.assertEqual(self.customer.email, "ivan@example.com")

    def test_get_pending_orders(self):
        # Create order that is pending and received
        order1 = Order.objects.create(
            customer=self.customer,
            name="Test Product",
            price=1000,
            status='pending',
            reception_status='received'
        )
        
        # Create order that is pending but not received
        order2 = Order.objects.create(
            customer=self.customer,
            name="Test Product 2",
            price=2000,
            status='pending',
            reception_status='pending'
        )
        
        # Create order that is delivered (not pending)
        order3 = Order.objects.create(
            customer=self.customer,
            name="Test Product 3",
            price=3000,
            status='delivered',
            reception_status='received'
        )
        
        pending_orders = self.customer.get_pending_orders()
        self.assertEqual(pending_orders.count(), 1)
        self.assertEqual(pending_orders.first().id, order1.id)

    def test_get_total_orders_count(self):
        # Initially no orders
        self.assertEqual(self.customer.get_total_orders_count(), 0)
        
        # Create some orders
        Order.objects.create(customer=self.customer, name="Order 1", price=100)
        Order.objects.create(customer=self.customer, name="Order 2", price=200, status='delivered')
        
        # Refresh customer instance to ensure relations are updated if needed (though usually not required for count)
        self.customer.refresh_from_db() 
        self.assertEqual(self.customer.get_total_orders_count(), 2)

    def test_has_active_pickup_session(self):
        # Test case where related manager might not be present (e.g., unsaved instance)
        unsaved_customer = Customer(name="Temp", phone="123")
        unsaved_customer.save() # Save the customer instance
        # Accessing related manager on unsaved instance might raise an error depending on Django version/setup
        # The updated method handles this by returning False.
        self.assertFalse(unsaved_customer.has_active_pickup_session())

        # Initially no active sessions for saved customer
        self.assertFalse(self.customer.has_active_pickup_session())
        
        # Create active session
        session = PickupSession.objects.create(
            customer=self.customer,
            is_active=True
        )
        
        # Now should have active session
        self.assertTrue(self.customer.has_active_pickup_session())
        
        # Mark session as inactive
        session.is_active = False
        session.save()
        
        # Should no longer have active session
        self.assertFalse(self.customer.has_active_pickup_session())


class StorageCellModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="Иван Иванов",
            phone="+79001234567"
        )
        self.cell = StorageCell.objects.create(
            number="A001",
            is_occupied=False
        )

    def test_cell_creation(self):
        self.assertEqual(str(self.cell), "Ячейка A001 (Свободна)")
        self.assertEqual(self.cell.number, "A001")
        self.assertFalse(self.cell.is_occupied)
        self.assertIsNone(self.cell.current_customer)

    def test_assign_to_customer(self):
        self.cell.assign_to_customer(self.customer)
        self.assertTrue(self.cell.is_occupied)
        self.assertEqual(self.cell.current_customer, self.customer)

    def test_release(self):
        # First assign to a customer
        self.cell.assign_to_customer(self.customer)
        self.assertTrue(self.cell.is_occupied)
        
        # Now release
        self.cell.release()
        self.assertFalse(self.cell.is_occupied)
        self.assertIsNone(self.cell.current_customer)

    def test_get_available(self):
        # Create one more cell that is occupied
        StorageCell.objects.create(
            number="A002",
            is_occupied=True,
            current_customer=self.customer
        )
        
        # Create another available cell
        StorageCell.objects.create(
            number="A003",
            is_occupied=False
        )
        
        # Should return 2 available cells (A001 and A003)
        available_cells = StorageCell.get_available()
        self.assertEqual(available_cells.count(), 2)


class OrderModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="Иван Иванов",
            phone="+79001234567"
        )
        self.cell = StorageCell.objects.create(
            number="A001",
            is_occupied=False
        )
        self.order = Order.objects.create(
            name="Test Product",
            customer=self.customer,
            description="Product description",
            size="M",
            color="Red",
            price=1000,
            payment_status="postpaid",
            barcode="1234567890123"
        )
        self.reason = ReturnReason.objects.create(
            name="Defective product",
            category="opened"
        )

    def test_order_id_generation(self):
        # Test that order_id is automatically generated
        self.assertTrue(self.order.order_id.startswith("BP-"))
        self.assertEqual(len(self.order.order_id), 11)  # "BP-" + 8 chars
        
        # Test the generate_order_id function directly
        order_id = generate_order_id()
        self.assertTrue(order_id.startswith("BP-"))
        self.assertEqual(len(order_id), 11)

    def test_order_creation(self):
        self.assertEqual(str(self.order), f"{self.order.order_id} - Test Product (Иван Иванов)")
        self.assertEqual(self.order.name, "Test Product")
        self.assertEqual(self.order.customer, self.customer)
        self.assertEqual(self.order.description, "Product description")
        self.assertEqual(self.order.size, "M")
        self.assertEqual(self.order.color, "Red")
        self.assertEqual(self.order.price, 1000)
        self.assertEqual(self.order.payment_status, "postpaid")
        self.assertEqual(self.order.barcode, "1234567890123")
        self.assertEqual(self.order.status, "pending")
        self.assertEqual(self.order.reception_status, "pending")

    def test_is_available_for_pickup(self):
        # Initially order is not available (reception_status = 'pending')
        self.assertFalse(self.order.is_available_for_pickup())
        
        # Mark as received
        self.order.reception_status = "received"
        self.order.save()
        self.assertTrue(self.order.is_available_for_pickup())
        
        # Mark as picked up
        self.order.is_picked_up = True
        self.order.save()
        self.assertFalse(self.order.is_available_for_pickup())
        
        # Reset is_picked_up but change status to delivered
        self.order.is_picked_up = False
        self.order.status = "delivered"
        self.order.save()
        self.assertFalse(self.order.is_available_for_pickup())

    def test_complete_receipt(self):
        self.assertEqual(self.order.reception_status, "pending")
        self.assertIsNone(self.order.storage_cell)
        
        # Complete receipt with cell assignment
        self.order.complete_receipt(self.cell)
        
        # Verify order updated
        self.assertEqual(self.order.reception_status, "received")
        self.assertIsNotNone(self.order.received_at)
        self.assertEqual(self.order.storage_cell, self.cell)
        
        # Verify cell updated
        self.cell.refresh_from_db()
        self.assertTrue(self.cell.is_occupied)
        self.assertEqual(self.cell.current_customer, self.customer)
        
        # Test complete_receipt without cell
        order2 = Order.objects.create(
            name="Test Product 2",
            customer=self.customer,
            price=2000
        )
        order2.complete_receipt()  # No cell provided
        self.assertEqual(order2.reception_status, "received")
        self.assertIsNotNone(order2.received_at)
        self.assertIsNone(order2.storage_cell)

    def test_mark_delivered(self):
        self.assertEqual(self.order.status, "pending")
        self.assertFalse(self.order.is_picked_up)
        self.assertIsNone(self.order.delivered_at)
        
        # Mark as delivered
        self.order.mark_delivered()
        
        # Verify order updated
        self.assertEqual(self.order.status, "delivered")
        self.assertTrue(self.order.is_picked_up)
        self.assertIsNotNone(self.order.delivered_at)

    def test_mark_for_return(self):
        self.assertFalse(self.order.marked_for_return)
        self.assertIsNone(self.order.return_reason_id)
        self.assertIsNone(self.order.return_notes)
        
        # Mark for return with notes
        self.order.mark_for_return(self.reason.id, "Customer changed mind")
        
        # Verify order updated
        self.assertTrue(self.order.marked_for_return)
        self.assertEqual(self.order.return_reason_id, self.reason.id)
        self.assertEqual(self.order.return_notes, "Customer changed mind")
        
        # Mark for return without notes
        self.order.return_notes = None
        self.order.save()
        self.order.mark_for_return(self.reason.id)
        self.assertTrue(self.order.marked_for_return)
        self.assertEqual(self.order.return_reason_id, self.reason.id)
        self.assertIsNone(self.order.return_notes)

    def test_cancel_return(self):
        # First mark for return
        self.order.mark_for_return(self.reason.id, "Customer changed mind")
        self.assertTrue(self.order.marked_for_return)
        
        # Now cancel return
        self.order.cancel_return()
        
        # Verify order updated
        self.assertFalse(self.order.marked_for_return)
        self.assertIsNone(self.order.return_reason_id)
        self.assertIsNone(self.order.return_notes)

    def test_process_return(self):
        # Cannot process return if not marked for return
        result = self.order.process_return()
        self.assertFalse(result)
        self.assertEqual(self.order.status, "pending")
        
        # Mark for return but don't provide reason ID
        self.order.marked_for_return = True
        self.order.save()
        result = self.order.process_return()
        self.assertFalse(result)
        self.assertEqual(self.order.status, "pending")
        
        # Mark for return with reason ID
        self.order.return_reason_id = self.reason.id
        self.order.save()
        result = self.order.process_return()
        self.assertTrue(result)
        
        # Verify order updated
        self.assertEqual(self.order.status, "returned")
        
        # Verify return record created
        self.assertTrue(hasattr(self.order, 'return_info'))
        self.assertEqual(self.order.return_info.reason, self.reason)

    def test_clean_validation(self):
        # Test validation for delivered orders
        self.order.status = "delivered"
        self.order.delivered_at = None
        with self.assertRaises(ValidationError):
            self.order.clean()
            
        # Fix delivered_at
        self.order.delivered_at = timezone.now()
        self.order.clean()  # Should not raise error
        
        # Test validation for returned orders
        self.order.status = "returned"
        self.order.return_reason_id = None
        with self.assertRaises(ValidationError):
            self.order.clean()
            
        # Fix return_reason_id
        self.order.return_reason_id = self.reason.id
        self.order.clean()  # Should not raise error

    def test_save_method(self):
        # Test that reception_date is set when reception_status is 'received'
        self.order.reception_status = "received"
        self.order.reception_date = None
        self.order.save()
        self.assertIsNotNone(self.order.reception_date)


class ReturnReasonModelTests(TestCase):
    def test_return_reason_creation(self):
        reason = ReturnReason.objects.create(
            name="Defective product",
            category="opened"
        )
        self.assertEqual(str(reason), "Defective product")
        self.assertEqual(reason.name, "Defective product")
        self.assertEqual(reason.category, "opened")


class OrderReturnModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="Иван Иванов",
            phone="+79001234567"
        )
        self.order = Order.objects.create(
            name="Test Product",
            customer=self.customer,
            price=1000
        )
        self.reason = ReturnReason.objects.create(
            name="Defective product",
            category="opened"
        )

    def test_order_return_creation(self):
        order_return = OrderReturn.objects.create(
            order=self.order,
            reason=self.reason,
            notes="Customer received defective product"
        )
        
        self.assertEqual(str(order_return), f"Возврат заказа {self.order.order_id}")
        self.assertEqual(order_return.order, self.order)
        self.assertEqual(order_return.reason, self.reason)
        self.assertEqual(order_return.notes, "Customer received defective product")
        self.assertIsNotNone(order_return.created_at)


class PickupSessionModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="Иван Иванов",
            phone="+79001234567"
        )
        self.cell = StorageCell.objects.create(
            number="A001",
            is_occupied=False
        )
        self.order1 = Order.objects.create(
            name="Test Product 1",
            customer=self.customer,
            price=1000,
            status='pending',
            reception_status='received',
            storage_cell=self.cell
        )
        self.order2 = Order.objects.create(
            name="Test Product 2",
            customer=self.customer,
            price=2000,
            status='pending',
            reception_status='received'
        )
        self.session = PickupSession.objects.create(
            customer=self.customer,
            is_active=True
        )
        self.session.orders.add(self.order1, self.order2)
        
        # Return reason for testing
        self.reason = ReturnReason.objects.create(
            name="Defective product",
            category="opened"
        )

    def test_pickup_session_creation(self):
        self.assertEqual(str(self.session), f"Выдача Иван Иванов (Активна)")
        self.assertEqual(self.session.customer, self.customer)
        self.assertTrue(self.session.is_active)
        self.assertFalse(self.session.is_cancelled)
        self.assertIsNotNone(self.session.started_at)
        self.assertIsNone(self.session.completed_at)

    def test_has_received_orders(self):
        self.assertTrue(self.session.has_received_orders())
        
        # Change reception status of all orders
        Order.objects.all().update(reception_status='pending')
        self.assertFalse(self.session.has_received_orders())

    def test_count_received_orders(self):
        self.assertEqual(self.session.count_received_orders(), 2)
        
        # Change reception status of one order
        self.order1.reception_status = 'pending'
        self.order1.save()
        self.assertEqual(self.session.count_received_orders(), 1)

    def test_cancel(self):
        # Mark one order as picked up
        self.order1.is_picked_up = True
        self.order1.save()
        
        # Now cancel the session
        self.session.cancel("Customer changed mind")
        
        # Verify session updated
        self.assertTrue(self.session.is_cancelled)
        self.assertFalse(self.session.is_active)
        self.assertEqual(self.session.cancel_reason, "Customer changed mind")
        self.assertIsNotNone(self.session.completed_at)
        
        # Verify order reset
        self.order1.refresh_from_db()
        self.assertFalse(self.order1.is_picked_up)

    def test_complete_with_deliveries(self):
        # Setup: mark cell as occupied
        self.cell.is_occupied = True
        self.cell.current_customer = self.customer
        self.cell.save()
        
        # Complete session with order1 selected for delivery
        self.session.complete([str(self.order1.id)])
        
        # Verify session updated
        self.assertFalse(self.session.is_active)
        self.assertIsNotNone(self.session.completed_at)
        
        # Verify orders updated
        self.order1.refresh_from_db()
        self.order2.refresh_from_db()
        
        self.assertEqual(self.order1.status, "delivered")
        self.assertTrue(self.order1.is_picked_up)
        self.assertEqual(self.order2.status, "pending")
        self.assertFalse(self.order2.is_picked_up)
        
        # Storage cell should still be occupied since we still have pending orders
        self.cell.refresh_from_db()
        self.assertTrue(self.cell.is_occupied)

    def test_complete_with_returns(self):
        # Mark order2 for return
        self.order2.mark_for_return(self.reason.id, "Defective")
        
        # Complete session with order1 selected for delivery
        self.session.complete([str(self.order1.id)])
        
        # Verify orders updated
        self.order1.refresh_from_db()
        self.order2.refresh_from_db()
        
        self.assertEqual(self.order1.status, "delivered")
        self.assertEqual(self.order2.status, "returned")
        
        # Verify return record created for order2
        self.assertTrue(hasattr(self.order2, 'return_info'))

    def test_complete_with_cell_release(self):
        # Complete session with both orders selected for delivery
        self.session.complete([str(self.order1.id), str(self.order2.id)])
        
        # Storage cell should be released since no more pending orders
        self.cell.refresh_from_db()
        self.assertFalse(self.cell.is_occupied)
        self.assertIsNone(self.cell.current_customer)
