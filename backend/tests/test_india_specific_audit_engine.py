import pytest
from decimal import Decimal
from datetime import date, timedelta
from apps.companies.models import Company, FinancialYear, Engagement, EntityType, EngagementType
from apps.accounting.models import ChartOfAccounts, LedgerAccount, Transaction, AccountType, ScheduleIIIGroup, VoucherType
from apps.audit.models import FixedAsset, SubledgerAgingItem, RelatedParty, StatutoryClauseAudit, ExceptionItem
from apps.audit.far_depreciation import FixedAssetAuditEngine
from apps.audit.subledger_analytics import SubledgerAnalyticsEngine
from apps.audit.forensic_scrutiny import ForensicScrutinyEngine
from apps.audit.statutory_forms import StatutoryFormMatrixEngine
from apps.audit.compliance_rules import ComplianceRuleRegistry
from apps.reporting.models import Workpaper
from apps.reporting.services import WorkpaperDraftingService, DemoDataService

@pytest.fixture
def test_company_pvt(db):
    return Company.objects.create(
        name="Apex Infotech Private Limited",
        cin="U72200MH2021PTC356789",
        pan="AABCA9876K",
        gstin="27AABCA9876K1Z1",
        entity_type=EntityType.PVT_LTD
    )

@pytest.fixture
def test_company_llp(db):
    return Company.objects.create(
        name="Horizon Advisory LLP",
        cin="AAA-1234",
        pan="AAAFH1234L",
        entity_type=EntityType.LLP
    )

@pytest.fixture
def test_fy(db, test_company_pvt):
    return FinancialYear.objects.create(
        company=test_company_pvt,
        label="FY 2024-25",
        start_date=date(2024, 4, 1),
        end_date=date(2025, 3, 31)
    )

@pytest.fixture
def test_engagement_stat(db, test_company_pvt, test_fy):
    return Engagement.objects.create(
        company=test_company_pvt,
        financial_year=test_fy,
        title="Statutory & Tax Audit FY 2024-25",
        engagement_type=EngagementType.STATUTORY
    )

@pytest.mark.django_db
def test_caro_2020_and_form3ca_applicability_routing(test_company_pvt, test_company_llp, test_fy):
    """Verifies statutory routing: CARO 2020 applies to companies, exempt for LLPs; Form 3CA vs 3CB routing."""
    eng_pvt = Engagement.objects.create(
        company=test_company_pvt,
        financial_year=test_fy,
        title="Pvt Ltd Statutory Audit",
        engagement_type=EngagementType.STATUTORY
    )
    res_pvt = StatutoryFormMatrixEngine.evaluate_statutory_applicability(eng_pvt)
    assert res_pvt['caro_2020']['is_applicable'] is True
    assert res_pvt['tax_audit_form']['form_type'] == 'FORM_3CA'

    # LLP Audit
    fy_llp = FinancialYear.objects.create(
        company=test_company_llp,
        label="FY 2024-25",
        start_date=date(2024, 4, 1),
        end_date=date(2025, 3, 31)
    )
    eng_llp = Engagement.objects.create(
        company=test_company_llp,
        financial_year=fy_llp,
        title="LLP Statutory Audit",
        engagement_type=EngagementType.LLP_AUDIT
    )
    res_llp = StatutoryFormMatrixEngine.evaluate_statutory_applicability(eng_llp)
    # CARO 2020 is strictly exempt for LLPs under MCA orders
    assert res_llp['caro_2020']['is_applicable'] is False
    assert "Exempt: CARO 2020 does not apply" in res_llp['caro_2020']['reason']
    assert res_llp['tax_audit_form']['form_type'] == 'FORM_3CB'

    # Initialize clauses on LLP: CARO clauses marked EXEMPT
    clauses_llp = StatutoryFormMatrixEngine.initialize_and_audit_clauses(eng_llp)
    caro_clauses = [c for c in clauses_llp if c.form_type == 'CARO_2020']
    assert len(caro_clauses) == 21
    for c in caro_clauses:
        assert c.compliance_status == 'EXEMPT'
        assert c.is_applicable is False

