from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    tax_rate = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, nullable=False)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_gstin = db.Column(db.String(15), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    customer_address = db.Column(db.String(300), nullable=False)
    billing_address = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(20), default="Pending")
    items = db.relationship('InvoiceItem', backref='invoice', cascade='all, delete-orphan')

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_gstin = db.Column(db.String(15), nullable=False)
    customer_address = db.Column(db.String(300), nullable=False)
    billing_address = db.Column(db.String(300), nullable=False)
    receivables = db.Column(db.Float, nullable=False, default=0.0)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(300))
    products = db.relationship('Product', backref='category', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=0)
    tax_rate = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    payment_no = db.Column(db.String(20), unique=True, nullable=False)

    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)

    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    mode = db.Column(db.String(50))
    reference = db.Column(db.String(100))

class SalesOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    so_number = db.Column(db.String(20), unique=True, nullable=False)
    customer_po_number = db.Column(db.String(50), nullable=False)

    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)

    status = db.Column(db.String(20), default="Open")  
    # Open / Partially Invoiced / Completed

    customer = db.relationship('Customer', backref='sales_orders')
    items = db.relationship(
        'SalesOrderItem',
        backref='sales_order',
        cascade='all, delete-orphan'
    )

    
class SalesOrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    sales_order_id = db.Column(
        db.Integer,
        db.ForeignKey('sales_order.id'),
        nullable=False
    )

    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)

    ordered_qty = db.Column(db.Integer, nullable=False)
    invoiced_qty = db.Column(db.Integer, default=0)

    unit_price = db.Column(db.Float, nullable=False)

    product = db.relationship('Product')
