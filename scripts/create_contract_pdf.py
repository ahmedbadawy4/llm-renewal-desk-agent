#!/usr/bin/env python3
"""Create contract PDF using pymupdf."""
from __future__ import annotations

from pathlib import Path

try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples"


def create_contract_pdf() -> None:
    """Create a proper contract PDF with all required fields."""
    if not HAS_PYMUPDF:
        print("pymupdf not available. Install with: pip install pymupdf")
        return

    output_path = EXAMPLES_DIR / "sample_contract.pdf"
    
    doc = fitz.open()
    page = doc.new_page()
    
    text = """SOFTWARE LICENSE AGREEMENT

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
    
    rect = page.rect
    margin = 50
    text_rect = fitz.Rect(margin, margin, rect.width - margin, rect.height - margin)
    
    page.insert_textbox(
        text_rect,
        text,
        fontsize=11,
        fontname="helv",
        align=0,
    )
    
    doc.save(str(output_path))
    doc.close()
    print(f"Created contract PDF: {output_path}")


if __name__ == "__main__":
    create_contract_pdf()