@pytest.mark.django_db
def test_fixed_asset_dual_depreciation_and_half_rate_rule(test_engagement_stat):
    """
    Verifies dual depreciation:
    1. Schedule II useful life SLM with 5% residual value.
    2. Income Tax Act Section 32 block rate.
    3. Half-rate (50%) rule when asset is put to use < 180 days in FY.
    4. Duplicate asset detection.
    """
    far_records = [
        {
            'asset_id': 'FA-001',
            'asset_name': 'Production Database Server',
            'category': 'COMPUTERS & SERVERS',
            'cost': '300000.00',
            'acquisition_date': '2024-04-01',
            'put_to_use_date': '2024-04-01', # Full year (>180 days)
            'accumulated_depreciation': '0.00'
        },
        {
            'asset_id': 'FA-002',
            'asset_name': 'AI GPU Server Cluster',
            'category': 'COMPUTERS & SERVERS',
            'cost': '600000.00',
            'acquisition_date': '2024-11-15',
            'put_to_use_date': '2024-12-01', # Put to use in Dec (<180 days: 121 days)
            'accumulated_depreciation': '0.00'
        },
        {
            # Exact duplicate candidate
            'asset_id': 'FA-003',
            'asset_name': 'Production Database Server',
            'category': 'COMPUTERS & SERVERS',
            'cost': '300000.00',
            'acquisition_date': '2024-04-01',
            'put_to_use_date': '2024-04-01',
            'accumulated_depreciation': '0.00'
        }
    ]

    res = FixedAssetAuditEngine.import_and_validate_far(test_engagement_stat, far_records)
    assert res['total_assets'] == 3
    assert res['duplicate_candidates_count'] >= 1

    asset_full = FixedAsset.objects.get(engagement=test_engagement_stat, asset_id='FA-001')
    # Schedule II: Useful life 3 yrs, 5% residual. Depreciable = 285,000 / 3 = 95,000
    assert asset_full.sch_ii_depreciation == Decimal('95000.00')
    # IT Act: 40% full rate = 300,000 * 40% = 120,000
    assert asset_full.sec_32_depreciation == Decimal('120000.00')

    asset_half = FixedAsset.objects.get(engagement=test_engagement_stat, asset_id='FA-002')
    # IT Act: <180 days -> half rate (40% * 50% = 20%) = 600,000 * 20% = 120,000
    assert asset_half.sec_32_depreciation == Decimal('120000.00')

    # Exception item for duplicate candidate created
    dup_excs = ExceptionItem.objects.filter(engagement=test_engagement_stat, rule_code='RULE_FAR_DUPLICATE_ASSET')
    assert dup_excs.exists()

