from flask import Flask,  render_template, request, redirect, url_for, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract, func

import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime

app = Flask(__name__)

# ---------------- CONFIG ----------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'invoices.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------- HELPERS ----------------
def get_state_code(gstin):
    return gstin[:2] if gstin and len(gstin) >= 2 else None


def calculate_gst(price, qty, gst_rate, seller_state, buyer_state):
    taxable = price * qty

    if seller_state == buyer_state:
        cgst = taxable * (gst_rate / 2) / 100
        sgst = taxable * (gst_rate / 2) / 100
        igst = 0
    else:
        cgst = 0
        sgst = 0
        igst = taxable * gst_rate / 100

    total = taxable + cgst + sgst + igst

    return {
        "taxable": round(taxable, 2),
        "cgst": round(cgst, 2),
        "sgst": round(sgst, 2),
        "igst": round(igst, 2),
        "total": round(total, 2)
    }

# ---------------- MODELS ----------------
class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_gstin = db.Column(db.String(15), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    customer_address = db.Column(db.String(300), nullable=False)
    billing_address = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(20), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('InvoiceItem', backref='invoice', cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='invoice', cascade='all, delete-orphan')

    @property
    def total_paid(self):
        return sum(p.amount for p in self.payments)

    @property
    def balance(self):
        return round(self.amount - self.total_paid, 2)


class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)

    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)

    gst_rate = db.Column(db.Float, nullable=False)
    taxable_value = db.Column(db.Float, nullable=False)

    cgst = db.Column(db.Float, default=0.0)
    sgst = db.Column(db.Float, default=0.0)
    igst = db.Column(db.Float, default=0.0)

    total = db.Column(db.Float, nullable=False)


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_gstin = db.Column(db.String(15), nullable=False)
    customer_address = db.Column(db.String(300), nullable=False)
    billing_address = db.Column(db.String(300), nullable=False)
    receivables = db.Column(db.Float, default=0.0)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    description = db.Column(db.String(300))
    products = db.relationship('Product', backref='category')


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.String(300))
    price = db.Column(db.Float)
    quantity = db.Column(db.Integer)
    tax_rate = db.Column(db.Float)
    discount = db.Column(db.Float)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    payment_no = db.Column(db.String(20), unique=True, nullable=False)

    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)

    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    mode = db.Column(db.String(50))       # Cash / UPI / Bank
    reference = db.Column(db.String(100)) # optional

# ---------------- SALES ORDER MODELS ----------------

class SalesOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    so_number = db.Column(db.String(20), unique=True, nullable=False)
    customer_po_number = db.Column(db.String(50), nullable=False)
    total_value = db.Column(db.Float, default=0.0)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    status = db.Column(db.String(30), default="Open")
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


# ---------------- DB INIT ----------------
with app.app_context():
    db.create_all()

#-----------------Helpers-------------------

def generate_payment_no():
    last = Payment.query.order_by(Payment.id.desc()).first()
    next_id = (last.id + 1) if last else 1
    return f"PAY-{next_id:05d}"

def generate_so_number():
    last = SalesOrder.query.order_by(SalesOrder.id.desc()).first()
    next_id = (last.id + 1) if last else 1
    return f"SO-{next_id:05d}"



