from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
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
    items = db.relationship('InvoiceItem', backref='invoice', cascade='all, delete-orphan')


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

# ---------------- DB INIT ----------------
with app.app_context():
    db.create_all()

# ---------------- ROUTES ----------------
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/invoices')
def invoices():
    return render_template(
        'invoices.html',
        invoices=Invoice.query.all(),
        customers=Customer.query.all(),
        products=Product.query.all()
    )


@app.route('/add_invoice', methods=['POST'])
def add_invoice():
    customer_id = request.form.get('customer_id')

    if customer_id:
        customer = Customer.query.get_or_404(customer_id)
        customer_name = customer.customer_name
        customer_gstin = customer.customer_gstin
        customer_address = customer.customer_address
        billing_address = customer.billing_address
    else:
        customer_name = request.form['customer_name']
        customer_gstin = request.form['customer_gstin']
        customer_address = request.form['customer_address']
        billing_address = request.form['billing_address']

    seller_gstin = "33ABCDE1234F1Z5"  # CHANGE LATER
    seller_state = get_state_code(seller_gstin)
    buyer_state = get_state_code(customer_gstin)

    new_invoice = Invoice(
        customer_name=customer_name,
        customer_gstin=customer_gstin,
        amount=0,
        customer_address=customer_address,
        billing_address=billing_address,
        status=request.form['status']
    )

    db.session.add(new_invoice)
    db.session.flush()

    total_amount = 0

    product_ids = request.form.getlist('product_id[]')
    quantities = request.form.getlist('quantity[]')

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

        db.session.add(InvoiceItem(
            invoice_id=new_invoice.id,
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
        ))

    new_invoice.amount = total_amount
    db.session.commit()
    print("GST DEBUG")
    for item in new_invoice.items:
        print(item.product_name, item.cgst, item.sgst, item.igst)


    return redirect(url_for('invoices'))



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