@pytest.mark.django_db
def test_subledger_aging_and_section_43bh_msme_disallowance(test_engagement_stat):
    """
    Verifies receivables & payables ageing bucket classification and
    Section 43B(h) MSMED Act 45-day overdue disallowance screening.
    """
    as_of = date(2025, 3, 31)
    aging_records = [
        # Receivable 0-30 days
        {
            'item_type': 'RECEIVABLE',
            'party_name': 'Client A Ltd',
            'invoice_number': 'INV-001',
            'invoice_date': '2025-03-15',
            'total_amount': '100000.00',
            'outstanding_amount': '100000.00'
        },
        # Receivable >365 days
        {
            'item_type': 'RECEIVABLE',
            'party_name': 'Client B Old Debt',
            'invoice_number': 'INV-OLD',
            'invoice_date': '2023-12-01',
            'total_amount': '250000.00',
            'outstanding_amount': '250000.00'
        },
        # Payable to Non-MSME
        {
            'item_type': 'PAYABLE',
            'party_name': 'Cloud Vendor Inc',
            'is_msme': False,
            'msme_type': 'NON_MSME',
            'invoice_number': 'V-001',
            'invoice_date': '2024-11-01',
            'total_amount': '50000.00',
            'outstanding_amount': '50000.00'
        },
        # Payable to Micro enterprise (<45 days: Compliant)
        {
            'item_type': 'PAYABLE',
            'party_name': 'Micro Vendor Compliant',
            'is_msme': True,
            'msme_type': 'MICRO',
            'invoice_number': 'M-001',
            'invoice_date': '2025-03-01', # 30 days
            'total_amount': '35000.00',
            'outstanding_amount': '35000.00'
        },
        # Payable to Small enterprise (>45 days: OVERDUE under 43B(h)!)
        {
            'item_type': 'PAYABLE',
            'party_name': 'Small Enterprise Overdue',
            'is_msme': True,
            'msme_type': 'SMALL',
            'invoice_number': 'S-OVERDUE',
            'invoice_date': '2024-12-01', # 120 days
            'total_amount': '85000.00',
            'outstanding_amount': '85000.00',
            'has_written_agreement': True
        }
    ]

    analysis = SubledgerAnalyticsEngine.process_subledger_items(test_engagement_stat, aging_records, as_of)
    assert analysis['receivables']['buckets']['0-30 days'] == '100000.00'
    assert analysis['receivables']['buckets']['>365 days'] == '250000.00'
    assert analysis['msme_compliance']['overdue_count'] == 1
    assert analysis['msme_compliance']['overdue_amount_section_43bh'] == '85000.00'
    assert analysis['msme_compliance']['status'] == 'DISALLOWANCE_REQUIRED'

    # Verify critical ExceptionItem created
    msme_exc = ExceptionItem.objects.filter(engagement=test_engagement_stat, rule_code='RULE_MSME_OVERDUE_43BH').first()
    assert msme_exc is not None
    assert msme_exc.amount_involved == Decimal('85000.00')
    assert "Section 43B(h)" in msme_exc.title

@pytest.mark.django_db
def test_documentary_inventory_movement_equation(test_engagement_stat):
    """Verifies stock equation (Opening + Purchases - Sales = Closing) and negative stock alerts."""
    stock_items = [
        {
            'item_code': 'SKU-OK',
            'description': 'Laptop Model X',
            'opening_qty': 10,
            'opening_rate': 50000,
            'inward_qty': 20,
            'outward_qty': 15,
            'closing_qty': 15, # 10 + 20 - 15 = 15
            'closing_rate': 50000
        },
        {
            'item_code': 'SKU-NEG',
            'description': 'Server RAM module',
            'opening_qty': 5,
            'opening_rate': 4000,
            'inward_qty': 5,
            'outward_qty': 15,
            'closing_qty': -5, # Negative!
            'closing_rate': 4000
        }
    ]

    res = SubledgerAnalyticsEngine.verify_documentary_inventory(test_engagement_stat, stock_items)
    assert res['negative_stock_count'] == 1
    assert "SA 501" in res['disclaimer']
    neg_exc = ExceptionItem.objects.filter(engagement=test_engagement_stat, rule_code='RULE_NEGATIVE_STOCK').first()
    assert neg_exc is not None

