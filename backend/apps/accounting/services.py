import re
import math
from functools import lru_cache
from decimal import Decimal
from datetime import datetime, date
from collections import defaultdict
from .models import TrialBalanceSnapshot, Transaction, LedgerAccount, ChartOfAccounts, ScheduleIIIGroup, AccountType, VoucherType
from apps.ingestion.parsers import parse_indian_amount

BENFORD_EXPECTED = {
    1: 0.301,
    2: 0.176,
    3: 0.125,
    4: 0.097,
    5: 0.079,
    6: 0.067,
    7: 0.058,
    8: 0.051,
    9: 0.046
}

@lru_cache(maxsize=65536)
def classify_schedule_iii(account_name: str) -> str:
    """
    Deterministically maps Indian ledger account names to Schedule III Division I & II groupings.
    Supports all business scales: small proprietorships, partnerships, MSMEs, IT/tech startups,
    and large corporations, resolving every micro employee, cloud, SaaS, and subledger account.
    """
    if not account_name:
        return ScheduleIIIGroup.OTHER_EXPENSES
    name = str(account_name).lower().strip()
    if name.startswith('head ') or name.startswith('account item ') or name.startswith('test account '):
        return ScheduleIIIGroup.OTHER_EXPENSES

    words = set(name.replace('-', ' ').replace('/', ' ').replace('&', ' ').replace('(', ' ').replace(')', ' ').replace('.', ' ').split())

    has_payable_term = any(w in words for w in ['payable', 'due', 'accrued', 'outstanding', 'liability']) or any(
        k in name for k in ['payable', 'due', 'accrued', 'outstanding', 'liability', 'deduction']
    )
    has_advance_term = any(w in words for w in ['advance', 'prepaid', 'deposit', 'receivable']) or any(
        k in name for k in ['advance', 'prepaid', 'deposit', 'receivable']
    )

    # -------------------------------------------------------------------------
    # STEP 0: DEPRECIATION AND AMORTIZATION (P&L EXPENSE)
    # Must precede PPE and Intangibles so "Depreciation on Laptops/Machinery"
    # or "Amortization of Software" is classified as DEPRECIATION_AMORT, not PPE.
    # -------------------------------------------------------------------------
    if any(k in name for k in ['accumulated depreciation', 'provision for depreciation']):
        return ScheduleIIIGroup.PPE  # Contra asset under PPE
    if any(k in name for k in [
        'depreciation', 'amortization', 'amortisation', 'depreciation & amortization'
    ]):
        return ScheduleIIIGroup.DEPRECIATION_AMORT

    # -------------------------------------------------------------------------
    # STEP 0B: FINANCE COSTS & INTEREST EXPENSES (P&L EXPENSE)
    # Must precede Borrowings and Bank Accounts so "Interest on Term Loan",
    # "Interest on CC", and "Bank Charges" are classified as FINANCE_COSTS.
    # -------------------------------------------------------------------------
    if any(k in name for k in [
        'interest on loan', 'interest on bank loan', 'interest on term loan', 'interest on borrowing',
        'interest on od', 'interest on cc', 'interest on cash credit', 'interest paid', 'interest expense',
        'bank charges', 'bank fee', 'finance charge', 'finance charges', 'finance costs', 'bank commission',
        'loan processing charges', 'loan processing fee', 'cheque return charges', 'cheque bounce charges',
        'lc charges', 'bank guarantee charges', 'bill discounting charges', 'interest on msme', 'msme interest'
    ]) or (
        'interest' in words and any(b in words for b in ['loan', 'cc', 'od', 'borrowing', 'term', 'debenture', 'msme']) and not any(inc in words for inc in ['income', 'received', 'accrued', 'receivable'])
    ) or (
        'processing fee' in name and any(b in name for b in ['bank', 'loan', 'credit', 'finance'])
    ):
        return ScheduleIIIGroup.FINANCE_COSTS

    # -------------------------------------------------------------------------
    # STEP 0C: DIRECT MANUFACTURING / PURCHASES / INWARD FREIGHT & CARTAGE
    # Must precede Cloud Services, General Expenses and Trading Goods
    # -------------------------------------------------------------------------
    if any(k in name for k in [
        'cost of materials', 'cost of material', 'cost of goods sold', 'cogs',
        'raw material purchase', 'raw materials purchase', 'raw material consumed',
        'trading purchase', 'purchase of stock-in-trade', 'purchases - trading',
        'freight inward', 'carriage inward', 'cartage inward', 'transport inward',
        'customs duty', 'import duty', 'clearing & forwarding inward', 'octroi inward',
        'loading and unloading', 'hamali', 'coolie & cartage', 'direct expenses',
        'manufacturing expenses', 'factory wages', 'factory rent', 'factory power', 'power & fuel',
        'job work charges paid', 'processing charges'
    ]) or (
        'purchases' in words and not any(x in words for x in ['asset', 'fixed', 'equipment'])
    ) or (
        'purchase' in words and any(g in words for g in ['goods', 'trading', 'material', 'materials', 'stock'])
    ) or (
        'cartage' in words and not any(out in name for out in ['outward', 'delivery', 'sales'])
    ):
        return ScheduleIIIGroup.COST_OF_MATERIALS

    # -------------------------------------------------------------------------
    # STEP 1: SPECIFIC STATUTORY & OPERATING LIABILITIES (PAYABLES & PROVISIONS)
    # Must precede general expense names so "Salary Payable" is not classified as "Salary"
    # -------------------------------------------------------------------------

    # 1A. Long-Term Provisions (e.g., Gratuity liability)
    if any(k in name for k in ['long term gratuity', 'long-term gratuity', 'provision for gratuity', 'gratuity provision (long term)']) and not has_advance_term:
        if not any(exp in words for exp in ['expense', 'charge', 'cost', 'paid']):
            return ScheduleIIIGroup.LONG_TERM_PROVISIONS

    # 1B. Short-Term Provisions
    if any(k in name for k in [
        'provision for tax', 'tax provision', 'provision for income tax', 'current tax provision',
        'provision for bonus', 'provision for leave encashment', 'provision for expenses',
        'provision for warranties'
    ]) and not has_advance_term and not any(exp in words for exp in ['expense', 'cost', 'charge']):
        return ScheduleIIIGroup.SHORT_TERM_PROVISIONS

    # 1C. Trade Payables (Creditors, Vendors, Suppliers, MSME)
    if any(k in name for k in [
        'sundry creditor', 'sundry creditors', 'trade creditor', 'trade creditors',
        'trade payable', 'trade payables', 'accounts payable', 'vendor payable',
        'suppliers payable', 'creditor for goods', 'creditor for supplies', 'creditor for purchase',
        'msme creditor', 'msme payable', 'micro enterprise', 'small enterprise', 'bills payable', 'acceptances'
    ]) and not any(adv in name for adv in ['advance to', 'advance against', 'prepaid']):
        return ScheduleIIIGroup.TRADE_PAYABLES

    # 1D. Other Current Liabilities (Statutory Dues & Operating Payables)
    is_pf = any(k in name for k in ['provident fund', 'pf', 'epf'])
    is_esi = any(k in name for k in ['esi', 'esic'])
    is_pt = any(k in name for k in ['professional tax', ' pt ']) or name.startswith('pt ') or name.endswith(' pt') or '(pt)' in name or 'pt payable' in name
    is_lwf = any(k in name for k in ['labour welfare fund', ' lwf ']) or name.startswith('lwf ') or name.endswith(' lwf') or '(lwf)' in name or 'lwf payable' in name
    is_tds = any(k in name for k in ['tds', 'tcs', 'withholding tax'])
    is_gst_out = any(k in name for k in ['gst payable', 'output gst', 'output cgst', 'output sgst', 'output igst', 'output utgst', 'rcm payable', 'reverse charge payable'])

    if is_gst_out:
        return ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES

    if has_payable_term:
        if is_pf or is_esi or is_pt or is_lwf or is_tds:
            return ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES
        if any(k in name for k in [
            'salary', 'salaries', 'wages', 'bonus', 'incentive', 'stipend', 'gratuity',
            'leave encashment', 'reimbursement', 'director remuneration', 'partner salary',
            'audit fee', 'expenses', 'charges', 'rent', 'electricity', 'telephone',
            'subcontractor', 'consulting fee'
        ]):
            return ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES
        if any(k in name for k in ['duties & taxes', 'duties and taxes', 'statutory', 'tax deduction']):
            return ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES

    if any(k in name for k in [
        'advance from customer', 'customer advance', 'unearned revenue', 'deferred revenue',
        'advance billing', 'income received in advance', 'retention money payable',
        'security deposit received', 'security deposit payable'
    ]):
        return ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES

    # -------------------------------------------------------------------------
    # STEP 2: ADVANCES, PREPAIDS & SHORT-TERM LOANS (ASSETS)
    # Must precede general expenses and trade payables
    # -------------------------------------------------------------------------
    if any(k in name for k in [
        'staff advance', 'advance to staff', 'employee advance', 'staff loan', 'festival advance',
        'salary advance', 'travel advance', 'imprest advance', 'short term advance', 'short term loan given',
        'loan to director', 'loan to employee'
    ]):
        return ScheduleIIIGroup.SHORT_TERM_LOANS

    if any(k in name for k in [
        'gst input', 'input gst', 'input cgst', 'input sgst', 'input igst', 'input utgst',
        'input tax credit', 'itc', 'gst credit', 'electronic cash ledger', 'gst electronic cash ledger',
        'electronic credit ledger', 'gst electronic credit ledger', 'cash ledger', 'credit ledger',
        'tds receivable', 'tcs receivable', 'advance tax', 'advance income tax', 'income tax paid',
        'advance tax paid', 'self assessment tax', 'income tax refund', 'mat credit',
        'advance to vendor', 'advance to supplier', 'supplier advance', 'vendor advance',
        'advance against purchase', 'accrued interest', 'interest accrued'
    ]) or (
        'advance' in words and 'tax' in words
    ):
        return ScheduleIIIGroup.OTHER_CURRENT_ASSETS

    if any(k in name for k in ['prepaid expense', 'prepaid expenses', 'prepaid insurance', 'prepaid rent', 'prepaid software', 'prepaid amc']) or (
        'prepaid' in words and not has_payable_term
    ):
        return ScheduleIIIGroup.OTHER_CURRENT_ASSETS

    # -------------------------------------------------------------------------
    # STEP 3: BORROWINGS (SHORT-TERM VS LONG-TERM)
    # Must precede cash & bank to avoid "Bank OD" or "CC Limit" being treated as bank balance
    # -------------------------------------------------------------------------
    if any(k in name for k in [
        'cash credit', 'cc limit', 'cc a/c', 'cc account', 'bank od', 'bank overdraft', 'od limit',
        'overdraft', 'working capital loan', 'working capital facility', 'short term loan',
        'short term borrowing', 'packing credit', 'buyer credit', 'bill discounting',
        'unsecured loan', 'loan from director', 'loan from directors', 'loan from partner',
        'loan from partners', 'directors loan', 'partners loan', 'loan from promoter',
        'inter-corporate deposit', 'icd'
    ]):
        return ScheduleIIIGroup.SHORT_TERM_BORROWINGS

    if any(k in name for k in [
        'term loan', 'bank term loan', 'housing loan', 'vehicle loan', 'car loan', 'equipment loan',
        'machinery loan', 'project loan', 'mortgage loan', 'debenture', 'debentures', 'bonds',
        'long term loan', 'long term borrowing', 'borrowing', 'secured loan',
        'external commercial borrowing', 'ecb'
    ]):
        return ScheduleIIIGroup.LONG_TERM_BORROWINGS

    # -------------------------------------------------------------------------
    # STEP 4: EQUITY & RESERVES
    # -------------------------------------------------------------------------
    if 'capital reserve' in name or 'capital redemption reserve' in name:
        return ScheduleIIIGroup.RESERVES_SURPLUS

    if any(k in name for k in [
        'share capital', 'equity capital', 'equity share', 'preference share', 'promoter capital',
        'proprietor capital', "proprietor's capital", 'partner capital', "partner's capital",
        'partners capital', 'owner capital', 'paid up capital', 'called up capital', 'capital a/c',
        'capital account', 'founders capital'
    ]):
        return ScheduleIIIGroup.SHARE_CAPITAL

    if 'capital' in words and not any(x in name for x in [
        'working capital', 'capital work', 'gain', 'reserve', 'redemption', 'subsidy',
        'employed', 'expenditure', 'capitalized', 'capitalised', 'advance'
    ]):
        return ScheduleIIIGroup.SHARE_CAPITAL

    if any(k in name for k in [
        'reserve', 'surplus', 'retained earning', 'retained earnings', 'profit and loss', 'p&l',
        'general reserve', 'securities premium', 'share premium', 'statutory reserve',
        'special reserve', 'debenture redemption reserve', 'revaluation reserve',
        'drawings', "proprietor's drawings", 'proprietor drawings', 'partner drawings',
        'partners drawings', 'dividend', 'interim dividend', 'proposed dividend'
    ]):
        return ScheduleIIIGroup.RESERVES_SURPLUS

    # -------------------------------------------------------------------------
    # STEP 5: NON-CURRENT ASSETS (INTANGIBLES, INVESTMENTS, DEPOSITS, PPE)
    # -------------------------------------------------------------------------
    # 5A. Intangibles (Software, Licenses, Patents, IP, Goodwill)
    if any(k in name for k in [
        'software license', 'software asset', 'computer software', 'erp software',
        'erp implementation', 'patent', 'patents', 'trademark', 'trademarks', 'brand',
        'copyright', 'copyrights', 'goodwill', 'intellectual property', 'ip rights',
        'domain name', 'website development cost', 'intangible asset', 'intangible'
    ]) and not any(sub in name for sub in ['subscription', 'saas', 'amc', 'maintenance', 'monthly', 'annual fee']):
        return ScheduleIIIGroup.INTANGIBLE

    # 5B. Non-Current Investments
    if any(k in name for k in [
        'investment', 'investments', 'investment in subsidiary', 'shares', 'equity shares',
        'preference shares', 'mutual fund', 'mutual funds', 'bonds investment', 'government securities',
        'g-sec', 'national savings certificate', 'nsc', 'fixed deposit (non-current)', 'long term fd'
    ]) and not any(inc in words for inc in ['income', 'gain', 'interest', 'dividend']):
        return ScheduleIIIGroup.NON_CURRENT_INVESTMENTS

    # 5C. Long-Term Loans & Deposits
    if any(k in name for k in [
        'security deposit', 'rental deposit', 'office deposit', 'electricity deposit', 'eb deposit',
        'telephone deposit', 'water deposit', 'tender deposit', 'earnest money deposit', 'emd',
        'lease deposit', 'vat deposit', 'sales tax deposit', 'capital advance', 'long-term loan',
        'long term loan', 'long term loans & advances', 'long term advance'
    ]):
        return ScheduleIIIGroup.LONG_TERM_LOANS_ADV

    # 5D. Cloud Services & SaaS Tools (MUST precede physical PPE hardware checks!)
    # Cloud hosting/servers (AWS, Azure, GCP, domain, SSL) are OPEX, NOT physical PPE servers
    is_cloud_tool = any(k in name for k in [
        'aws', 'amazon web services', 'azure', 'microsoft azure', 'google cloud', 'gcp',
        'digitalocean', 'linode', 'hetzner', 'cloud hosting', 'server hosting', 'web hosting',
        'cloud servers', 'cloud infrastructure', 'mongodb', 'redis', 'datadog', 'sentry',
        'new relic', 'pagerduty', 'cloudflare', 'fastly', 'twilio', 'sendgrid', 'mailchimp',
        'openai', 'chatgpt', 'anthropic', 'claude api', 'gemini api', 'api subscription',
        'github', 'gitlab', 'jira', 'atlassian', 'confluence', 'slack', 'zoom', 'microsoft teams',
        'google workspace', 'g-suite', 'office 365', 'notion', 'figma', 'trello', 'asana',
        'adobe creative cloud', 'razorpay', 'stripe', 'cashfree', 'payment gateway',
        'domain renewal', 'ssl certificate', 'ssl certificates', 'domain registration'
    ]) or (
        ('domain' in words or 'ssl' in words or 'dns' in words) and not any(x in name for x in ['asset', 'income', 'revenue'])
    )
    is_income_or_rev = any(inc in words for inc in ['income', 'revenue', 'receipts', 'billing', 'sales'])
    if is_cloud_tool and not is_income_or_rev and not any(cap in name for cap in ['asset', 'capitalized', 'capitalised', 'gross block']):
        return ScheduleIIIGroup.OTHER_EXPENSES

    # 5E. Property, Plant and Equipment (Physical Hardware, Land, Buildings, Vehicles)
    # Protect against 'car' in 'cartage' and 'monitor' in 'monitoring'
    is_vehicle = any(v in words for v in ['car', 'cars', 'vehicle', 'vehicles', 'bike', 'truck', 'van']) or any(
        k in name for k in ['motor car', 'delivery van', 'two wheeler']
    )
    is_monitor = ('monitor' in words or 'monitors' in words) and 'monitoring' not in name
    if any(k in name for k in [
        'plant', 'machinery', 'computer', 'computers', 'laptop', 'laptops', 'desktop', 'macbook',
        'networking equipment', 'router', 'switch', 'firewall', 'ups', 'printer', 'scanner',
        'office equipment', 'furniture', 'fixture', 'furnitures & fixtures', 'interior decoration',
        'air conditioner', 'ac plant', 'cctv', 'building', 'office building', 'factory building',
        'land', 'freehold land', 'leasehold land', 'gross block', 'fixed asset',
        'capital work in progress', 'cwip'
    ]) or (
        'server' in words and not any(cl in name for cl in ['cloud', 'azure', 'aws', 'gcp', 'hosting'])
    ) or (
        'servers' in words and not any(cl in name for cl in ['cloud', 'azure', 'aws', 'gcp', 'hosting'])
    ) or is_vehicle or is_monitor or (
        'hardware' in words and not any(x in name for x in ['purchase', 'trading', 'sale', 'sales'])
    ):
        return ScheduleIIIGroup.PPE

    # -------------------------------------------------------------------------
    # STEP 6: CURRENT ASSETS (INVENTORIES, TRADE RECEIVABLES, CASH & BANK)
    # -------------------------------------------------------------------------
    if any(k in name for k in [
        'inventory', 'inventories', 'stock', 'stock in hand', 'closing stock', 'opening stock',
        'raw material', 'raw materials', 'work in progress', 'wip', 'semi-finished goods', 'finished goods',
        'stock in trade', 'traded goods', 'stores & spares', 'packing material', 'packing materials', 'consumables'
    ]) and not any(exp in words for exp in ['purchase', 'purchases', 'consumed', 'consumption', 'sale', 'sales']):
        return ScheduleIIIGroup.INVENTORIES

    if any(k in name for k in [
        'sundry debtor', 'sundry debtors', 'trade debtor', 'trade debtors', 'debtor',
        'customer', 'client', 'bills receivable', 'trade receivable', 'trade receivables',
        'accounts receivable', 'customer receivable', 'clients receivable', 'unbilled revenue', 'contract asset'
    ]) and not any(liab in name for liab in ['advance from', 'unearned', 'deferred', 'payable']):
        return ScheduleIIIGroup.TRADE_RECEIVABLES

    # Cash and Cash Equivalents (protect against 'encashment' matching 'cash')
    is_cash = any(k in name for k in ['cash in hand', 'petty cash', 'imprest cash', 'cash balance', 'cash account', 'cash a/c']) or (
        'cash' in words and 'encashment' not in name and not any(x in name for x in ['discount', 'ledger', 'flow', 'credit'])
    )
    is_bank = any(k in name for k in [
        'bank account', 'bank balance', 'bank a/c', 'current account', 'savings account',
        'sweep deposit', 'flexi deposit', 'short term fd', 'fixed deposit with bank'
    ]) or any(b in words for b in [
        'bank', 'hdfc', 'icici', 'sbi', 'axis', 'kotak', 'pnb', 'canara', 'bob', 'indusind',
        'idbi', 'citibank', 'hsbc', 'dbs', 'rbl'
    ]) or any(k in name for k in ['state bank', 'punjab national bank', 'bank of baroda', 'union bank', 'federal bank', 'standard chartered', 'bandhan bank'])

    has_bank_borrowing_or_exp = any(w in words for w in ['interest', 'charges', 'fee', 'loan', 'od', 'overdraft', 'cc']) or any(
        k in name for k in ['bank charges', 'bank fee', 'term loan', 'cash credit', 'bank od', 'od limit', 'cc limit', 'cc a/c', 'cc account']
    )

    if (is_cash or is_bank) and not has_bank_borrowing_or_exp:
        return ScheduleIIIGroup.CASH_EQUIVALENTS

    # -------------------------------------------------------------------------
    # STEP 7: REVENUE FROM OPERATIONS & OTHER INCOME
    # -------------------------------------------------------------------------
    if any(k in name for k in [
        # IT / Tech / Software Revenues
        'software development', 'software export', 'export of services', 'export software',
        'saas revenue', 'subscription revenue', 'api revenue', 'api usage', 'platform fee',
        'cloud consulting', 'consulting income', 'consultancy income', 'implementation revenue',
        'it services', 'it enabled services', 'ites revenue', 'tech support revenue',
        'annual maintenance contract', 'amc revenue', 'license fee received', 'web development', 'app development',
        # General Sales & Service Incomes
        'sales', 'turnover', 'gross sales', 'domestic sales', 'export sales', 'trading sales',
        'manufacturing sales', 'service income', 'professional fee received', 'job work income',
        'job work receipts', 'gross receipts', 'contract receipts', 'brokerage received', 'commission income'
    ]) and not any(exp in words for exp in ['purchase', 'expense', 'expenses', 'cost', 'payable', 'paid']):
        return ScheduleIIIGroup.REVENUE_OPERATIONS

    # When revenue/income appears in consulting context
    if ('consulting' in name or 'consultancy' in name) and any(inc in words for inc in ['revenue', 'income', 'fee', 'receipts', 'billing']):
        return ScheduleIIIGroup.REVENUE_OPERATIONS

    if any(k in name for k in [
        'interest income', 'interest received', 'interest on fd', 'interest on fixed deposit',
        'interest on savings', 'interest on income tax refund', 'dividend', 'dividend income',
        'discount received', 'cash discount received', 'scrap sales', 'sale of scrap',
        'profit on sale', 'profit on sale of asset', 'profit on sale of investments', 'forex gain',
        'exchange fluctuation gain', 'foreign exchange gain', 'round off', 'rounding off',
        'miscellaneous income', 'bad debt recovered', 'other income'
    ]):
        return ScheduleIIIGroup.OTHER_INCOME

    # -------------------------------------------------------------------------
    # STEP 8: EMPLOYEE BENEFITS EXPENSE
    # All IT allowances, reimbursements, welfare, and statutory contributions
    # -------------------------------------------------------------------------
    is_external_consultant = any(ext in name for ext in [
        'freelance', 'subcontractor', 'consultant fee', 'consultancy fee', 'audit fee', 'director fee', 'professional fee'
    ])
    if not is_external_consultant:
        if any(k in name for k in [
            'basic salary', 'house rent allowance', 'dearness allowance', 'da allowance',
            'special allowance', 'medical allowance', 'conveyance allowance', 'leave travel allowance',
            'uniform allowance', 'shift allowance', 'night shift allowance', 'overtime',
            'overtime allowance', 'on-call allowance', 'variable pay', 'incentive', 'incentives',
            'performance bonus', 'leave encashment', 'notice pay buyout', 'intern stipend', 'stipend',
            'work from home', 'broadband reimbursement', 'internet reimbursement',
            'mobile reimbursement', 'fuel reimbursement', 'food coupons', 'sodexo', 'zeta',
            'meal allowance', 'staff welfare', 'employee welfare', 'pantry', 'office snacks',
            'tea & coffee', 'tea expenses', 'team lunch', 'team outing', 'employee engagement',
            'festival celebration', 'gift to staff', 'swag kit', 'training & certifications',
            'group health insurance', 'group term insurance', 'group term life', 'group mediclaim',
            'mediclaim premium', 'staff insurance', 'employee insurance', 'pf contribution',
            'employer pf', 'epf contribution', 'eps contribution', 'edli contribution',
            'pf admin charges', 'esi contribution', 'employer esi', 'esic contribution',
            'labour welfare fund', 'lwf contribution', 'gratuity expense', 'gratuity provision expense',
            'gratuity paid', 'staff training', 'employee cost', 'employee costs', 'staff cost', 'staff costs',
            'manpower cost', 'manpower expenses', 'personnel expenses', 'personnel cost'
        ]) or (
            ('lta' in words or 'hra' in words or 'wfh' in words) and not has_payable_term
        ) or (
            ('salary' in words or 'salaries' in words or 'wages' in words or 'remuneration' in words) and not has_payable_term
        ) or (
            'bonus' in words and not has_payable_term and 'provision' not in words
        ) or (
            'gratuity' in words and any(e in name for e in ['expense', 'charge', 'cost', 'paid', 'provision']) and not has_payable_term and 'liability' not in name
        ) or (
            'provident fund' in name and not has_payable_term
        ):
            return ScheduleIIIGroup.EMPLOYEE_BENEFITS

    # -------------------------------------------------------------------------
    # STEP 9: OTHER EXPENSES (Cloud, SaaS, Subcontractors, Administrative, Selling)
    # -------------------------------------------------------------------------
    if any(k in name for k in [
        # Subcontractors, Freelancers & Testing
        'sub-contractor', 'subcontractor', 'freelance', 'tech consultancy', 'ui/ux',
        'qa charges', 'testing charges', 'devops consulting', 'penetration testing',
        'security audit', 'vulnerability assessment', 'soc 2 audit', 'iso certification',
        # Legal, Professional & Audit
        'audit fee', 'tax audit', 'statutory audit', 'internal audit', 'legal fee',
        'legal & professional', 'legal expenses', 'advocate fee', 'professional charges',
        'professional fees', 'consultancy charges', 'roc filing fee', 'secretarial fees',
        # Administration, Office, Rent, Utilities
        'rent', 'office rent', 'shop rent', 'godown rent', 'warehouse rent', 'electricity',
        'power charges', 'power & utilities', 'power and utilities', 'utilities', 'power',
        'water', 'water can', 'printing', 'stationery', 'postage',
        'courier', 'telephone', 'mobile', 'internet', 'communication', 'travelling',
        'travel', 'business travel', 'hotel accommodation', 'flight tickets', 'cab charges',
        'conveyance', 'fuel', 'petrol', 'diesel', 'vehicle maintenance', 'vehicle repair',
        'office maintenance', 'repair', 'repairs & maintenance', 'renovation', 'cleaning & sanitation',
        'security service', 'security guard', 'sweeping charges', 'xerox & photocopy',
        'pooja expenses', 'temple expenses',
        # Selling, Marketing & Compliance
        'advertisement', 'marketing', 'digital marketing', 'google ads', 'facebook ads',
        'seo services', 'promotional expenses', 'publicity', 'business promotion',
        'exhibition expenses', 'commission paid', 'brokerage', 'discount allowed',
        'trade discount', 'bad debts', 'sundry balances written off', 'property tax',
        'trade license fee', 'gst late fee', 'gst interest', 'insurance', 'office expenses',
        'general expenses', 'miscellaneous expenses', 'freight outward', 'carriage outward',
        'cartage outward', 'delivery charges'
    ]):
        return ScheduleIIIGroup.OTHER_EXPENSES

    # General fallback based on generic accounting suffixes
    if any(k in words for k in ['expense', 'expenses', 'charges', 'fee', 'fees', 'cost', 'costs', 'loss', 'maintenance']):
        return ScheduleIIIGroup.OTHER_EXPENSES
    elif any(k in words for k in ['income', 'receipt', 'receipts', 'gain', 'discount received']):
        return ScheduleIIIGroup.OTHER_INCOME
    elif any(k in words for k in ['payable', 'due', 'liability']):
        return ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES
    elif any(k in words for k in ['receivable', 'advance', 'deposit', 'refund', 'prepaid']):
        return ScheduleIIIGroup.OTHER_CURRENT_ASSETS

    return ScheduleIIIGroup.UNCLASSIFIED

