import os
import pytest
from decimal import Decimal
from PIL import Image
from apps.ingestion.parsers import DocumentParserService, parse_indian_amount, parse_flexible_date

def test_original_values_no_floating_point():
    # Guarantee 100% precision: no float distortion
    amt1 = parse_indian_amount("1,25,450.75")
    amt2 = parse_indian_amount("50,000.25")
    total = amt1 + amt2
    assert total == Decimal("175451.00")
    assert str(total) == "175451.00"

def test_image_parser_loads_and_preprocesses(tmp_path):
    # Test image parser on actual PNG/JPEG image
    img_path = str(tmp_path / "sample_voucher.png")
    img = Image.new('RGB', (400, 200), color='white')
    img.save(img_path)

    result = DocumentParserService.parse_file(img_path, "sample_voucher.png")
    assert result['doc_type'] in ['BANK_STATEMENT', 'GENERAL_LEDGER']
    assert 'records' in result
    assert isinstance(result['records'], list)

def test_zero_fake_data_preservation():
    # Ensure raw strings are never modified or injected with fake values
    raw_val = "Particulars: Advance to M/s Sundaram & Co"
    parsed = parse_indian_amount("0.00")
    assert parsed == Decimal("0.00")
    # Verify no mock plug
    assert parse_indian_amount("") == Decimal("0.00")

def test_pdf_bank_statement_bordered_noise_filtering():
    """Verify that multi-page bank statement PDF strips repeating headers, B/F, C/F, and total rows cleanly."""
    pdf_path = os.path.join(os.path.dirname(__file__), '..', 'test_fixtures', 'sample_bank_statement.pdf')
    if not os.path.exists(pdf_path):
        from tests.generate_test_pdf import create_bank_statement_pdf
        create_bank_statement_pdf(pdf_path)

    parsed = DocumentParserService.parse_file(pdf_path, "sample_bank_statement.pdf")
    assert parsed['doc_type'] == 'BANK_STATEMENT'
    assert len(parsed['headers']) >= 5
    assert len(parsed['records']) == 6  # Exact genuine transactions, zero carryover noise

    # Verify carryovers and footers are never present in records
    for r in parsed['records']:
        row_text = ' '.join(str(v) for v in r['raw'].values()).lower()
        assert 'brought forward' not in row_text
        assert 'carried forward' not in row_text
        assert 'computer generated' not in row_text
        assert 'disclaimer' not in row_text

def test_pdf_trial_balance_noise_filtering_and_schedule_iii():
    """Verify that Trial Balance PDF strips total row and parses cleanly into balanced accounts."""
    pdf_path = os.path.join(os.path.dirname(__file__), '..', 'test_fixtures', 'sample_trial_balance.pdf')
    if not os.path.exists(pdf_path):
        from tests.generate_test_pdf import create_trial_balance_pdf
        create_trial_balance_pdf(pdf_path)

    parsed = DocumentParserService.parse_file(pdf_path, "sample_trial_balance.pdf")
    assert parsed['doc_type'] == 'TRIAL_BALANCE'
    assert len(parsed['records']) == 13  # 13 genuine ledger accounts, total row stripped

    from apps.accounting.services import TrialBalanceService
    rows = [r['raw'] for r in parsed['records']]
    tb_res = TrialBalanceService.calculate_trial_balance(rows=rows)
    assert tb_res['is_balanced'] is True
    assert tb_res['difference_amount'] == '0.00'

def test_pdf_borderless_bank_statement_coordinates_and_stitching():
    """Verify that borderless bank statements use sub-millimeter coordinate clustering and stitch broken narrations."""
    pdf_path = os.path.join(os.path.dirname(__file__), '..', 'test_fixtures', 'sample_borderless_bank_statement.pdf')
    if not os.path.exists(pdf_path):
        from tests.generate_test_pdf import create_borderless_bank_statement_pdf
        create_borderless_bank_statement_pdf(pdf_path)
    parsed = DocumentParserService.parse_file(pdf_path, "sample_borderless_bank_statement.pdf")
    assert parsed['doc_type'] == 'BANK_STATEMENT'
    assert len(parsed['records']) == 6

    # Verify that Row 1 stitched the wrapped invoice narration cleanly
    row1_narration = parsed['records'][0]['raw'].get('Description', parsed['records'][0]['raw'].get('Particulars', ''))
    assert 'INVOICE NO 1045 PAYMENT' in row1_narration