@pytest.mark.django_db
def test_related_party_and_forensic_journal_scrutiny(test_engagement_stat):
    """Verifies counterparty scrutiny against Section 2(76) related parties and SA 240 forensic journal flags."""
    party_data = [{
        'party_name': 'Mehra Tech Ventures',
        'pan': 'AABCM1122K',
        'relationship_type': 'Director Interested Firm',
        'applicable_standard': 'SECTION_2_76'
    }]

    coa = ChartOfAccounts.objects.create(
        company=test_engagement_stat.company,
        account_code='4102',
        account_name='Consultancy Fees',
        account_type=AccountType.EXPENSE,
        schedule_iii_group=ScheduleIIIGroup.OTHER_EXPENSES
    )
    ledger = LedgerAccount.objects.create(company=test_engagement_stat.company, code='4102', name='Consultancy Fees', coa=coa)

    # 1. Related party transaction
    Transaction.objects.create(
        engagement=test_engagement_stat,
        ledger_account=ledger,
        voucher_number='JV-RP-01',
        voucher_type=VoucherType.JOURNAL,
        date=date(2024, 10, 15),
        counterparty='Mehra Tech Ventures',
        narration='Advisory services fees',
        debit_amount=Decimal('250000.00'),
        credit_amount=Decimal('0.00')
    )

    # 2. Weekend posting on Sunday (Nov 24, 2024 is Sunday)
    Transaction.objects.create(
        engagement=test_engagement_stat,
        ledger_account=ledger,
        voucher_number='JV-SUN-01',
        voucher_type=VoucherType.JOURNAL,
        date=date(2024, 11, 24),
        counterparty='Generic Vendor',
        narration='Cloud billing',
        debit_amount=Decimal('80000.00'),
        credit_amount=Decimal('0.00')
    )

    # 3. Round amount voucher
    Transaction.objects.create(
        engagement=test_engagement_stat,
        ledger_account=ledger,
        voucher_number='JV-RND-01',
        voucher_type=VoucherType.JOURNAL,
        date=date(2025, 1, 10),
        counterparty='Consulting Co',
        narration='Round amount retainer',
        debit_amount=Decimal('100000.00'),
        credit_amount=Decimal('0.00')
    )

    rp_res = ForensicScrutinyEngine.scrutinize_related_parties(test_engagement_stat, party_data)
    assert rp_res['total_related_parties'] == 1
    assert rp_res['matched_transactions_count'] == 1
    assert rp_res['total_volume'] == '250000.00'

    jr_res = ForensicScrutinyEngine.scrutinize_manual_journals(test_engagement_stat)
    assert jr_res['manual_journal_count'] == 3
    assert jr_res['weekend_journals_count'] >= 1
    assert jr_res['round_amount_journals_count'] >= 1

@pytest.mark.django_db
def test_compliance_rule_registry_versioned_evaluation(test_engagement_stat):
    """Verifies versioned statutory compliance rule evaluation with legal citations."""
    context_data = {
        'cash_transactions': [
            {'voucher': 'V-1', 'amount': '25000.00', 'party': 'Sharma Works'} # >10,000
        ],
        'payables_aging': [
            {'msme_type': 'MICRO', 'outstanding_amount': '45000.00', 'overdue_days': 60, 'has_written_agreement': True} # >45 days
        ],
        'far_immovable_properties': [],
        'statutory_dues': [],
        'tds_scrutiny_expenses': [
            {'tds_applicable': True, 'tds_deducted': False, 'amount': '100000.00'} # 30% disallowance under 40(a)(ia)
        ]
    }

    results = ComplianceRuleRegistry.evaluate_all(test_engagement_stat, context_data)
    rule_map = {r['rule_id']: r for r in results}

    assert 'RULE_IN_TAX_40A3_v24' in rule_map
    assert rule_map['RULE_IN_TAX_40A3_v24']['status'] == 'EXCEPTION_NOTED'
    assert rule_map['RULE_IN_TAX_40A3_v24']['amount_involved'] == Decimal('25000.00')

    assert 'RULE_IN_TAX_43BH_v24' in rule_map
    assert rule_map['RULE_IN_TAX_43BH_v24']['status'] == 'EXCEPTION_NOTED'
    assert rule_map['RULE_IN_TAX_43BH_v24']['amount_involved'] == Decimal('45000.00')

    assert 'RULE_IN_TAX_40AIA_v24' in rule_map
    assert rule_map['RULE_IN_TAX_40AIA_v24']['status'] == 'EXCEPTION_NOTED'
    # 30% of 100,000 = 30,000
    assert rule_map['RULE_IN_TAX_40AIA_v24']['amount_involved'] == Decimal('30000.00')