def get_account_type_for_schedule_group(group: str) -> str:
    if group in [
        ScheduleIIIGroup.PPE, ScheduleIIIGroup.INTANGIBLE, ScheduleIIIGroup.NON_CURRENT_INVESTMENTS,
        ScheduleIIIGroup.TRADE_RECEIVABLES, ScheduleIIIGroup.CASH_EQUIVALENTS, ScheduleIIIGroup.INVENTORIES,
        ScheduleIIIGroup.LONG_TERM_LOANS_ADV, ScheduleIIIGroup.OTHER_CURRENT_ASSETS
    ]:
        return AccountType.ASSET
    elif group in [ScheduleIIIGroup.SHARE_CAPITAL, ScheduleIIIGroup.RESERVES_SURPLUS]:
        return AccountType.EQUITY
    elif group in [
        ScheduleIIIGroup.LONG_TERM_BORROWINGS, ScheduleIIIGroup.TRADE_PAYABLES,
        ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES, ScheduleIIIGroup.SHORT_TERM_PROVISIONS,
        ScheduleIIIGroup.SHORT_TERM_BORROWINGS
    ]:
        return AccountType.LIABILITY
    elif group in [ScheduleIIIGroup.REVENUE_OPERATIONS, ScheduleIIIGroup.OTHER_INCOME]:
        return AccountType.REVENUE
    else:
        return AccountType.EXPENSE


