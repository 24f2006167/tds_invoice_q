from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dateutil import parser
import re

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvoiceInput(BaseModel):
    invoice_text: str


def search_patterns(patterns, text):
    """Return first regex match."""
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def money(value):
    """Convert money string to float."""
    if value is None:
        return None

    value = value.replace(",", "")
    value = re.sub(r"(Rs\.?|INR|₹)", "", value, flags=re.IGNORECASE)
    value = value.strip()

    m = re.search(r"[-+]?\d*\.?\d+", value)

    if not m:
        return None

    try:
        return float(m.group())
    except:
        return None


@app.post("/extract")
def extract(data: InvoiceInput):

    text = data.invoice_text

    # ---------------- Invoice Number ----------------

    invoice_patterns = [
        r"Invoice\s*No\.?\s*[:#-]?\s*([A-Za-z0-9\-\/]+)",
        r"Invoice\s*Number\s*[:#-]?\s*([A-Za-z0-9\-\/]+)",
        r"Invoice\s*#\s*[:#-]?\s*([A-Za-z0-9\-\/]+)",
        r"Invoice\s*ID\s*[:#-]?\s*([A-Za-z0-9\-\/]+)",
        r"Invoice\s*[:#-]?\s*([A-Za-z0-9\-\/]+)",
        r"Bill\s*No\.?\s*[:#-]?\s*([A-Za-z0-9\-\/]+)",
        r"Bill\s*Number\s*[:#-]?\s*([A-Za-z0-9\-\/]+)",
    ]

    invoice_no = search_patterns(invoice_patterns, text)

    # ---------------- Vendor ----------------

    vendor_patterns = [
        r"Vendor\s*[:\-]?\s*(.+)",
        r"Supplier\s*[:\-]?\s*(.+)",
        r"Seller\s*[:\-]?\s*(.+)",
        r"Sold\s*By\s*[:\-]?\s*(.+)",
        r"Company\s*[:\-]?\s*(.+)"
    ]

    vendor = search_patterns(vendor_patterns, text)

    if vendor:
        vendor = vendor.split("\n")[0].strip()

    # ---------------- Date ----------------

    date_patterns = [
        r"Invoice\s*Date\s*[:\-]?\s*(.+)",
        r"Date\s*[:\-]?\s*(.+)",
        r"Dated\s*[:\-]?\s*(.+)"
    ]

    date_text = search_patterns(date_patterns, text)

    iso_date = None

    if date_text:
        date_text = date_text.split("\n")[0]

        try:
            iso_date = parser.parse(date_text, dayfirst=True).date().isoformat()
        except:
            try:
                iso_date = parser.parse(date_text).date().isoformat()
            except:
                iso_date = None

    # ---------------- Amount ----------------

    amount_patterns = [
        r"Subtotal\s*[:\-]?\s*(.+)",
        r"Sub\s*Total\s*[:\-]?\s*(.+)",
        r"Taxable\s*Amount\s*[:\-]?\s*(.+)",
        r"Amount\s*Before\s*Tax\s*[:\-]?\s*(.+)"
    ]

    subtotal = search_patterns(amount_patterns, text)
    amount = money(subtotal)

    # ---------------- Tax ----------------

    tax = None

    cgst = money(search_patterns([r"CGST.*?([\d,]+\.\d+)"], text))
    sgst = money(search_patterns([r"SGST.*?([\d,]+\.\d+)"], text))

    if cgst is not None and sgst is not None:
        tax = round(cgst + sgst, 2)
    else:
        tax_patterns = [
            r"GST.*?([\d,]+\.\d+)",
            r"IGST.*?([\d,]+\.\d+)",
            r"Tax.*?([\d,]+\.\d+)"
        ]

        tax = money(search_patterns(tax_patterns, text))

    # ---------------- Response ----------------

    return {
        "invoice_no": invoice_no,
        "date": iso_date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": "INR"
    }