# ---------------- ROUTES ----------------
@app.route('/')
@app.route('/dashboard')
def dashboard():
    current_year = datetime.now().year

    months = ["Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]

    def empty_series():
        return [0] * 12

    sales = empty_series()
    payments = empty_series()
    receivables = empty_series()
    orders = empty_series()
    expenses = empty_series()  # placeholder

    # ---------------- SALES (INVOICES) ----------------
    sales_q = db.session.query(
        extract('month', Invoice.created_at),
        func.sum(Invoice.amount)
    ).filter(
        extract('year', Invoice.created_at) == current_year
    ).group_by(
        extract('month', Invoice.created_at)
    ).all()

    for month, total in sales_q:
        sales[int(month) - 1] = float(total or 0)

    # ---------------- PAYMENTS ----------------
    payments_q = db.session.query(
        extract('month', Payment.payment_date),
        func.sum(Payment.amount)
    ).filter(
        extract('year', Payment.payment_date) == current_year
    ).group_by(
        extract('month', Payment.payment_date)
    ).all()

    for month, total in payments_q:
        payments[int(month) - 1] = float(total or 0)

    # ---------------- RECEIVABLES ----------------
    receivables_q = db.session.query(
        extract('month', Invoice.created_at),
        func.sum(Invoice.amount)
    ).filter(
        Invoice.status != 'Paid',
        extract('year', Invoice.created_at) == current_year
    ).group_by(
        extract('month', Invoice.created_at)
    ).all()

    for month, total in receivables_q:
        receivables[int(month) - 1] = float(total or 0)

    # ---------------- SALES ORDERS ----------------
    orders_q = db.session.query(
        extract('month', SalesOrder.created_at),
        func.sum(SalesOrder.total_value)
    ).filter(
        extract('year', SalesOrder.created_at) == current_year
    ).group_by(
        extract('month', SalesOrder.created_at)
    ).all()

    for month, total in orders_q:
        orders[int(month) - 1] = float(total or 0)

    return render_template(
        "dashboard.html",
        months=months,
        sales=sales,
        payments=payments,
        receivables=receivables,
        orders=orders,
        expenses=expenses,
        year=current_year
    )


@app.route('/invoices')
def invoices():
    return render_template(
        'invoices.html',
        invoices=Invoice.query.all(),
        customers=Customer.query.all(),
        products=Product.query.all(),
        sales_orders=SalesOrder.query.all()
    )

@app.route('/add_invoice', methods=['POST'])
def add_invoice():
    print("ENTERED add_invoice")
    print("FORM DATA:", request.form.to_dict())

    invoice_date_str = request.form.get("invoice_date")

    if not invoice_date_str:
        abort(400, "Invoice date is required")

    invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d")



    # ---------------- CUSTOMER ----------------
    customer_id = request.form.get('customer_id')

    if customer_id:
        customer = Customer.query.get_or_404(customer_id)
        customer_name = customer.customer_name
        customer_gstin = customer.customer_gstin
        customer_address = customer.customer_address
        billing_address = customer.billing_address
    else:
        customer = None
        customer_name = request.form['customer_name']
        customer_gstin = request.form['customer_gstin']
        customer_address = request.form['customer_address']
        billing_address = request.form['billing_address']

    status = request.form['status']

    # ---------------- GST ----------------
    seller_gstin = "33ABCDE1234F1Z5"
    seller_state = get_state_code(seller_gstin)
    buyer_state = get_state_code(customer_gstin)

    # ---------------- CREATE INVOICE ----------------
    new_invoice = Invoice(
        customer_name=customer_name,
        customer_gstin=customer_gstin,
        customer_address=customer_address,
        billing_address=billing_address,
        amount=0,
        status=status,
        created_at=invoice_date
    )
    print("INVOICE DATE FROM FORM:", invoice_date)

    db.session.add(new_invoice)
    db.session.flush()  # get invoice.id

    total_amount = 0

    product_ids = request.form.getlist('product_id[]')
    quantities = request.form.getlist('quantity[]')

    # ---------------- ADD INVOICE ITEMS (IMPORTANT FIX) ----------------
    for pid, qty in zip(product_ids, quantities):
        product = Product.query.get(pid)
        if not product:
            continue

        gst = calculate_gst(
            price=product.price,
            qty=int(qty),
            gst_rate=product.tax_rate,
            seller_state=seller_state,
            buyer_state=buyer_state
        )

        total_amount += gst["total"]

        item = InvoiceItem(
            product_id=product.id,
            product_name=product.name,
            quantity=int(qty),
            unit_price=product.price,
            gst_rate=product.tax_rate,
            taxable_value=gst["taxable"],
            cgst=gst["cgst"],
            sgst=gst["sgst"],
            igst=gst["igst"],
            total=gst["total"]
        )

        # 🔥 THIS IS THE CRITICAL LINE
        new_invoice.items.append(item)

    new_invoice.amount = total_amount

    # ---------------- UPDATE CUSTOMER RECEIVABLES ----------------
    if customer and status != "Paid":
        customer.receivables += total_amount
    print("INVOICE ITEMS COUNT:", len(new_invoice.items))

    # ---------------- SALES ORDER QTY REDUCTION ----------------
    sales_order_id = request.form.get('sales_order_id')

    if sales_order_id:
        so = SalesOrder.query.get_or_404(sales_order_id)

        for inv_item in new_invoice.items:
            so_item = SalesOrderItem.query.filter_by(
                sales_order_id=so.id,
                product_id=inv_item.product_id
            ).first()

            if not so_item:
                print("SO ERROR: product not in sales order")
                return redirect(url_for('invoices'))

            remaining = so_item.ordered_qty - so_item.invoiced_qty

            if inv_item.quantity > remaining:
                print("SO ERROR: qty exceeds remaining")
                return redirect(url_for('invoices'))

            # 🔥 ACTUAL REDUCTION
            so_item.invoiced_qty += inv_item.quantity

        # update SO status
        if all(i.invoiced_qty >= i.ordered_qty for i in so.items):
            so.status = "Completed"
        else:
            so.status = "Partially Invoiced"

    # ---------------- COMMIT ----------------
    db.session.commit()
    print("INVOICE COMMITTED SUCCESSFULLY")

    return redirect(url_for('invoices'))

@app.route('/edit_invoice/<int:id>', methods=['GET', 'POST'])
def edit_invoice(id):
    invoice = Invoice.query.get_or_404(id)

    if request.method == 'POST':
        invoice.customer_name = request.form['customer_name']
        invoice.customer_gstin = request.form['customer_gstin']
        invoice.customer_address = request.form['customer_address']
        invoice.billing_address = request.form['billing_address']
        invoice.amount = float(request.form['amount'])
        invoice.status = request.form['status']

        db.session.commit()
        return redirect(url_for('invoices'))

    return render_template('edit_invoice.html', invoice=invoice)

@app.route('/sales_orders')
def sales_orders():
    orders = SalesOrder.query.order_by(SalesOrder.order_date.desc()).all()
    customers = Customer.query.all()
    products = Product.query.all()
    return render_template(
        'sales_orders.html',
        orders=orders,
        customers=customers,
        products=products
    )

@app.route('/add_sales_order', methods=['POST'])
def add_sales_order():
    customer_id = request.form['customer_id']
    po_number = request.form['customer_po_number']

    product_ids = request.form.getlist('product_id[]')
    quantities = request.form.getlist('quantity[]')
    prices = request.form.getlist('price[]')

    so = SalesOrder(
        so_number=generate_so_number(),
        customer_po_number=po_number,
        customer_id=customer_id
    )

    db.session.add(so)
    db.session.flush()

    for pid, qty, price in zip(product_ids, quantities, prices):
        product = Product.query.get(pid)
        item = SalesOrderItem(
            sales_order_id=so.id,
            product_id=pid,
            product_name=product.name,
            ordered_qty=int(qty),
            unit_price=float(price)
        )
        db.session.add(item)

    db.session.commit()
    return redirect(url_for('sales_orders'))


@app.route('/payments')
def payments():
    all_payments = Payment.query.order_by(Payment.payment_date.desc()).all()
    return render_template('payments.html', payments=all_payments)


@app.route('/add_payment/<int:invoice_id>', methods=['GET', 'POST'])
def add_payment(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    customer = Customer.query.filter_by(customer_name=invoice.customer_name).first()

    if request.method == 'POST':
        amount = float(request.form['amount'])
        mode = request.form.get('mode')
        reference = request.form.get('reference')

        if amount <= 0:
            return redirect(url_for('invoices'))

        if amount > invoice.balance:
            amount = invoice.balance

        payment = Payment(
            payment_no=generate_payment_no(),
            invoice_id=invoice.id,
            customer_id=customer.id,
            amount=amount,
            mode=mode,
            reference=reference
        )

        db.session.add(payment)

        # update receivables
        customer.receivables -= amount
        if customer.receivables < 0:
            customer.receivables = 0

        # update invoice status
        if invoice.balance - amount == 0:
            invoice.status = "Paid"
        else:
            invoice.status = "Partially Paid"

        db.session.commit()
        return redirect(url_for('invoices'))

    return render_template('add_payment.html', invoice=invoice)

@app.route('/edit_payment/<int:id>', methods=['GET', 'POST'])
def edit_payment(id):
    payment = Payment.query.get_or_404(id)
    invoice = payment.invoice
    customer = Customer.query.get(payment.customer_id)

    old_amount = payment.amount

    if request.method == 'POST':
        new_amount = float(request.form['amount'])
        mode = request.form.get('mode')
        reference = request.form.get('reference')

        # prevent overpayment
        max_allowed = invoice.balance + old_amount
        if new_amount > max_allowed:
            new_amount = max_allowed

        payment.amount = new_amount
        payment.mode = mode
        payment.reference = reference

        # ---- FIX RECEIVABLES ----
        customer.receivables += (old_amount - new_amount)
        if customer.receivables < 0:
            customer.receivables = 0

        # ---- UPDATE INVOICE STATUS ----
        if invoice.balance == 0:
            invoice.status = "Paid"
        else:
            invoice.status = "Partially Paid"

        db.session.commit()
        return redirect(url_for('payments'))

    return render_template('edit_payment.html', payment=payment)


# View All Customers
@app.route('/customers', methods=['GET'])
def customers():
    all_customers = Customer.query.all()
    return render_template('customers.html', customers=all_customers)

# Add Customer
@app.route('/add_customer', methods=['POST'])
def add_customer():
    customer_name = request.form['customer_name']
    customer_gstin = request.form['customer_gstin']
    customer_address = request.form['customer_address']
    billing_address = request.form['billing_address']
    receivables = float(request.form['receivables'])

    new_customer = Customer(
        customer_name=customer_name, 
        customer_gstin = customer_gstin,
        customer_address=customer_address, 
        billing_address=billing_address, 
        receivables=receivables
    )
    
    db.session.add(new_customer)
    db.session.commit()
    return redirect(url_for('customers'))

# Edit Customer
@app.route('/edit_customer/<int:id>', methods=['GET', 'POST'])
def edit_customer(id):
    customer = Customer.query.get_or_404(id)
    
    if request.method == 'POST':
        customer.customer_name = request.form['customer_name']
        customer.customer_gstin = request.form['customer_gstin']
        customer.customer_address = request.form['customer_address']
        customer.billing_address = request.form['billing_address']
        customer.receivables = float(request.form['receivables'])

        db.session.commit()
        return redirect(url_for('customers'))

    return render_template('edit_customer.html', customer=customer)

# Delete Customer
@app.route('/delete_customer/<int:id>', methods=['POST'])
def delete_customer(id):
    customer = Customer.query.get_or_404(id)
    db.session.delete(customer)
    db.session.commit()
    return redirect(url_for('customers'))


# Product Routes
@app.route('/products')
def products():
    all_products = Product.query.all()
    all_categories = Category.query.all()
    return render_template('products.html', products=all_products, categories=all_categories)

@app.route('/add_product', methods=['POST'])
def add_product():
    name = request.form['name']
    description = request.form['description']
    price = float(request.form['price'])
    quantity = int(request.form['quantity'])
    tax_rate = float(request.form.get('tax_rate', 0))
    discount = float(request.form.get('discount', 0))
    category_id = int(request.form['category_id'])

    new_product = Product(
        name=name,
        description=description,
        price=price,
        quantity=quantity,
        tax_rate=tax_rate,
        discount=discount,
        category_id=category_id
    )
    
    db.session.add(new_product)
    db.session.commit()
    return redirect(url_for('products'))

@app.route('/edit_product/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    product = Product.query.get_or_404(id)
    categories = Category.query.all()
    
    if request.method == 'POST':
        product.name = request.form['name']
        product.description = request.form['description']
        product.price = float(request.form['price'])
        product.quantity = int(request.form['quantity'])
        product.tax_rate = float(request.form.get('tax_rate', 0))
        product.discount = float(request.form.get('discount', 0))
        product.category_id = int(request.form['category_id'])

        db.session.commit()
        return redirect(url_for('products'))

    return render_template('edit_product.html', product=product, categories=categories)

@app.route('/delete_product/<int:id>', methods=['POST'])
def delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('products'))

# Category Routes
@app.route('/categories')
def categories():
    all_categories = Category.query.all()
    return render_template('categories.html', categories=all_categories)

@app.route('/add_category', methods=['POST'])
def add_category():
    name = request.form['name']
    description = request.form['description']

    new_category = Category(name=name, description=description)
    db.session.add(new_category)
    db.session.commit()
    return redirect(url_for('categories'))

@app.route('/edit_category/<int:id>', methods=['GET', 'POST'])
def edit_category(id):
    category = Category.query.get_or_404(id)
    
    if request.method == 'POST':
        category.name = request.form['name']
        category.description = request.form['description']
        db.session.commit()
        return redirect(url_for('categories'))

    return render_template('edit_category.html', category=category)

@app.route('/delete_category/<int:id>', methods=['POST'])
def delete_category(id):
    category = Category.query.get_or_404(id)
    db.session.delete(category)
    db.session.commit()
    return redirect(url_for('categories'))
    
if __name__ == '__main__':
    app.run(debug=True)