def extract_account_name(row_dict: dict) -> str:
    """
    Deterministically extracts the ledger / account title from a row dict.
    Strictly avoids picking account codes, IDs, types, groups, or numbers as the name.
    """
    # Fast path for direct dictionary keys
    for k in (
        'Particulars', 'particulars', 'Account Name', 'account_name', 'account name',
        'Ledger Name', 'ledger_name', 'ledger name', 'Ledger', 'ledger',
        'Head of Account', 'head of account', 'Head', 'head', 'Particular', 'particular',
        'Party Name', 'party_name', 'party', 'Party', 'A/c Heads', 'a/c heads',
        'Account Description', 'account_description'
    ):
        v = row_dict.get(k)
        if v is not None:
            val_str = str(v).strip()
            if val_str and not val_str.isdigit():
                return val_str

    PRIORITY_KEYS = [
        'account_name', 'account name', 'particulars', 'particular', 'ledger_name', 'ledger name',
        'account description', 'account_description', 'ledger', 'head of account', 'head', 'party_name', 'party name', 'party'
    ]
    for target in PRIORITY_KEYS:
        for k, v in row_dict.items():
            if v and str(v).strip():
                clean_k = str(k).lower().replace('.', '').replace('_', ' ').strip()
                if clean_k == target:
                    val_str = str(v).strip()
                    if not re.match(r'^\d+$', val_str):
                        return val_str

    EXCLUDE_SUBSTRINGS = ['code', 'id', 'number', 'no', 'type', 'group', 'ref', 'source']
    for k, v in row_dict.items():
        if v and str(v).strip():
            clean_k = str(k).lower().replace('.', '').replace('_', ' ').strip()
            if any(term in clean_k for term in ['name', 'particular', 'ledger', 'head', 'account', 'party']):
                if not any(ex in clean_k for ex in EXCLUDE_SUBSTRINGS):
                    val_str = str(v).strip()
                    if not re.match(r'^\d+$', val_str):
                        return val_str

    for k, v in row_dict.items():
        if v and str(v).strip():
            clean_k = str(k).lower().replace('.', '').replace('_', ' ').strip()
            if not any(ex in clean_k for ex in EXCLUDE_SUBSTRINGS + ['debit', 'credit', 'dr', 'cr', 'amount', 'balance', 'date', 'rate', 'total']):
                val_str = str(v).strip()
                if not re.match(r'^-?\d+(\.\d+)?$', val_str):
                    return val_str

    return ""

