INVOICEO

🧾 Simple Invoice, Sales Order & Payment Manager (Flask)

This is a lightweight business management app built with Flask and SQLite for handling sales orders, invoices, customers, and payments.
It supports GST calculations (CGST / SGST / IGST) and allows backdated invoices and payments, just like real accounting software.
Sales orders can be partially invoiced, with remaining quantities tracked automatically.
Payments update invoice balances and customer receivables in real time.
A basic dashboard shows monthly sales, orders, payments, and receivables.
Invoices can be exported as PDFs using ReportLab.
The project is designed to be simple, readable, and easy to extend.

🚀 How to Run

git clone <repo-url>

cd invoiceo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py


Open your browser and visit:
👉 http://127.0.0.1:5000
