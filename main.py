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


def find(pattern, text):
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def money(value):
    if value is None:
        return None

    value = value.replace(",", "")
    value = value.replace("Rs.", "")
    value = value.replace("Rs", "")
    value = value.replace("INR", "")
    value = value.strip()

    try:
        return float(value)
    except:
        return None


@app.post("/extract")
def extract(data: InvoiceInput):

    text = data.invoice_text

    invoice_no = find(r"Invoice\s*No[:\-]?\s*(.+)", text)

    vendor = find(r"Vendor[:\-]?\s*(.+)", text)

    subtotal = find(r"Subtotal[:\-]?\s*(.+)", text)

    tax = find(r"(?:GST.*?|Tax.*?)[:\-]?\s*(Rs\.?\s*[\d,]+\.\d+)", text)

    date_text = find(r"Date[:\-]?\s*(.+)", text)

    iso_date = None

    if date_text:
        try:
            iso_date = parser.parse(date_text).date().isoformat()
        except:
            pass

    return {
        "invoice_no": invoice_no,
        "date": iso_date,
        "vendor": vendor,
        "amount": money(subtotal),
        "tax": money(tax),
        "currency": "INR"
    }