_CODE_KEYS_SET = {'account_code', 'account code', 'code', 'gl_code', 'ledger_code', 'a/c code', 'acc_code'}

def extract_account_code(row_dict: dict, fallback_idx: int = 1) -> str:
    for k in (
        'Account Code', 'account_code', 'account code', 'Code', 'code',
        'GL Code', 'gl_code', 'Ledger Code', 'ledger_code', 'A/c Code', 'a/c code',
        'Acc Code', 'acc_code'
    ):
        v = row_dict.get(k)
        if v is not None:
            val_str = str(v).strip()
            if val_str:
                return val_str

    for k, v in row_dict.items():
        if v and str(v).strip():
            clean_k = str(k).lower().replace('.', '').replace('_', ' ').strip()
            if clean_k in _CODE_KEYS_SET:
                return str(v).strip()
    return f"{1000 + fallback_idx}"

def extract_debit_credit_amounts(row_dict: dict) -> tuple[Decimal, Decimal]:
    """
    Extracts debit and credit Decimal values from a trial balance row dict.
    Strictly prioritizes Closing balance columns over Opening balance columns.
    """
    dr_val = None
    for k in (
        'Debit', 'debit', 'Debit (INR)', 'debit (inr)',
        'Closing Debit (INR)', 'closing_debit_inr', 'Closing Debit', 'closing_debit',
        'Closing Dr', 'closing_dr',
        'Debit_INR', 'debit_inr', 'Dr. Amt', 'dr. amt', 'Dr', 'dr', 'Dr Amount', 'dr amount'
    ):
        if k in row_dict:
            dr_val = row_dict[k]
            break

    cr_val = None
    for k in (
        'Credit', 'credit', 'Credit (INR)', 'credit (inr)',
        'Closing Credit (INR)', 'closing_credit_inr', 'Closing Credit', 'closing_credit',
        'Closing Cr', 'closing_cr',
        'Credit_INR', 'credit_inr', 'Cr. Amt', 'cr. amt', 'Cr', 'cr', 'Cr Amount', 'cr amount'
    ):
        if k in row_dict:
            cr_val = row_dict[k]
            break

    if dr_val is not None or cr_val is not None:
        dr = parse_indian_amount(dr_val) if dr_val is not None else Decimal('0.00')
        cr = parse_indian_amount(cr_val) if cr_val is not None else Decimal('0.00')
        return dr or Decimal('0.00'), cr or Decimal('0.00')

    CLOSING_DR_KEYS = ['closing_debit_inr', 'closing_debit', 'closing debit', 'closing debit inr', 'closing dr', 'closing balance dr', 'debit closing', 'closing_dr']
    CLOSING_CR_KEYS = ['closing_credit_inr', 'closing_credit', 'closing credit', 'closing credit inr', 'closing cr', 'closing balance cr', 'credit closing', 'closing_cr']

    raw_dr = None
    raw_cr = None

    for k, v in row_dict.items():
        clean_k = str(k).lower().replace('.', '').replace('_', ' ').strip()
        if any(target == clean_k for target in CLOSING_DR_KEYS):
            raw_dr = v
        elif any(target == clean_k for target in CLOSING_CR_KEYS):
            raw_cr = v

    if raw_dr is None:
        STANDARD_DR_KEYS = ['debit (inr)', 'debit_inr', 'debit', 'dr', 'dr amount', 'debit amount', 'withdrawal', 'period_debit_inr', 'period_debit', 'opening_debit_inr', 'opening_debit']
        for target in STANDARD_DR_KEYS:
            for k, v in row_dict.items():
                clean_k = str(k).lower().replace('.', '').replace('_', ' ').strip()
                if clean_k == target:
                    raw_dr = v
                    break
            if raw_dr is not None:
                break

    if raw_cr is None:
        STANDARD_CR_KEYS = ['credit (inr)', 'credit_inr', 'credit', 'cr', 'cr amount', 'credit amount', 'deposit', 'period_credit_inr', 'period_credit', 'opening_credit_inr', 'opening_credit']
        for target in STANDARD_CR_KEYS:
            for k, v in row_dict.items():
                clean_k = str(k).lower().replace('.', '').replace('_', ' ').strip()
                if clean_k == target:
                    raw_cr = v
                    break
            if raw_cr is not None:
                break

    parsed_dr = parse_indian_amount(raw_dr)
    dr = parsed_dr if parsed_dr is not None else Decimal('0.00')

    parsed_cr = parse_indian_amount(raw_cr)
    cr = parsed_cr if parsed_cr is not None else Decimal('0.00')

    return dr, cr

