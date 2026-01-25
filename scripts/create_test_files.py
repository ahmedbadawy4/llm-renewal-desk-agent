#!/usr/bin/env python3
"""Create proper test files for contract, invoices, and usage."""
from __future__ import annotations

import csv
from pathlib import Path

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples"


def create_contract_pdf() -> None:
    """Create a proper contract PDF with all required fields."""
    if not HAS_REPORTLAB:
        print("reportlab not installed. Install with: pip install reportlab")
        print("Creating a text-based contract instead...")
        create_contract_text()
        return

    output_path = EXAMPLES_DIR / "sample_contract.pdf"
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    title = Paragraph("<b>SOFTWARE LICENSE AGREEMENT</b>", styles["Title"])
    story.append(title)
    story.append(Spacer(1, 12))

    content = [
        "This Software License Agreement (the 'Agreement') is entered into effective January 1, 2024 through December 31, 2024.",
        "",
        "<b>1. TERM AND RENEWAL</b>",
        "This Agreement shall be effective from January 1, 2024 through December 31, 2024. "
        "This Agreement will auto-renew for successive one-year terms unless either party provides "
        "written notice of non-renewal at least 90 days prior to the expiration date.",
        "",
        "<b>2. LICENSE AND SEATS</b>",
        "Customer is licensed for 500 seats of the Software. The license is non-transferable and "
        "restricted to Customer's internal business use.",
        "",
        "<b>3. PRICING AND PAYMENT</b>",
        "The annual license fee is $120,000. Payment shall be made quarterly in installments of $30,000. "
        "Upon renewal, pricing may increase by up to 5% annually.",
        "",
        "<b>4. LIABILITY</b>",
        "Vendor's total liability under this Agreement shall not exceed 2x the annual license fee paid by Customer.",
        "",
        "<b>5. DATA PROCESSING</b>",
        "The parties have executed a separate Data Processing Agreement (DPA) that governs data protection obligations.",
        "",
        "<b>6. NOTICE</b>",
        "All notices must be provided in writing at least 90 days before the renewal date.",
    ]

    for para in content:
        if para.startswith("<b>"):
            story.append(Paragraph(para, styles["Heading2"]))
        elif para:
            story.append(Paragraph(para, styles["Normal"]))
        else:
            story.append(Spacer(1, 12))

    pricing_table = Table([
        ["Period", "Amount", "Seats"],
        ["Q1 2024", "$30,000", "500"],
        ["Q2 2024", "$30,000", "500"],
        ["Q3 2024", "$30,000", "500"],
        ["Q4 2024", "$30,000", "500"],
    ])
    pricing_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 12),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(Spacer(1, 12))
    story.append(pricing_table)

    doc.build(story)
    print(f"Created contract PDF: {output_path}")


def create_contract_text() -> None:
    """Create a text file that can be converted to PDF manually."""
    output_path = EXAMPLES_DIR / "sample_contract.txt"
    content = """SOFTWARE LICENSE AGREEMENT

This Software License Agreement (the "Agreement") is entered into effective January 1, 2024 through December 31, 2024.

1. TERM AND RENEWAL
This Agreement shall be effective from January 1, 2024 through December 31, 2024. This Agreement will auto-renew for successive one-year terms unless either party provides written notice of non-renewal at least 90 days prior to the expiration date.

2. LICENSE AND SEATS
Customer is licensed for 500 seats of the Software. The license is non-transferable and restricted to Customer's internal business use.

3. PRICING AND PAYMENT
The annual license fee is $120,000. Payment shall be made quarterly in installments of $30,000. Upon renewal, pricing may increase by up to 5% annually.

4. LIABILITY
Vendor's total liability under this Agreement shall not exceed 2x the annual license fee paid by Customer.

5. DATA PROCESSING
The parties have executed a separate Data Processing Agreement (DPA) that governs data protection obligations.

6. NOTICE
All notices must be provided in writing at least 90 days before the renewal date.

PRICING SCHEDULE
Period          Amount      Seats
Q1 2024         $30,000     500
Q2 2024         $30,000     500
Q3 2024         $30,000     500
Q4 2024         $30,000     500
"""
    output_path.write_text(content)
    print(f"Created contract text file: {output_path}")
    print("Note: Convert to PDF manually or install reportlab: pip install reportlab")


def create_invoices_csv() -> None:
    """Create a proper invoices CSV file."""
    output_path = EXAMPLES_DIR / "invoices.csv"
    
    invoices = [
        {
            "invoice_id": "INV-2024-001",
            "vendor_id": "vendor_123",
            "period_start": "2024-01-01",
            "period_end": "2024-03-31",
            "amount_usd": "30000",
            "seats": "500",
        },
        {
            "invoice_id": "INV-2024-002",
            "vendor_id": "vendor_123",
            "period_start": "2024-04-01",
            "period_end": "2024-06-30",
            "amount_usd": "30000",
            "seats": "500",
        },
        {
            "invoice_id": "INV-2024-003",
            "vendor_id": "vendor_123",
            "period_start": "2024-07-01",
            "period_end": "2024-09-30",
            "amount_usd": "30000",
            "seats": "500",
        },
        {
            "invoice_id": "INV-2024-004",
            "vendor_id": "vendor_123",
            "period_start": "2024-10-01",
            "period_end": "2024-12-31",
            "amount_usd": "30000",
            "seats": "500",
        },
    ]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=invoices[0].keys())
        writer.writeheader()
        writer.writerows(invoices)

    print(f"Created invoices CSV: {output_path}")
    total = sum(float(inv["amount_usd"]) for inv in invoices)
    print(f"  Total annual spend: ${total:,.0f}")
    print(f"  Average seats: 500")


def create_usage_csv() -> None:
    """Create a proper usage CSV file."""
    output_path = EXAMPLES_DIR / "usage.csv"
    
    usage_data = [
        {
            "month": "2024-01",
            "vendor_id": "vendor_123",
            "allocated_seats": "500",
            "active_seats": "485",
            "notes": "Initial deployment, gradual adoption",
        },
        {
            "month": "2024-04",
            "vendor_id": "vendor_123",
            "allocated_seats": "500",
            "active_seats": "492",
            "notes": "New team onboarded, usage increasing",
        },
        {
            "month": "2024-07",
            "vendor_id": "vendor_123",
            "allocated_seats": "500",
            "active_seats": "498",
            "notes": "Peak usage period, near capacity",
        },
        {
            "month": "2024-10",
            "vendor_id": "vendor_123",
            "allocated_seats": "500",
            "active_seats": "475",
            "notes": "Some teams churned, usage decreased",
        },
    ]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=usage_data[0].keys())
        writer.writeheader()
        writer.writerows(usage_data)

    print(f"Created usage CSV: {output_path}")
    last = usage_data[-1]
    allocated = int(last["allocated_seats"])
    active = int(last["active_seats"])
    delta = ((active - allocated) / allocated) * 100
    print(f"  Latest: {last['month']}")
    print(f"  Allocated seats: {allocated}")
    print(f"  Active seats: {active}")
    print(f"  Delta: {delta:.1f}%")


def main() -> None:
    """Create all test files."""
    EXAMPLES_DIR.mkdir(exist_ok=True)
    
    print("Creating test files...")
    print()
    
    create_contract_pdf()
    print()
    create_invoices_csv()
    print()
    create_usage_csv()
    print()
    print("All test files created successfully!")


if __name__ == "__main__":
    main()
