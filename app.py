from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime


app = Flask(__name__)

# Database Configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'invoices.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Add these models to your existing ones

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

# Update your Invoice model to include items relationship
class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_gstin = db.Column(db.String(15), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    customer_address = db.Column(db.String(300), nullable=False)
    billing_address = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(20), default="Pending")
    items = db.relationship('InvoiceItem', backref='invoice', cascade='all, delete-orphan')

# Customer Model
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_gstin= db.Column(db.String(15),nullable=False)
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
    tax_rate = db.Column(db.Float, default=0.0)  # in percentage
    discount = db.Column(db.Float, default=0.0)   # in percentage
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create database tables
with app.app_context():
    db.create_all()

# Home Page
@app.route('/')
def home():
    return render_template('home.html')

# View All Invoices
@app.route('/invoices', methods=['GET'])
def invoices():
    status_filter = request.args.get('status')
    if status_filter:
        all_invoices = Invoice.query.filter_by(status=status_filter).all()
    else:
        all_invoices = Invoice.query.all()
    all_customers = Customer.query.all()  # Get all customers
    all_products = Product.query.all()
    return render_template('invoices.html', invoices=all_invoices, customers=all_customers ,products=all_products)

# Add Invoice
# Add these new routes for invoice management with products

@app.route('/add_invoice', methods=['POST'])
def add_invoice():
    customer_id = request.form.get('customer_id')
    if customer_id:
        customer = Customer.query.get(customer_id)
        customer_name = customer.customer_name
        customer_gstin = customer.customer_gstin
        customer_address = customer.customer_address
        billing_address = customer.billing_address 
    else:
        customer_name = request.form['customer_name']
        customer_gstin = request.form['customer_gstin']
        customer_address = request.form['customer_address']
        billing_address = request.form['billing_address']

    status = request.form['status']
    product_ids = request.form.getlist('product_id[]')
    quantities = request.form.getlist('quantity[]')
    
    # Calculate invoice total
    total_amount = 0
    items = []
    
    for product_id, quantity in zip(product_ids, quantities):
        product = Product.query.get(product_id)
        if product:
            item_total = float(product.product_price) * int(quantity)
            total_amount += item_total
            items.append({
                'product': product,
                'quantity': quantity,
                'unit_price': product.product_price,
                'total': item_total
            })

    # Create invoice
    new_invoice = Invoice(
        customer_name=customer_name,
        customer_gstin=customer_gstin,
        amount=total_amount,
        customer_address=customer_address,
        billing_address=billing_address,
        status=status
    )
    
    db.session.add(new_invoice)
    db.session.flush()  # Get the invoice ID
    
    # Add invoice items
    for item in items:
        new_item = InvoiceItem(
            invoice_id=new_invoice.id,
            product_id=item['product'].id,
            product_name=item['product'].product_name,
            quantity=item['quantity'],
            unit_price=item['unit_price'],
            tax_rate=item['product'].product_tax,
            discount=item['product'].product_discount,
            total=item['total']
        )
        db.session.add(new_item)
    
    db.session.commit()
    return redirect(url_for('invoices'))
# Edit Invoice
@app.route('/edit_invoice/<int:id>', methods=['GET', 'POST'])
def edit_invoice(id):
    invoice = Invoice.query.get_or_404(id)
    
    if request.method == 'POST':
        invoice.customer_name = request.form['customer_name']
        invoice.customer_gstin = request.form['customer_gstin']
        invoice.amount = float(request.form['amount'])
        invoice.customer_address = request.form['customer_address']
        invoice.billing_address = request.form['billing_address']
        invoice.status = request.form['status']

        db.session.commit()
        return redirect(url_for('invoices'))

    return render_template('edit_invoice.html', invoice=invoice)


# Delete Invoice
@app.route('/delete_invoice/<int:id>', methods=['POST'])
def delete_invoice(id):
    invoice = Invoice.query.get_or_404(id)
    db.session.delete(invoice)
    db.session.commit()
    return redirect(url_for('invoices'))

# Generate PDF Invoice
@app.route('/generate_pdf/<int:id>')
def generate_pdf(id):
    invoice = Invoice.query.get_or_404(id)
    pdf_filename = f"invoice_{invoice.id}.pdf"
    pdf_path = f"./{pdf_filename}"

    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.drawString(100, 750, f"Invoice ID: {invoice.id}")
    c.drawString(100, 730, f"Customer Name: {invoice.customer_name}")
    c.drawString(100, 710, f"Amount: ${invoice.amount}")
    c.drawString(100, 690, f"Customer Address: {invoice.customer_address}")
    c.drawString(100, 670, f"Billing Address: {invoice.billing_address}")
    c.drawString(100, 650, f"Status: {invoice.status}")
    c.save()
    
    return send_file(pdf_path, as_attachment=True)

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