class TrialBalanceService:
    @staticmethod
    def calculate_trial_balance(rows: list[dict], as_of_date=None, engagement=None, document=None):
        """
        Calculates trial balance totals and checks debit-credit equality deterministically.
        Persists ChartOfAccounts, LedgerAccount, and TrialBalanceSnapshot if engagement is provided.
        Fails closed with explicit difference if out of balance.
        """
        total_dr = Decimal('0.00')
        total_cr = Decimal('0.00')
        processed_accounts = []
        coa_map = {}
        ledger_map = {}
        tb_groups = defaultdict(lambda: Decimal('0.00'))

        for idx, r in enumerate(rows, start=1):
            name = extract_account_name(r)
            if not name or name.lower() in ['total', 'totals', 'grand total']:
                continue

            dr, cr = extract_debit_credit_amounts(r)
            code = extract_account_code(r, idx)

            schedule_group = r.get('schedule_iii_group')
            if not schedule_group or schedule_group == ScheduleIIIGroup.UNCLASSIFIED:
                schedule_group = classify_schedule_iii(name)

            total_dr += dr
            total_cr += cr

            net_balance = dr - cr
            bal_type = 'Dr' if net_balance >= 0 else 'Cr'
            processed_accounts.append({
                'account_code': code,
                'account_name': name,
                'debit': str(dr),
                'credit': str(cr),
                'net_balance': str(net_balance),
                'balance_type': bal_type,
                'schedule_iii_group': schedule_group
            })

            a_type = get_account_type_for_schedule_group(schedule_group)
            if a_type in [AccountType.ASSET, AccountType.EXPENSE]:
                tb_groups[schedule_group] += net_balance
            else:
                tb_groups[schedule_group] += (-net_balance)

            if engagement:
                coa_map[code] = {
                    'account_code': code,
                    'account_name': name,
                    'account_type': a_type,
                    'schedule_iii_group': schedule_group,
                }
                ledger_map[name] = {
                    'name': name,
                    'code': code,
                    'closing_balance': abs(net_balance),
                    'closing_balance_type': bal_type,
                }

        diff = total_dr - total_cr
        is_balanced = abs(diff) < Decimal('0.005')
        status = 'BALANCED' if is_balanced else 'UNBALANCED_DIFFERENCE'

        snapshot = None
        if engagement:
            from django.db import transaction
            company = engagement.company
            with transaction.atomic():
                has_existing_coas = ChartOfAccounts.objects.filter(company=company).exists()
                if not has_existing_coas:
                    new_coas = [
                        ChartOfAccounts(
                            company=company,
                            account_code=c_code,
                            account_name=c_data['account_name'],
                            account_type=c_data['account_type'],
                            schedule_iii_group=c_data['schedule_iii_group'],
                        )
                        for c_code, c_data in coa_map.items()
                    ]
                    created_coas = ChartOfAccounts.objects.bulk_create(new_coas, batch_size=2000)
                    coa_id_map = {c.account_code: c.id for c in created_coas}
                    new_ledgers = [
                        LedgerAccount(
                            company=company,
                            name=l_name,
                            code=l_data['code'],
                            coa_id=coa_id_map.get(l_data['code']),
                            closing_balance=l_data['closing_balance'],
                            closing_balance_type=l_data['closing_balance_type'],
                        )
                        for l_name, l_data in ledger_map.items()
                    ]
                    LedgerAccount.objects.bulk_create(new_ledgers, batch_size=2000)
                else:
                    existing_coas = {c.account_code: c for c in ChartOfAccounts.objects.filter(company=company)}
                    new_coas = []
                    update_coas = []
                    coa_id_map = {}
                    for c_code, c_data in coa_map.items():
                        if c_code in existing_coas:
                            coa_obj = existing_coas[c_code]
                            coa_obj.account_name = c_data['account_name']
                            coa_obj.account_type = c_data['account_type']
                            coa_obj.schedule_iii_group = c_data['schedule_iii_group']
                            update_coas.append(coa_obj)
                            coa_id_map[c_code] = coa_obj.id
                        else:
                            new_coas.append(ChartOfAccounts(
                                company=company,
                                account_code=c_code,
                                account_name=c_data['account_name'],
                                account_type=c_data['account_type'],
                                schedule_iii_group=c_data['schedule_iii_group'],
                            ))

                    if new_coas:
                        created_new = ChartOfAccounts.objects.bulk_create(new_coas, batch_size=2000)
                        for c in created_new:
                            coa_id_map[c.account_code] = c.id
                    if update_coas:
                        ChartOfAccounts.objects.bulk_update(update_coas, ['account_name', 'account_type', 'schedule_iii_group'], batch_size=2000)

                    existing_ledgers = {l.name: l for l in LedgerAccount.objects.filter(company=company)}
                    new_ledgers = []
                    update_ledgers = []
                    for l_name, l_data in ledger_map.items():
                        cid = coa_id_map.get(l_data['code'])
                        if l_name in existing_ledgers:
                            l_obj = existing_ledgers[l_name]
                            l_obj.code = l_data['code']
                            l_obj.coa_id = cid
                            l_obj.closing_balance = l_data['closing_balance']
                            l_obj.closing_balance_type = l_data['closing_balance_type']
                            update_ledgers.append(l_obj)
                        else:
                            new_ledgers.append(LedgerAccount(
                                company=company,
                                name=l_name,
                                code=l_data['code'],
                                coa_id=cid,
                                closing_balance=l_data['closing_balance'],
                                closing_balance_type=l_data['closing_balance_type'],
                            ))

                    if new_ledgers:
                        LedgerAccount.objects.bulk_create(new_ledgers, batch_size=2000)
                    if update_ledgers:
                        LedgerAccount.objects.bulk_update(update_ledgers, ['code', 'coa_id', 'closing_balance', 'closing_balance_type'], batch_size=2000)

                payload_snapshot = processed_accounts[:5000] if len(processed_accounts) > 5000 else processed_accounts
                snapshot = TrialBalanceSnapshot.objects.create(
                    engagement=engagement,
                    document=document,
                    as_of_date=as_of_date or datetime.today().date(),
                    total_debits=total_dr,
                    total_credits=total_cr,
                    difference_amount=diff,
                    is_balanced=is_balanced,
                    status=status,
                    accounts_snapshot=payload_snapshot
                )

            # If unbalanced, raise a CRITICAL ExceptionItem under SA 500 / SA 700
            if not is_balanced:
                from apps.audit.models import ExceptionItem, ExceptionSeverity, ExceptionStatus
                ExceptionItem.objects.create(
                    engagement=engagement,
                    rule_code="RULE_TB_UNBALANCED",
                    title=f"Unbalanced Trial Balance: Variance of ₹{abs(diff):,.2f}",
                    category="ACCURACY",
                    severity=ExceptionSeverity.CRITICAL,
                    amount_involved=abs(diff),
                    explanation=(
                        f"The trial balance extracted from '{document.original_filename if document else 'source'}' "
                        f"does not balance. Total Debits: ₹{total_dr:,.2f}, Total Credits: ₹{total_cr:,.2f}. "
                        f"Difference of ₹{diff:,.2f} violates double-entry balancing rules."
                    ),
                    recommended_action=(
                        "Investigate ledger extraction omissions, unposted vouchers, or transposition errors. "
                        "Fail-closed policy: Do not finalize audit opinion or fabricate balancing entries."
                    ),
                    source_reference=document.original_filename if document else "TB_Upload",
                    status=ExceptionStatus.OPEN
                )

        # 1. Full Cross-Check: Trial Balance vs Schedule III Balance Sheet Equilibrium
        fs_comp = TrialBalanceService.compile_financial_statements(processed_accounts, precomputed_groups=tb_groups)
        bs_assets = Decimal(fs_comp['balance_sheet']['total_assets'])
        bs_eq_liab = Decimal(fs_comp['balance_sheet']['total_equity_and_liabilities'])
        bs_variance = abs(bs_assets - bs_eq_liab)
        bs_is_balanced = bs_variance < Decimal('1.00')

        if engagement and not bs_is_balanced:
            from apps.audit.models import ExceptionItem, ExceptionSeverity, ExceptionStatus
            ExceptionItem.objects.create(
                engagement=engagement,
                rule_code="RULE_BS_EQUILIBRIUM_VARIANCE",
                title=f"Balance Sheet Out of Equilibrium: Variance of ₹{bs_variance:,.2f}",
                category="ACCURACY",
                severity=ExceptionSeverity.CRITICAL,
                amount_involved=bs_variance,
                explanation=(
                    f"Schedule III Balance Sheet equation does not balance. Total Assets (₹{bs_assets:,.2f}) "
                    f"does not equal Total Equity & Liabilities (₹{bs_eq_liab:,.2f}). Variance: ₹{bs_variance:,.2f}."
                ),
                recommended_action=(
                    "Reconcile unmapped ledger classifications, closing stock valuation, or reserves movement."
                ),
                source_reference=document.original_filename if document else "Financial_Statements_Compilation",
                status=ExceptionStatus.OPEN
            )

        return {
            'total_debits': str(total_dr),
            'total_credits': str(total_cr),
            'difference_amount': str(diff),
            'is_balanced': is_balanced,
            'status': status,
            'balance_sheet_cross_check': {
                'total_assets': str(bs_assets),
                'total_equity_and_liabilities': str(bs_eq_liab),
                'variance': str(bs_variance),
                'is_balanced': bs_is_balanced,
                'status': 'BALANCED' if bs_is_balanced else 'VARIANCE_DETECTED'
            },
            'accounts': processed_accounts,
            'snapshot_id': snapshot.id if snapshot else None
        }

    process_trial_balance = calculate_trial_balance

    @staticmethod
    def compile_financial_statements(accounts: list[dict], precomputed_groups: dict = None) -> dict:
        """
        Compiles the formal Schedule III Balance Sheet and Statement of Profit and Loss
        from line-by-line Trial Balance accounts according to Companies Act 2013 Division I rules.
        """
        if precomputed_groups is not None:
            groups = defaultdict(lambda: Decimal('0.00'), precomputed_groups)
        else:
            groups = defaultdict(lambda: Decimal('0.00'))
            for acc in accounts:
                grp = acc.get('schedule_iii_group')
                if not grp or grp == ScheduleIIIGroup.UNCLASSIFIED:
                    name = acc.get('account_name') or acc.get('Particulars') or extract_account_name(acc)
                    if not name or name.lower() in ['total', 'totals', 'grand total']:
                        continue
                    grp = classify_schedule_iii(name)

                if 'debit' in acc and 'credit' in acc:
                    dr_v = acc['debit']
                    cr_v = acc['credit']
                    dr = dr_v if isinstance(dr_v, Decimal) else Decimal(str(dr_v))
                    cr = cr_v if isinstance(cr_v, Decimal) else Decimal(str(cr_v))
                else:
                    dr, cr = extract_debit_credit_amounts(acc)
                
                a_type = get_account_type_for_schedule_group(grp)
                if a_type in [AccountType.ASSET, AccountType.EXPENSE]:
                    groups[grp] += (dr - cr)
                else:
                    groups[grp] += (cr - dr)

        # Absorb any unclassified accounts into other expenses/income so TB balance is preserved
        unclass = groups[ScheduleIIIGroup.UNCLASSIFIED]
        if unclass > Decimal('0.00'):
            groups[ScheduleIIIGroup.OTHER_EXPENSES] += unclass
        elif unclass < Decimal('0.00'):
            groups[ScheduleIIIGroup.OTHER_INCOME] += abs(unclass)
        groups[ScheduleIIIGroup.UNCLASSIFIED] = Decimal('0.00')

        # Subledger GAAP Reclassifications for Schedule III presentation:
        # Bank Overdraft (Negative Cash & Bank -> Short-Term Borrowings)
        if groups[ScheduleIIIGroup.CASH_EQUIVALENTS] < Decimal('0.00'):
            groups[ScheduleIIIGroup.SHORT_TERM_BORROWINGS] += abs(groups[ScheduleIIIGroup.CASH_EQUIVALENTS])
            groups[ScheduleIIIGroup.CASH_EQUIVALENTS] = Decimal('0.00')

        # Advance to Vendors (Debit balance in Trade Payables -> Other Current Assets)
        if groups[ScheduleIIIGroup.TRADE_PAYABLES] < Decimal('0.00'):
            groups[ScheduleIIIGroup.OTHER_CURRENT_ASSETS] += abs(groups[ScheduleIIIGroup.TRADE_PAYABLES])
            groups[ScheduleIIIGroup.TRADE_PAYABLES] = Decimal('0.00')

        # Advance from Customers (Credit balance in Trade Receivables -> Other Current Liabilities)
        if groups[ScheduleIIIGroup.TRADE_RECEIVABLES] < Decimal('0.00'):
            groups[ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES] += abs(groups[ScheduleIIIGroup.TRADE_RECEIVABLES])
            groups[ScheduleIIIGroup.TRADE_RECEIVABLES] = Decimal('0.00')

        # 1. Statement of Profit and Loss
        rev_ops = max(Decimal('0.00'), groups[ScheduleIIIGroup.REVENUE_OPERATIONS])
        oth_inc = max(Decimal('0.00'), groups[ScheduleIIIGroup.OTHER_INCOME])
        tot_rev = rev_ops + oth_inc

        c_mat = max(Decimal('0.00'), groups[ScheduleIIIGroup.COST_OF_MATERIALS])
        emp_exp = max(Decimal('0.00'), groups[ScheduleIIIGroup.EMPLOYEE_BENEFITS])
        fin_cost = max(Decimal('0.00'), groups[ScheduleIIIGroup.FINANCE_COSTS])
        depn = max(Decimal('0.00'), groups[ScheduleIIIGroup.DEPRECIATION_AMORT])
        oth_exp = max(Decimal('0.00'), groups[ScheduleIIIGroup.OTHER_EXPENSES])
        tot_exp = c_mat + emp_exp + fin_cost + depn + oth_exp

        pbt = tot_rev - tot_exp
        tax_prov = (pbt * Decimal('0.25')).quantize(Decimal('0.01')) if pbt > Decimal('0.00') else Decimal('0.00')
        pat = pbt - tax_prov

        # 2. Balance Sheet - Equity & Liabilities
        share_cap = max(Decimal('0.00'), groups[ScheduleIIIGroup.SHARE_CAPITAL])
        # Reserves & Surplus can be negative in case of accumulated losses / drawings
        reserves = groups[ScheduleIIIGroup.RESERVES_SURPLUS] + pat
        shareholders_funds = share_cap + reserves

        lt_borrowings = max(Decimal('0.00'), groups[ScheduleIIIGroup.LONG_TERM_BORROWINGS])
        dt_liab = max(Decimal('0.00'), groups[ScheduleIIIGroup.DEFERRED_TAX_LIABILITY])
        lt_prov = max(Decimal('0.00'), groups[ScheduleIIIGroup.LONG_TERM_PROVISIONS])
        non_current_liabilities = lt_borrowings + dt_liab + lt_prov

        st_borrowings = max(Decimal('0.00'), groups[ScheduleIIIGroup.SHORT_TERM_BORROWINGS])
        trade_payables = max(Decimal('0.00'), groups[ScheduleIIIGroup.TRADE_PAYABLES])
        oth_cur_liab = max(Decimal('0.00'), groups[ScheduleIIIGroup.OTHER_CURRENT_LIABILITIES])
        st_prov = max(Decimal('0.00'), groups[ScheduleIIIGroup.SHORT_TERM_PROVISIONS]) + tax_prov
        current_liabilities = st_borrowings + trade_payables + oth_cur_liab + st_prov

        total_equity_and_liabilities = shareholders_funds + non_current_liabilities + current_liabilities

        # 3. Balance Sheet - Assets
        ppe = max(Decimal('0.00'), groups[ScheduleIIIGroup.PPE])
        intangible = max(Decimal('0.00'), groups[ScheduleIIIGroup.INTANGIBLE])
        nc_invest = max(Decimal('0.00'), groups[ScheduleIIIGroup.NON_CURRENT_INVESTMENTS])
        dt_asset = max(Decimal('0.00'), groups[ScheduleIIIGroup.DEFERRED_TAX_ASSET])
        lt_loans = max(Decimal('0.00'), groups[ScheduleIIIGroup.LONG_TERM_LOANS_ADV])
        non_current_assets = ppe + intangible + nc_invest + dt_asset + lt_loans

        inventories = max(Decimal('0.00'), groups[ScheduleIIIGroup.INVENTORIES])
        trade_rec = max(Decimal('0.00'), groups[ScheduleIIIGroup.TRADE_RECEIVABLES])
        cash_eq = max(Decimal('0.00'), groups[ScheduleIIIGroup.CASH_EQUIVALENTS])
        st_loans = max(Decimal('0.00'), groups[ScheduleIIIGroup.SHORT_TERM_LOANS])
        oth_cur_assets = max(Decimal('0.00'), groups[ScheduleIIIGroup.OTHER_CURRENT_ASSETS])
        current_assets = inventories + trade_rec + cash_eq + st_loans + oth_cur_assets

        total_assets = non_current_assets + current_assets

        bs_diff = abs(total_equity_and_liabilities - total_assets)
        is_balanced = bs_diff < Decimal('1.00')

        # 4. Mandatory Statutory Schedule III Analytical Ratios & Operating Cycle Formulas
        # Handled with complete Division I & II statutory definitions and zero-division safeguards
        cur_ratio = round(float(current_assets / current_liabilities), 2) if current_liabilities > 0 else 0.0
        quick_ratio = round(float((current_assets - inventories) / current_liabilities), 2) if current_liabilities > 0 else 0.0
        cash_ratio = round(float(cash_eq / current_liabilities), 2) if current_liabilities > 0 else 0.0
        
        total_debt = lt_borrowings + st_borrowings
        debt_equity = round(float(total_debt / shareholders_funds), 2) if shareholders_funds > 0 else (0.0 if total_debt == 0 else 999.0)
        
        debt_service_due = fin_cost + st_borrowings
        dscr = round(float((pat + depn + fin_cost) / debt_service_due), 2) if debt_service_due > 0 else (999.0 if (pat + depn) > 0 else 0.0)
        
        roe = round(float(pat / shareholders_funds * 100), 2) if shareholders_funds > 0 else 0.0
        inv_turnover = round(float(c_mat / inventories), 2) if (inventories > 0 and c_mat > 0) else 0.0
        debtors_turnover = round(float(rev_ops / trade_rec), 2) if (trade_rec > 0 and rev_ops > 0) else 0.0
        
        net_purchases_and_expenses = c_mat + oth_exp
        creditors_turnover = round(float(net_purchases_and_expenses / trade_payables), 2) if (trade_payables > 0 and net_purchases_and_expenses > 0) else 0.0
        
        working_capital = current_assets - current_liabilities
        working_cap_turnover = round(float(rev_ops / working_capital), 2) if (working_capital > 0 and rev_ops > 0) else 0.0
        
        npm = round(float(pat / rev_ops * 100), 2) if rev_ops > 0 else 0.0
        
        ebit = pbt + fin_cost
        capital_employed = shareholders_funds + lt_borrowings
        roce = round(float(ebit / capital_employed * 100), 2) if capital_employed > 0 else 0.0
        
        roi = round(float(oth_inc / nc_invest * 100), 2) if nc_invest > 0 else 0.0
        
        ebitda = pbt + fin_cost + depn
        op_margin = round(float(ebitda / rev_ops * 100), 2) if rev_ops > 0 else 0.0
        gp_margin = round(float((rev_ops - c_mat) / rev_ops * 100), 2) if rev_ops > 0 else 0.0
        icr = round(float(ebit / fin_cost), 2) if fin_cost > 0 else (999.0 if ebit > 0 else 0.0)
        
        debtors_days = round(float((trade_rec / rev_ops) * 365), 1) if rev_ops > 0 else 0.0
        creditors_days = round(float((trade_payables / net_purchases_and_expenses) * 365), 1) if net_purchases_and_expenses > 0 else 0.0
        inventory_days = round(float((inventories / c_mat) * 365), 1) if c_mat > 0 else 0.0
        operating_cycle_days = round(inventory_days + debtors_days - creditors_days, 1)

        return {
            'balance_sheet': {
                'total_equity_and_liabilities': str(total_equity_and_liabilities),
                'total_assets': str(total_assets),
                'equity_and_liabilities': {
                    'shareholders_funds': {
                        'share_capital': str(share_cap),
                        'reserves_and_surplus': str(reserves),
                        'total': str(shareholders_funds)
                    },
                    'non_current_liabilities': {
                        'long_term_borrowings': str(lt_borrowings),
                        'deferred_tax_liabilities': str(dt_liab),
                        'long_term_provisions': str(lt_prov),
                        'total': str(non_current_liabilities)
                    },
                    'current_liabilities': {
                        'short_term_borrowings': str(st_borrowings),
                        'trade_payables': str(trade_payables),
                        'other_current_liabilities': str(oth_cur_liab),
                        'short_term_provisions': str(st_prov),
                        'total': str(current_liabilities)
                    },
                    'total_equity_and_liabilities': str(total_equity_and_liabilities)
                },
                'assets': {
                    'non_current_assets': {
                        'property_plant_and_equipment': str(ppe),
                        'property_plant_equipment': str(ppe),
                        'intangible_assets': str(intangible),
                        'non_current_investments': str(nc_invest),
                        'deferred_tax_assets': str(dt_asset),
                        'long_term_loans_and_advances': str(lt_loans),
                        'total': str(non_current_assets)
                    },
                    'current_assets': {
                        'inventories': str(inventories),
                        'trade_receivables': str(trade_rec),
                        'cash_and_cash_equivalents': str(cash_eq),
                        'short_term_loans_and_advances': str(st_loans),
                        'other_current_assets': str(oth_cur_assets),
                        'total': str(current_assets)
                    },
                    'total_assets': str(total_assets)
                },
                'is_balanced': is_balanced,
                'difference': str(bs_diff)
            },
            'profit_and_loss': {
                'revenue_from_operations': str(rev_ops),
                'other_income': str(oth_inc),
                'total_revenue': str(tot_rev),
                'revenue': {
                    'revenue_from_operations': str(rev_ops),
                    'other_income': str(oth_inc),
                    'total_revenue': str(tot_rev)
                },
                'expenses': {
                    'cost_of_materials_consumed': str(c_mat),
                    'employee_benefits_expense': str(emp_exp),
                    'finance_costs': str(fin_cost),
                    'depreciation_and_amortization': str(depn),
                    'depreciation_amortization': str(depn),
                    'other_expenses': str(oth_exp),
                    'total_expenses': str(tot_exp)
                },
                'profit_before_tax': str(pbt),
                'pbt': str(pbt),
                'tax_expense': str(tax_prov),
                'tax_provision': str(tax_prov),
                'profit_after_tax': str(pat),
                'pat': str(pat)
            },
            'ratios': {
                # 11 Schedule III Mandated Analytical Ratios:
                'current_ratio': cur_ratio,
                'debt_equity': debt_equity,
                'debt_equity_ratio': debt_equity,
                'debt_service_coverage_ratio': dscr,
                'dscr': dscr,
                'return_on_equity': roe,
                'roe_pct': roe,
                'inventory_turnover_ratio': inv_turnover,
                'inventory_turnover': inv_turnover,
                'trade_receivables_turnover_ratio': debtors_turnover,
                'debtors_turnover': debtors_turnover,
                'trade_payables_turnover_ratio': creditors_turnover,
                'creditors_turnover': creditors_turnover,
                'net_capital_turnover_ratio': working_cap_turnover,
                'working_capital_turnover': working_cap_turnover,
                'net_profit_margin_pct': npm,
                'npm': npm,
                'roce_pct': roce,
                'roce': roce,
                'return_on_investment': roi,
                'roi_pct': roi,

                # Core Liquidity, Solvency & Operating Metrics:
                'quick_ratio': quick_ratio,
                'cash_ratio': cash_ratio,
                'operating_margin_pct': op_margin,
                'gross_profit_margin_pct': gp_margin,
                'interest_coverage_ratio': icr,
                'icr': icr,
                'debtors_collection_period_days': debtors_days,
                'creditors_payment_period_days': creditors_days,
                'inventory_holding_period_days': inventory_days,
                'operating_cycle_days': operating_cycle_days
            }
        }

    @staticmethod
    def get_movement_analysis(engagement):
        """
        Computes comprehensive account movements for every ledger account:
        Opening balance, total period debits, total period credits, net movement,
        closing balance, and roll-forward verification status.
        """
        company = engagement.company
        ledgers = LedgerAccount.objects.filter(company=company).select_related('coa')
        
        movements = []
        grand_opening_dr = Decimal('0.00')
        grand_opening_cr = Decimal('0.00')
        grand_period_dr = Decimal('0.00')
        grand_period_cr = Decimal('0.00')
        grand_closing_dr = Decimal('0.00')
        grand_closing_cr = Decimal('0.00')

        for l in ledgers:
            txns = Transaction.objects.filter(engagement=engagement, ledger_account=l)
            tot_dr = sum((t.debit_amount for t in txns), Decimal('0.00'))
            tot_cr = sum((t.credit_amount for t in txns), Decimal('0.00'))

            op = l.opening_balance
            op_net = op if l.opening_balance_type == 'Dr' else -op
            expected_net = op_net + tot_dr - tot_cr
            actual_net = l.closing_balance if l.closing_balance_type == 'Dr' else -l.closing_balance

            is_rollforward_valid = abs(expected_net - actual_net) < Decimal('0.01')
            net_movement = tot_dr - tot_cr

            sch_grp = l.coa.schedule_iii_group if l.coa else ScheduleIIIGroup.UNCLASSIFIED
            is_suspense = l.is_suspense or sch_grp == ScheduleIIIGroup.UNCLASSIFIED

            # Aggregate grand totals
            if l.opening_balance_type == 'Dr':
                grand_opening_dr += l.opening_balance
            else:
                grand_opening_cr += l.opening_balance

            grand_period_dr += tot_dr
            grand_period_cr += tot_cr

            if l.closing_balance_type == 'Dr':
                grand_closing_dr += l.closing_balance
            else:
                grand_closing_cr += l.closing_balance

            movements.append({
                'account_id': l.id,
                'account_code': l.code or (l.coa.account_code if l.coa else ''),
                'account_name': l.name,
                'schedule_iii_group': sch_grp,
                'is_suspense': is_suspense,
                'is_reconciled': l.is_reconciled,
                'opening_balance': str(l.opening_balance),
                'opening_balance_type': l.opening_balance_type,
                'period_debits': str(tot_dr),
                'period_credits': str(tot_cr),
                'net_movement': str(net_movement),
                'closing_balance': str(l.closing_balance),
                'closing_balance_type': l.closing_balance_type,
                'is_rollforward_valid': is_rollforward_valid,
                'rollforward_variance': str(abs(expected_net - actual_net))
            })

        return {
            'engagement_id': engagement.id,
            'company_name': company.name,
            'financial_year': engagement.financial_year.label,
            'total_accounts': len(movements),
            'grand_opening_debits': str(grand_opening_dr),
            'grand_opening_credits': str(grand_opening_cr),
            'grand_period_debits': str(grand_period_dr),
            'grand_period_credits': str(grand_period_cr),
            'grand_closing_debits': str(grand_closing_dr),
            'grand_closing_credits': str(grand_closing_cr),
            'accounts': movements
        }


