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
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def money(value):
    if value is None:
        return None

    value = value.replace(",", "")

    value = re.sub(
        r"(Rs\.?|INR|USD|EUR|GBP|AED|AUD|CAD|JPY|₹|\$|€|£)",
        "",
        value,
        flags=re.IGNORECASE,
    )

    m = re.search(r"\d+(?:\.\d+)?", value)

    if not m:
        return None

    return float(m.group())


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
        r"Ref\.?\s*[:#-]?\s*([A-Za-z0-9\-\/]+)",
        r"Reference\s*[:#-]?\s*([A-Za-z0-9\-\/]+)"
    ]

    invoice_no = search_patterns(invoice_patterns, text)

    # ---------------- Vendor ----------------

    vendor_patterns = [
        r"Vendor\s*[:\-]?\s*(.+)",
        r"Supplier\s*[:\-]?\s*(.+)",
        r"Seller\s*[:\-]?\s*(.+)",
        r"Sold\s*By\s*[:\-]?\s*(.+)",
        r"Company\s*[:\-]?\s*(.+)",
        r"Client\s*[:\-]?\s*(.+)",
        r"From\s*[:\-]?\s*(.+)"
    ]

    vendor = search_patterns(vendor_patterns, text)

    if vendor:
        vendor = vendor.split("\n")[0].strip()

    # ---------------- Date ----------------

    date_patterns = [
        r"Invoice\s*Date\s*[:\-]?\s*(.+)",
        r"Issued\s*[:\-]?\s*(.+)",
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
        r"Taxable\s*Value\s*[:\-]?\s*(.+)",
        r"Amount\s*Before\s*Tax\s*[:\-]?\s*(.+)",
        r"Basic\s*Amount\s*[:\-]?\s*(.+)",
        r"Net\s*Amount\s*[:\-]?\s*(.+)",
        r"Net\s*Payable\s*[:\-]?\s*(.+)",
        r"Amount\s*[:\-]?\s*(.+)"
    ]

    subtotal = search_patterns(amount_patterns, text)
    amount = money(subtotal)

    # ---------------- Tax ----------------

    cgst = money(search_patterns([r"CGST.*?([\d,]+\.\d+)"], text))
    sgst = money(search_patterns([r"SGST.*?([\d,]+\.\d+)"], text))

    if cgst is not None and sgst is not None:
        tax = round(cgst + sgst, 2)
    else:
        tax_patterns = [
            r"GST.*?([\d,]+\.\d+)",
            r"IGST.*?([\d,]+\.\d+)",
            r"VAT.*?([\d,]+\.\d+)",
            r"Sales\s*Tax.*?([\d,]+\.\d+)",
            r"Tax.*?([\d,]+\.\d+)"
        ]

        tax = money(search_patterns(tax_patterns, text))

    # ---------------- Currency ----------------

    currency_patterns = [
        r"Currency\s*[:\-]?\s*([A-Z]{3})",
        r"\b(INR|USD|EUR|GBP|AED|AUD|CAD|JPY)\b",
        r"₹",
        r"\$",
        r"€",
        r"£"
    ]

    currency = search_patterns(currency_patterns, text)

    if currency == "₹":
        currency = "INR"
    elif currency == "$":
        currency = "USD"
    elif currency == "€":
        currency = "EUR"
    elif currency == "£":
        currency = "GBP"

    if currency is None:
        currency = "INR"

    return {
        "invoice_no": invoice_no,
        "date": iso_date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": currency
    }