@pytest.mark.django_db
def test_demo_dataset_phase4_integration():
    """Verifies DemoDataService generates all Phase 4 models, workpapers, and statutory matrices."""
    engagement = DemoDataService.generate_demo_dataset()
    assert engagement is not None

    # Check workflow config
    assert hasattr(engagement, 'workflow_config')
    assert engagement.workflow_config.applicable_framework == 'COMPANIES_ACT_2013'
    assert engagement.workflow_config.caro_applicable is True

    # Check fixed assets
    assert FixedAsset.objects.filter(engagement=engagement).count() >= 4

    # Check subledger aging
    assert SubledgerAgingItem.objects.filter(engagement=engagement).count() >= 6
    assert SubledgerAgingItem.objects.filter(engagement=engagement, is_overdue_43bh=True).exists()

    # Check related parties
    assert RelatedParty.objects.filter(engagement=engagement).exists()

    # Check statutory clauses
    assert StatutoryClauseAudit.objects.filter(engagement=engagement, form_type='CARO_2020').count() == 21
    assert StatutoryClauseAudit.objects.filter(engagement=engagement, form_type='FORM_3CD').count() >= 9

    # Check Phase 4 workpapers drafted
    wps = list(Workpaper.objects.filter(engagement=engagement).values_list('wp_reference', flat=True))
    for expected_wp in ['WP-A101', 'WP-A102', 'WP-B201', 'WP-B202', 'WP-T301', 'WP-G401', 'WP-F501', 'WP-M501', 'WP-R502', 'WP-P503', 'WP-J504', 'WP-C601', 'WP-T302']:
        assert expected_wp in wps, f"Expected workpaper {expected_wp} was not drafted"

@pytest.mark.django_db
def test_schedule_iii_unmapped_fail_closed_and_adjusted_balances(test_engagement_stat):
    """
    Verifies Schedule III fail-closed principle:
    1. Unmapped accounts trigger explicit review required state and never silently classify.
    2. Side-by-side original vs adjusted balances incorporate AJEs.
    """
    from apps.accounting.views import LedgerAccountViewSet
    from apps.reporting.models import ProposedAdjustment, AdjustmentStatus
    from rest_framework.test import APIRequestFactory

    company = test_engagement_stat.company
    coa = ChartOfAccounts.objects.create(
        company=company,
        account_code='9999',
        account_name='Suspense / Unmapped Account',
        account_type=AccountType.ASSET,
        schedule_iii_group=ScheduleIIIGroup.OTHER_CURRENT_ASSETS
    )
    acc = LedgerAccount.objects.create(
        company=company,
        name='Suspense / Unmapped Account',
        code='9999',
        coa=coa,
        closing_balance=Decimal('50000.00'),
        closing_balance_type='DEBIT',
        mapping_status='UNMAPPED'
    )

    # 1. Test unmapped action
    factory = APIRequestFactory()
    view = LedgerAccountViewSet.as_view({'get': 'unmapped'})
    req = factory.get(f'/api/accounting/ledgers/unmapped/?company={company.id}')
    resp = view(req)
    assert resp.status_code == 200
    assert resp.data['fail_closed_alert'] is True
    assert resp.data['count'] >= 1
    unmapped_names = [a['name'] for a in resp.data['unmapped_accounts']]
    assert 'Suspense / Unmapped Account' in unmapped_names

    # 2. Add an AJE impacting this account
    ProposedAdjustment.objects.create(
        engagement=test_engagement_stat,
        adjustment_number="AJE-TEST-01",
        title="Reclassify Suspense",
        reason="Auditor AJE reclassification",
        journal_entries=[
            {'account': 'Suspense / Unmapped Account', 'debit': '0.00', 'credit': '10000.00'}
        ],
        total_debit=Decimal('10000.00'),
        total_credit=Decimal('10000.00'),
        status=AdjustmentStatus.PROPOSED
    )

    # 3. Test adjusted_balances action
    view_adj = LedgerAccountViewSet.as_view({'get': 'adjusted_balances'})
    req_adj = factory.get(f'/api/accounting/ledgers/adjusted_balances/?engagement={test_engagement_stat.id}')
    resp_adj = view_adj(req_adj)
    assert resp_adj.status_code == 200
    acc_bal = next(b for b in resp_adj.data['balances'] if b['name'] == 'Suspense / Unmapped Account')
    assert acc_bal['original_balance'] == '50000.00'
    assert acc_bal['adjustments_credit'] == '10000.00'
    # 50,000 debit minus 10,000 credit adjustment = 40,000
    assert acc_bal['adjusted_balance'] == '40000.00'
    assert acc_bal['has_adjustments'] is True