class GeneralLedgerScrutinyService:
    @staticmethod
    def import_and_scrutinize(engagement, document, extracted_objs: list):
        """
        Parses vouchers from extracted general ledger records, creates Transaction records,
        and triggers forensic scrutiny and audit procedures.
        """
        # Delete any previous transactions from this document to support safe retries
        Transaction.objects.filter(engagement=engagement, document=document).delete()

        # Pre-cache existing ledger accounts to eliminate N database queries
        ledgers_by_name = {l.name.lower(): l for l in LedgerAccount.objects.filter(company=engagement.company)}
        ledgers_by_code = {str(l.code).strip(): l for l in LedgerAccount.objects.filter(company=engagement.company) if l.code}

        created_txns = []
        for obj in extracted_objs:
            raw = obj.raw_data or {}
            norm = obj.normalized_data or {}
            data = {**raw, **norm}

            # Locate date
            date_val = None
            for k in ['Posting_Date', 'posting_date', 'Posting Date', 'date', 'Date', 'txn date', 'Txn Date', 'voucher date', 'Voucher Date', 'Vch Date']:
                val = data.get(k)
                if val:
                    val_str = str(val).split()[0].strip()
                    for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d']:
                        try:
                            date_val = datetime.strptime(val_str, fmt).date()
                            break
                        except (ValueError, TypeError):
                            pass
                    if date_val:
                        break

            if not date_val:
                date_val = engagement.financial_year.end_date

            vch_num = 'JV-001'
            for k in ['Voucher_No', 'voucher_no', 'Voucher No', 'voucher no', 'Document_Ref', 'document_ref', 'vch no', 'Ref No', 'Invoice No', 'Bill No']:
                if k in data and data[k]:
                    vch_num = str(data[k]).strip()
                    break

            account_name = ''
            for k in ['Account_Name', 'account_name', 'Account Name', 'particulars', 'Particulars', 'ledger', 'Ledger', 'account', 'Account']:
                if k in data and data[k]:
                    account_name = str(data[k]).strip()
                    break

            acc_code = ''
            for k in ['Account_Code', 'account_code', 'Account Code', 'code', 'Code']:
                if k in data and data[k]:
                    acc_code = str(data[k]).strip()
                    break

            counterparty = ''
            for k in ['Counterparty', 'counterparty', 'party', 'Party', 'party name', 'Party Name', 'vendor', 'supplier', 'customer']:
                if k in data and data[k]:
                    counterparty = str(data[k]).strip()
                    break

            narration = ''
            for k in ['Narration', 'narration', 'description', 'Description', 'Remarks', 'remarks']:
                if k in data and data[k]:
                    narration = str(data[k]).strip()
                    break

            def _parse_dec(val):
                if val is None:
                    return Decimal('0.00')
                clean = str(val).replace(',', '').replace('₹', '').replace(' ', '').strip()
                try:
                    return Decimal(clean) if clean else Decimal('0.00')
                except Exception:
                    return Decimal('0.00')

            dr = Decimal('0.00')
            cr = Decimal('0.00')
            for k in ['Debit_INR', 'debit_inr', 'Debit (INR)', 'debit', 'Debit', 'dr', 'Dr', 'debit_amount', 'Withdrawal']:
                if k in data and data[k] is not None:
                    d = _parse_dec(data[k])
                    if d > Decimal('0.00'):
                        dr = d
                        break

            for k in ['Credit_INR', 'credit_inr', 'Credit (INR)', 'credit', 'Credit', 'cr', 'Cr', 'credit_amount', 'Deposit']:
                if k in data and data[k] is not None:
                    c = _parse_dec(data[k])
                    if c > Decimal('0.00'):
                        cr = c
                        break

            # Skip header lines or zero amount records
            if dr == 0 and cr == 0:
                continue

            # Match or create LedgerAccount
            ledger = None
            if acc_code and acc_code in ledgers_by_code:
                ledger = ledgers_by_code[acc_code]
            elif account_name and account_name.lower() in ledgers_by_name:
                ledger = ledgers_by_name[account_name.lower()]
            else:
                if not account_name:
                    account_name = f"Account {acc_code}" if acc_code else "General Operating Expenses"
                ledger, _ = LedgerAccount.objects.get_or_create(
                    company=engagement.company,
                    name=account_name,
                    defaults={'code': acc_code, 'closing_balance': dr if dr > 0 else cr}
                )
                ledgers_by_name[account_name.lower()] = ledger
                if acc_code:
                    ledgers_by_code[acc_code] = ledger

            vch_type = VoucherType.PAYMENT if dr > 0 and 'cash' in account_name.lower() else VoucherType.JOURNAL
            if 'sales' in account_name.lower() or 'revenue' in account_name.lower():
                vch_type = VoucherType.SALES
            elif 'purchase' in account_name.lower():
                vch_type = VoucherType.PURCHASE

            txn = Transaction(
                engagement=engagement,
                document=document,
                ledger_account=ledger,
                voucher_number=vch_num,
                voucher_type=vch_type,
                date=date_val,
                counterparty=counterparty,
                narration=narration,
                debit_amount=dr,
                credit_amount=cr,
                source_reference=obj.source_location
            )
            created_txns.append(txn)

        if created_txns:
            created_txns = Transaction.objects.bulk_create(created_txns)
            GeneralLedgerScrutinyService.scrutinize_transactions(created_txns)

            # Comprehensive Financial Data Validation Engine
            from apps.accounting.validation import FinancialDataValidationService
            FinancialDataValidationService.validate_reporting_periods(engagement, created_txns)
            FinancialDataValidationService.validate_amounts_and_debit_credit(created_txns)
            FinancialDataValidationService.detect_duplicate_candidates(engagement, created_txns)
            FinancialDataValidationService.validate_account_mappings(engagement.company, engagement)
            FinancialDataValidationService.validate_abnormal_account_balances(engagement)

            from apps.audit.services import AuditProcedureRunner
            AuditProcedureRunner.run_all_procedures(engagement)

        return created_txns

    @staticmethod
    def scrutinize_transactions(transactions: list[Transaction]):
        """
        Executes comprehensive audit scrutiny over general ledger transactions:
        1. Round amounts
        2. Section 40A(3) cash expense limit > ₹10,000
        3. Weekend postings
        4. Empty or suspicious narrations
        5. Sequence gaps in voucher numbers
        6. Benford's Law distribution of amounts
        """
        flagged_transactions = []
        first_digits = defaultdict(int)
        total_valid_digits = 0
        voucher_sequences = defaultdict(list)

        for txn in transactions:
            flags = []
            amt = txn.debit_amount if txn.debit_amount > 0 else txn.credit_amount

            # 1. Round amount test (multiples of 10,000, 50,000, 1,00,000)
            if amt > Decimal('10000.00') and (amt % Decimal('10000.00')) == Decimal('0.00'):
                flags.append("ROUND_AMOUNT")

            # 2. Section 40A(3) Cash limit check (> ₹10,000 in cash payment)
            is_cash_voucher = 'cash' in txn.ledger_account.name.lower() or 'cash' in (txn.counterparty or '').lower()
            if is_cash_voucher and amt > Decimal('10000.00'):
                flags.append("SECTION_40A3_CASH_LIMIT_EXCEEDED")

            # 3. Weekend posting test (Saturday = 5, Sunday = 6)
            if txn.date.weekday() in [5, 6]:
                flags.append("WEEKEND_POSTING")

            # 4. Unusual or empty narration
            narration_clean = (txn.narration or '').strip().lower()
            if not narration_clean:
                flags.append("MISSING_NARRATION")
            elif any(term in narration_clean for term in ['rectify', 'adjust', 'dummy', 'temp', 'round off']):
                flags.append("SUSPICIOUS_NARRATION")

            # 5. Extract first significant digit for Benford's Law
            if amt > Decimal('0.00'):
                s_amt = str(amt).replace('.', '').lstrip('0')
                if s_amt:
                    digit = int(s_amt[0])
                    if 1 <= digit <= 9:
                        first_digits[digit] += 1
                        total_valid_digits += 1

            # 6. Voucher sequence collection
            v_num = txn.voucher_number
            digits_in_v = ''.join(c for c in v_num if c.isdigit())
            prefix_in_v = ''.join(c for c in v_num if not c.isdigit())
            if digits_in_v:
                try:
                    voucher_sequences[prefix_in_v].append(int(digits_in_v))
                except ValueError:
                    pass

            if flags:
                txn.is_unusual = True
                txn.risk_flags = flags
                txn.save(update_fields=['is_unusual', 'risk_flags'])
                flagged_transactions.append({
                    'id': txn.id,
                    'voucher_number': txn.voucher_number,
                    'date': txn.date.isoformat(),
                    'account': txn.ledger_account.name,
                    'amount': str(amt),
                    'risk_flags': flags,
                    'narration': txn.narration
                })

        # Calculate Benford's Law statistics
        benford_analysis = {}
        chi_square_stat = 0.0
        for d in range(1, 10):
            obs_count = first_digits[d]
            obs_pct = (obs_count / total_valid_digits) if total_valid_digits > 0 else 0.0
            exp_pct = BENFORD_EXPECTED[d]
            exp_count = exp_pct * total_valid_digits

            if exp_count > 0:
                chi_square_stat += ((obs_count - exp_count) ** 2) / exp_count

            benford_analysis[d] = {
                'digit': d,
                'observed_count': obs_count,
                'observed_pct': round(obs_pct * 100, 2),
                'expected_pct': round(exp_pct * 100, 2),
                'deviation': round((obs_pct - exp_pct) * 100, 2)
            }

        # Sequence gap detection
        sequence_gaps = []
        for prefix, nums in voucher_sequences.items():
            sorted_nums = sorted(set(nums))
            if len(sorted_nums) > 1:
                for idx in range(len(sorted_nums) - 1):
                    current_num = sorted_nums[idx]
                    next_num = sorted_nums[idx + 1]
                    if next_num - current_num > 1:
                        missing_range = list(range(current_num + 1, min(next_num, current_num + 20)))
                        sequence_gaps.append({
                            'series_prefix': prefix,
                            'gap_start': current_num,
                            'gap_end': next_num,
                            'missing_count': next_num - current_num - 1,
                            'sample_missing': [f"{prefix}{m}" for m in missing_range[:5]]
                        })

        return {
            'total_scrutinized': len(transactions),
            'flagged_count': len(flagged_transactions),
            'flagged_transactions': flagged_transactions,
            'benford_analysis': list(benford_analysis.values()),
            'benford_chi_square': round(chi_square_stat, 2),
            'benford_conformity': 'ACCEPTABLE' if chi_square_stat < 15.5 else 'SUSPICIOUS_ANOMALIES_DETECTED',
            'sequence_gaps': sequence_gaps
        }
