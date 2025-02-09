from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)

# Database Configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'invoices.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Invoice Model
class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_gstin= db.Column(db.String(15),nullable=False)
    amount = db.Column(db.Float, nullable=False)
    customer_address = db.Column(db.String(300), nullable=False)
    billing_address = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(20), default="Pending")

# Customer Model
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_gstin= db.Column(db.String(15),nullable=False)
    customer_address = db.Column(db.String(300), nullable=False)
    billing_address = db.Column(db.String(300), nullable=False)
    receivables = db.Column(db.Float, nullable=False, default=0.0)

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
    return render_template('invoices.html', invoices=all_invoices)

# Add Invoice
@app.route('/add_invoice', methods=['POST'])
def add_invoice():
    customer_name = request.form['customer_name']
    customer_gstin = request.form['customer_gstin']
    amount = float(request.form['amount'])
    customer_address = request.form['customer_address']
    billing_address = request.form['billing_address']
    status = request.form['status']

    new_invoice = Invoice(
        customer_name=customer_name, 
        customer_gstin=customer_gstin,
        amount=amount, 
        customer_address=customer_address, 
        billing_address=billing_address, 
        status=status
    )
    
    db.session.add(new_invoice)
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

if __name__ == '__main__':
    app.run(debug=True)
