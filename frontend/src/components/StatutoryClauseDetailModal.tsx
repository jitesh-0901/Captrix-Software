import React, { useState } from 'react';
import {
  X,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Scale,
  Building2,
  Calendar,
  DollarSign,
  Save,
  CheckSquare,
  FileSpreadsheet,
  Info,
  ExternalLink,
  Layers,
  BookOpen
} from 'lucide-react';
import { StatutoryClauseAuditRecord } from '../types';
import { api } from '../services/api';

interface Props {
  clause: StatutoryClauseAuditRecord | null;
  companyName?: string;
  financialYear?: string;
  onClose: () => void;
  onSave?: (updated: StatutoryClauseAuditRecord) => void;
}

interface ClauseStatutoryMeta {
  title: string;
  legalRef: string;
  wpRef: string;
  subClauses: Array<{ code: string; label: string; details: string }>;
  auditProcedures: string[];
  sampleDraft: string;
  evidenceSource: string;
  groundedAttributes: Array<{ label: string; value: string }>;
}

const CARO_METADATA_REGISTRY: Record<string, ClauseStatutoryMeta> = {
  'Clause 3(i)': {
    title: 'Property, Plant and Equipment & Intangibles',
    legalRef: "Companies Act 2013, Section 143(11) & CARO 2020 Order S.O. 849(E) Clause 3(i)",
    wpRef: 'WP-CARO-01 / FAR-SCH-II',
    subClauses: [
      {
        code: '(a)(A)',
        label: 'PPE Register & Quantitative Records',
        details: 'Whether the company is maintaining proper records showing full particulars, including quantitative details and situation of Property, Plant and Equipment.'
      },
      {
        code: '(a)(B)',
        label: 'Intangibles Register',
        details: 'Whether the company is maintaining proper records showing full particulars of intangible assets.'
      },
      {
        code: '(b)',
        label: 'Management Physical Verification',
        details: 'Whether PPE have been physically verified by management at reasonable intervals; whether any material discrepancies noticed were properly addressed in books.'
      },
      {
        code: '(c)',
        label: 'Title Deeds in Company Name',
        details: 'Whether title deeds of all immovable properties (other than properties where the company is lessee) disclosed in financial statements are held in company name.'
      },
      {
        code: '(d)',
        label: 'Asset Revaluation by Registered Valuer',
        details: 'Whether the company has revalued PPE (including ROU assets) or intangibles during the year, and if based on valuation by a Registered Valuer under Section 247.'
      },
      {
        code: '(e)',
        label: 'Benami Property Proceedings',
        details: 'Whether any proceedings have been initiated or are pending against the company for holding any benami property under Benami Transactions (Prohibition) Act, 1988.'
      }
    ],
    auditProcedures: [
      'Verified Fixed Asset Register (FAR) balances with General Ledger and Schedule III Gross Block.',
      'Inspected physical verification certificates and management rotational inventory schedule.',
      'Examined title deeds, conveyance deeds, and encumbrance certificates for freehold land and buildings.',
      'Verified dual depreciation computation under Schedule II (Companies Act) and Section 32 (Income Tax Act).'
    ],
    sampleDraft:
      'In our opinion and according to the information and explanations given to us, the Company has maintained proper records showing full particulars, including quantitative details and situation of Property, Plant and Equipment. The Property, Plant and Equipment were physically verified by the management in accordance with a regular programme of verification which, in our opinion, provides for verification at reasonable intervals. No material discrepancies were noticed on such verification. The title deeds of all immovable properties disclosed in the financial statements are held in the name of the Company. No proceedings have been initiated or are pending against the Company for holding any benami property under the Benami Transactions (Prohibition) Act, 1988.',
    evidenceSource: 'Fixed Asset Register (FAR), Title Deeds, MCA MCA21 RoC Search, Municipal Tax Receipts',
    groundedAttributes: [
      { label: 'Statutory Act', value: 'Companies Act, 2013' },
      { label: 'Depreciation Framework', value: 'Schedule II (SLM/WDV) vs Sec 32' },
      { label: 'Benami Inquiries', value: 'Nil Proceedings Pending' },
      { label: 'Revaluation Status', value: 'No Revaluation during FY' }
    ]
  },
  'Clause 3(ii)': {
    title: 'Inventories & Working Capital Limits',
    legalRef: "CARO 2020 Order Clause 3(ii)(a) & 3(ii)(b)",
    wpRef: 'WP-CARO-02 / INV-STK',
    subClauses: [
      {
        code: '(a)',
        label: 'Physical Verification of Inventory',
        details: 'Whether physical verification of inventory has been conducted at reasonable intervals by management; whether discrepancies of 10% or more in aggregate for each class of inventory were noticed.'
      },
      {
        code: '(b)',
        label: 'Quarterly Bank Returns (> ₹5 Crore Working Capital)',
        details: 'Whether quarterly returns or statements filed with banks/financial institutions for sanctioned working capital limits exceeding ₹5 Crore agree with books of account.'
      }
    ],
    auditProcedures: [
      'Attended year-end physical inventory counting procedures as observing auditor.',
      'Reconciled quarterly hypothecation stock statements submitted to working capital consortium banks with General Ledger.',
      'Tested lower of cost or net realizable value (NRV) valuation method in compliance with AS 2 / Ind AS 2.'
    ],
    sampleDraft:
      'Physical verification of inventory has been conducted at reasonable intervals by the management. In our opinion, the coverage and procedure of such verification by the management is appropriate. No discrepancies of 10% or more in the aggregate for each class of inventory were noticed on physical verification. The quarterly returns/statements filed by the Company with banks/financial institutions for sanctioned working capital limits are in agreement with the books of account of the Company.',
    evidenceSource: 'Physical Stock Count Sheets, Bank Stock Hypothecation Statements, Cost Audit Records',
    groundedAttributes: [
      { label: 'Valuation Standard', value: 'AS 2 / Ind AS 2 (Lower of Cost or NRV)' },
      { label: 'Bank Sanction Limit', value: 'Assessed against ₹5 Crore threshold' },
      { label: 'Stock Discrepancy', value: 'Less than 10% tolerance' },
      { label: 'Bank Reconcile Status', value: 'Fully Reconciled with GL' }
    ]
  },
  'Clause 3(iii)': {
    title: 'Investments, Guarantees, Security, Loans to Parties',
    legalRef: "Companies Act 2013, Sections 185, 186, 189 & CARO 2020 Clause 3(iii)",
    wpRef: 'WP-CARO-03 / SEC-189',
    subClauses: [
      {
        code: '(a)',
        label: 'Loans & Guarantees Given to Subsidiaries/Others',
        details: 'Aggregate amount granted during year and balance outstanding at balance sheet date with respect to subsidiaries, joint ventures, associates, and others.'
      },
      {
        code: '(b)',
        label: 'Terms Not Prejudicial to Company',
        details: 'Whether investments made, guarantees provided, security given and terms and conditions are not prejudicial to company interest.'
      },
      {
        code: '(c)',
        label: 'Regularity of Repayment & Interest',
        details: 'Whether schedule of repayment of principal and payment of interest has been stipulated and repayments or receipts are regular.'
      },
      {
        code: '(d)',
        label: 'Overdue Amounts (>90 Days)',
        details: 'Whether any amount is overdue for more than 90 days, and reasonable steps taken by company for recovery of principal and interest.'
      }
    ],
    auditProcedures: [
      'Inspected Loan agreements, Board resolutions, and register maintained under Section 189.',
      'Verified interest rate benchmarking against prevailing bank/RBI lending yields.',
      'Analyzed aging of loans given and evaluated expected credit loss (ECL) provisioning.'
    ],
    sampleDraft:
      'According to the information and explanations given to us, the Company has not granted any loans, secured or unsecured, to companies, firms, LLPs or other parties covered in the register maintained under Section 189 of the Companies Act, 2013. The terms and conditions of investments and guarantees are not prejudicial to the interest of the Company. Repayments of principal and interest where stipulated have been regular and no amounts are overdue for more than 90 days.',
    evidenceSource: 'Register under Section 189, Loan Agreements, Bank Advices, Board Minutes',
    groundedAttributes: [
      { label: 'Section 186 Ceiling', value: 'Within permissible 60%/100% threshold' },
      { label: 'Related Party Loans', value: 'Nil Prejudicial Terms' },
      { label: 'Overdue > 90 Days', value: '₹0.00 Overdue' }
    ]
  },
  'Clause 3(iv)': {
    title: 'Compliance with Sections 185 and 186',
    legalRef: "Companies Act 2013, Sections 185 (Loans to Directors) and 186 (Loans & Investments)",
    wpRef: 'WP-CARO-04 / SEC-185-186',
    subClauses: [
      {
        code: '(a)',
        label: 'Loans to Directors (Section 185)',
        details: 'Whether company has complied with restrictions on granting loans, guarantees, or security to directors or entities in which directors are interested.'
      },
      {
        code: '(b)',
        label: 'Loans & Investments (Section 186)',
        details: 'Whether loans, guarantees, security, and acquisitions comply with statutory ceilings (60% of paid-up capital + free reserves + securities premium or 100% of free reserves + securities premium).'
      }
    ],
    auditProcedures: [
      'Scrutinized General Ledger for direct or indirect advances to directors and related entities.',
      'Verified Special Resolutions passed in General Meeting for investments exceeding Section 186 limits.',
      'Inspected MBP-1 declarations of director interests and board approvals.'
    ],
    sampleDraft:
      'In our opinion and according to the information and explanations given to us, the Company has complied with the provisions of Sections 185 and 186 of the Companies Act, 2013 in respect of loans, investments, guarantees, and security provided, where applicable.',
    evidenceSource: 'Form MBP-1, Board Resolutions, Loan Registers, ROC Filings',
    groundedAttributes: [
      { label: 'Director Loans', value: 'Compliant with Section 185' },
      { label: 'Investment Limit', value: 'Within Section 186 Limits' }
    ]
  },
  'Clause 3(v)': {
    title: 'Public Deposits Acceptance',
    legalRef: "Companies Act 2013, Sections 73 to 76 & Reserve Bank of India Directives",
    wpRef: 'WP-CARO-05 / DPT-3',
    subClauses: [
      {
        code: '(a)',
        label: 'Deemed Deposits & Compliance',
        details: 'Whether company has accepted any deposits or deemed deposits under Sections 73 to 76 and RBI directives; whether Company Law Board/NCLT orders complied with.'
      }
    ],
    auditProcedures: [
      'Reconciled Form DPT-3 return of deposits / particulars of transactions not considered as deposit.',
      'Examined share application money pending allotment beyond statutory 60-day period.',
      'Verified unsecured loans from directors accompanied by written declaration of source of funds.'
    ],
    sampleDraft:
      'The Company has not accepted any deposits or amounts which are deemed to be deposits within the meaning of Sections 73 to 76 of the Companies Act, 2013 and the rules framed thereunder. Accordingly, reporting under Clause 3(v) of the Order is not applicable.',
    evidenceSource: 'Form DPT-3, Director Declarations, General Ledger Unsecured Loans',
    groundedAttributes: [
      { label: 'Public Deposits', value: 'Nil Accepted' },
      { label: 'Form DPT-3 Status', value: 'Filed on MCA Portal' }
    ]
  },
  'Clause 3(vi)': {
    title: 'Maintenance of Cost Records',
    legalRef: "Companies Act 2013, Section 148(1) & Companies (Cost Records and Audit) Rules",
    wpRef: 'WP-CARO-06 / COST-AUDIT',
    subClauses: [
      {
        code: '(a)',
        label: 'Maintenance of Accounts & Records',
        details: 'Whether maintenance of cost records has been specified by Central Government under Section 148(1) and whether such accounts and records have been made and maintained.'
      }
    ],
    auditProcedures: [
      'Evaluated turnover of company against statutory threshold (₹35 Crore / ₹100 Crore in regulated/non-regulated sectors).',
      'Broadly reviewed Form CRA-1 cost records maintained by management to ensure compliance.'
    ],
    sampleDraft:
      'We have broadly reviewed the books of account maintained by the Company pursuant to the rules made by the Central Government for the maintenance of cost records under Section 148(1) of the Companies Act, 2013, and are of the opinion that prima facie, the prescribed accounts and records have been made and maintained. We have not, however, made a detailed examination of the same.',
    evidenceSource: 'Turnover Calculations, Form CRA-1 / CRA-2, Manufacturing Production Logs',
    groundedAttributes: [
      { label: 'Cost Rules Applicability', value: 'Verified based on Turnover & Industry' },
      { label: 'Record Quality', value: 'Proper Records Maintained' }
    ]
  },
  'Clause 3(vii)': {
    title: 'Undisputed & Disputed Statutory Dues',
    legalRef: "CARO 2020 Clause 3(vii)(a) & 3(vii)(b)",
    wpRef: 'WP-CARO-07 / STAT-DUES',
    subClauses: [
      {
        code: '(a)',
        label: 'Undisputed Statutory Dues (> 6 Months)',
        details: 'Regularity in depositing undisputed statutory dues including GST, PF, ESI, Income-tax, Customs duty, Cess; arrears outstanding for > 6 months from due date.'
      },
      {
        code: '(b)',
        label: 'Disputed Statutory Dues & Forum',
        details: 'Statutory dues not deposited on account of any dispute, showing amount involved and forum where dispute is pending.'
      }
    ],
    auditProcedures: [
      'Reconciled GST liability with GSTR-3B filings, Electronic Cash/Credit Ledgers.',
      'Examined PF/ESI monthly challans and payment dates against statutory due date (15th of succeeding month).',
      'Inspected litigation register and demand notices for disputed income tax / GST appeals.'
    ],
    sampleDraft:
      'According to the records of the Company, undisputed statutory dues including Goods and Services Tax, Provident Fund, Employees State Insurance, Income-tax, Sales-tax, Duty of Customs, Duty of Excise, Value Added Tax, Cess and other statutory dues have been regularly deposited with the appropriate authorities. There are no undisputed arrears of statutory dues outstanding as at 31st March for a period of more than six months from the date they became payable. There are no disputed dues pending before any appellate forum.',
    evidenceSource: 'GSTR-3B, Electronic Cash Ledger, PF/ESI Challans, Advance Tax Challans',
    groundedAttributes: [
      { label: 'GST Dues Status', value: 'Regularly Deposited' },
      { label: 'PF / ESI Regularity', value: 'Within statutory due dates' },
      { label: 'Arrears > 6 Months', value: '₹0.00 Nil' },
      { label: 'Litigation Disputes', value: 'No adverse demands' }
    ]
  },
  'Clause 3(viii)': {
    title: 'Unrecorded Income Disclosed in Tax Assessments',
    legalRef: "Income Tax Act, 1961 Search/Survey & CARO 2020 Clause 3(viii)",
    wpRef: 'WP-CARO-08 / TAX-SURVEY',
    subClauses: [
      {
        code: '(a)',
        label: 'Tax Surrender / Disclosure in Books',
        details: 'Whether any transactions not recorded in books of account have been surrendered or disclosed as income during the year in tax assessments under Income Tax Act, 1961.'
      }
    ],
    auditProcedures: [
      'Scrutinized Income Tax portal for assessment orders under Section 143(3), 144, 147, or 153A.',
      'Obtained written representation from management on absence of undisclosed income.'
    ],
    sampleDraft:
      'According to the information and explanations given to us, no transactions not recorded in the books of account have been surrendered or disclosed as income during the year in the tax assessments under the Income Tax Act, 1961. Previously unrecorded income and related assets have been properly recorded in the books of account.',
    evidenceSource: 'ITR Acknowledgement, Assessment Orders, Management Representation Letter',
    groundedAttributes: [
      { label: 'Search/Survey Status', value: 'Nil Initiated' },
      { label: 'Disclosed Income', value: '₹0.00' }
    ]
  },
  'Clause 3(ix)': {
    title: 'Default in Repayment of Borrowings',
    legalRef: "CARO 2020 Clause 3(ix)(a)-(f)",
    wpRef: 'WP-CARO-09 / BORR-DEF',
    subClauses: [
      {
        code: '(a)',
        label: 'Defaults in Loans/Interest',
        details: 'Whether company has defaulted in repayment of loans or other borrowings or in payment of interest to any lender; period and amount of default.'
      },
      {
        code: '(b)',
        label: 'Wilful Defaulter Declaration',
        details: 'Whether company is declared a wilful defaulter by any bank, financial institution or other lender.'
      },
      {
        code: '(c)',
        label: 'Application of Term Loans',
        details: 'Whether term loans were applied for purpose for which loans were obtained.'
      },
      {
        code: '(d)',
        label: 'Short-Term Funds Used for Long-Term',
        details: 'Whether funds raised on short-term basis have been utilized for long-term purposes.'
      }
    ],
    auditProcedures: [
      'Obtained independent balance confirmations and bank statements from all lending banks.',
      'Inspected CIBIL Commercial reports and RBI Wilful Defaulter database.',
      'Analyzed cash flow statements to track end-use of term loans against sanction covenants.'
    ],
    sampleDraft:
      'According to the records of the Company, the Company has not defaulted in repayment of loans or other borrowings or in the payment of interest thereon to any lender. The Company has not been declared a wilful defaulter by any bank or financial institution or other lender. Term loans obtained were applied for the purpose for which they were raised, and funds raised on short-term basis have not been utilized for long-term purposes.',
    evidenceSource: 'Bank Loan Sanction Letters, Bank Statements, CIBIL Reports, Cash Flow Statement',
    groundedAttributes: [
      { label: 'Default Amount', value: '₹0.00 Nil Default' },
      { label: 'Wilful Defaulter', value: 'Clean Record (No declaration)' },
      { label: 'Term Loan End-Use', value: 'Utilized as per Sanction' }
    ]
  },
  'Clause 3(x)': {
    title: 'Public Offers & Preferential Allotments',
    legalRef: "Companies Act 2013, Sections 42, 62 & CARO 2020 Clause 3(x)",
    wpRef: 'WP-CARO-10 / SHARE-CAP',
    subClauses: [
      {
        code: '(a)',
        label: 'IPO/FPO Moneys Utilization',
        details: 'Whether moneys raised by initial public offer or further public offer were applied for purposes for which raised.'
      },
      {
        code: '(b)',
        label: 'Private Placement & Preferential Issue (Sec 42/62)',
        details: 'Whether company made preferential allotment or private placement of shares or convertible debentures, and requirements of Section 42 and 62 complied with.'
      }
    ],
    auditProcedures: [
      'Inspected Form PAS-3 (Return of Allotment) and valuation reports for share issuance.',
      'Reconciled dedicated escrow bank account for subscription moneys received.'
    ],
    sampleDraft:
      'The Company has not raised any money by way of initial public offer or further public offer (including debt instruments) during the year. The Company has not made any preferential allotment or private placement of shares or convertible debentures during the year under review. Accordingly, Clause 3(x) of the Order is not applicable.',
    evidenceSource: 'Form PAS-3, ROC Filings, Bank Statements, Valuation Certificates',
    groundedAttributes: [
      { label: 'Public Offer', value: 'Nil during FY' },
      { label: 'Private Placement', value: 'Fully Compliant under Sec 42' }
    ]
  },
  'Clause 3(xi)': {
    title: 'Fraud Noticed or Reported (SA 240)',
    legalRef: "Companies Act 2013, Section 143(12) & CARO 2020 Clause 3(xi)",
    wpRef: 'WP-CARO-11 / SA-240-FRAUD',
    subClauses: [
      {
        code: '(a)',
        label: 'Fraud Noticed on/by Company',
        details: 'Whether any fraud by the company or any fraud on the company has been noticed or reported during the year; nature and amount involved.'
      },
      {
        code: '(b)',
        label: 'Reporting under Section 143(12) Form ADT-4',
        details: 'Whether any report under Section 143(12) has been filed by auditors in Form ADT-4 with the Central Government.'
      },
      {
        code: '(c)',
        label: 'Whistle-Blower Complaints',
        details: 'Whether auditor has considered whistle-blower complaints, if any, received during the year by the company.'
      }
    ],
    auditProcedures: [
      'Executed forensic Benford Law analysis, weekend posting scans, and round-sum journal queries.',
      'Inspected vigil mechanism records and audit committee whistle-blower logs.',
      'Obtained written representations from management and audit committee.'
    ],
    sampleDraft:
      'Based upon the audit procedures performed for the purpose of reporting the true and fair view of the financial statements and according to the information and explanations given to us, no fraud by the Company or on the Company has been noticed or reported during the year. No report under Section 143(12) of the Companies Act has been filed in Form ADT-4 with the Central Government during the year and upto the date of this report. No whistle-blower complaints have been received by the Company during the year.',
    evidenceSource: 'Forensic Journal Logs, Whistle-Blower Register, Audit Committee Minutes',
    groundedAttributes: [
      { label: 'Fraud Incidents', value: 'Nil Reported' },
      { label: 'Form ADT-4', value: 'Not Required (Zero Fraud)' },
      { label: 'Whistle-blower Logs', value: 'Zero Complaints Pending' }
    ]
  },
  'Clause 3(xii)': {
    title: 'Nidhi Company Compliance',
    legalRef: "Companies Act 2013, Section 406 & Nidhi Rules 2014",
    wpRef: 'WP-CARO-12 / NIDHI-RULES',
    subClauses: [
      {
        code: '(a)',
        label: 'Net Owned Funds to Deposits Ratio',
        details: 'Whether Nidhi Company has maintained Net Owned Funds to Deposits ratio of 1:20 and 10% unencumbered term deposits.'
      }
    ],
    auditProcedures: ['Checked incorporation charter; company is not a Nidhi Company.'],
    sampleDraft: 'The Company is not a Nidhi Company. Accordingly, Clause 3(xii) of the Order is not applicable.',
    evidenceSource: 'Certificate of Incorporation, Memorandum of Association',
    groundedAttributes: [{ label: 'Entity Status', value: 'Non-Nidhi Commercial Corporate' }]
  },
  'Clause 3(xiii)': {
    title: 'Transactions with Related Parties (Sec 177 & 188)',
    legalRef: "Companies Act 2013, Sections 177, 188 & Accounting Standard AS-18 / Ind AS 24",
    wpRef: 'WP-CARO-13 / REL-PARTY',
    subClauses: [
      {
        code: '(a)',
        label: 'Compliance with Section 177 and 188',
        details: 'Whether all transactions with related parties are in compliance with Section 177 and 188 where applicable and details disclosed in financial statements.'
      }
    ],
    auditProcedures: [
      'Scrutinized related party ledger transactions against omnibus approval of Audit Committee.',
      'Verified transfer pricing and arm’s length justification for sales/purchases with related parties.',
      'Checked Notes to Accounts disclosures against AS-18 / Ind AS 24.'
    ],
    sampleDraft:
      'According to the information and explanations given to us and based on our examination of the records of the Company, transactions with related parties are in compliance with Sections 177 and 188 of the Companies Act, 2013 where applicable and details of such transactions have been disclosed in the financial statements as required by the applicable accounting standards.',
    evidenceSource: 'Related Party Ledger, Audit Committee Approvals, Form MBP-1, AS-18 Disclosures',
    groundedAttributes: [
      { label: 'Approval Status', value: 'Prior Board/Committee Approval Recorded' },
      { label: 'Pricing Standard', value: 'Arm’s Length Basis Verified' }
    ]
  },
  'Clause 3(xiv)': {
    title: 'Internal Audit System (Section 138)',
    legalRef: "Companies Act 2013, Section 138 & Companies (Accounts) Rules",
    wpRef: 'WP-CARO-14 / INT-AUDIT',
    subClauses: [
      {
        code: '(a)',
        label: 'Adequacy of Internal Audit System',
        details: 'Whether company has an internal audit system commensurate with size and nature of its business.'
      },
      {
        code: '(b)',
        label: 'Consideration of Internal Audit Reports',
        details: 'Whether reports of internal auditor for period under audit were considered by statutory auditor.'
      }
    ],
    auditProcedures: [
      'Reviewed scope of internal audit and qualifications of appointed internal auditor.',
      'Examined internal audit reports and management action taken reports (ATR).'
    ],
    sampleDraft:
      'In our opinion, the Company has an internal audit system commensurate with the size and nature of its business. We have considered the internal audit reports of the Company issued till date for the period under audit.',
    evidenceSource: 'Internal Audit Reports, Board Appointment Resolutions, Action Taken Reports',
    groundedAttributes: [
      { label: 'System Adequacy', value: 'Commensurate with business scale' },
      { label: 'Reports Scrutinized', value: 'All periodic reports reviewed' }
    ]
  },
  'Clause 3(xv)': {
    title: 'Non-Cash Transactions with Directors (Sec 192)',
    legalRef: "Companies Act 2013, Section 192",
    wpRef: 'WP-CARO-15 / NON-CASH',
    subClauses: [
      {
        code: '(a)',
        label: 'Director Non-Cash Assets Exchange',
        details: 'Whether company has entered into non-cash transactions with directors or persons connected with him and provisions of Section 192 complied with.'
      }
    ],
    auditProcedures: [
      'Reviewed asset additions and disposals for non-cash consideration.',
      'Obtained director written confirmations on Section 192 compliance.'
    ],
    sampleDraft:
      'According to the information and explanations given to us, the Company has not entered into any non-cash transactions with directors or persons connected with them. Accordingly, provisions of Section 192 of the Companies Act, 2013 are not applicable.',
    evidenceSource: 'Fixed Asset Additions/Deletions, General Ledger, Director Confirmations',
    groundedAttributes: [{ label: 'Non-Cash Deals', value: 'Nil during FY' }]
  },
  'Clause 3(xvi)': {
    title: 'Registration under Section 45-IA of RBI Act',
    legalRef: "Reserve Bank of India Act, 1934 Section 45-IA & Core Investment Company Rules",
    wpRef: 'WP-CARO-16 / RBI-45IA',
    subClauses: [
      {
        code: '(a)',
        label: 'NBFC / CIC Registration Requirement',
        details: 'Whether company is required to be registered under Section 45-IA of RBI Act, 1934 and whether registration obtained; whether company conducted housing finance/NBFC activities without CoR.'
      }
    ],
    auditProcedures: [
      'Conducted 50-50 test (financial assets > 50% of total assets AND income from financial assets > 50% of gross income).',
      'Confirmed company principal business is non-financial.'
    ],
    sampleDraft:
      'The Company is not required to be registered under Section 45-IA of the Reserve Bank of India Act, 1934. The Company has not conducted any Non-Banking Financial or Housing Finance activities. The Company is not a Core Investment Company (CIC) as defined in the regulations made by the Reserve Bank of India.',
    evidenceSource: 'Balance Sheet Asset Structure, P&L Income Breakup, MoA Objects Clause',
    groundedAttributes: [
      { label: '50-50 Asset Test', value: 'Negative (Operating Commercial Company)' },
      { label: 'CoR Required', value: 'Not Required' }
    ]
  },
  'Clause 3(xvii)': {
    title: 'Cash Losses Incurred',
    legalRef: "CARO 2020 Clause 3(xvii)",
    wpRef: 'WP-CARO-17 / CASH-LOSS',
    subClauses: [
      {
        code: '(a)',
        label: 'Cash Loss in Current & Preceding FY',
        details: 'Whether company has incurred cash losses in financial year and in immediately preceding financial year; amount of cash losses.'
      }
    ],
    auditProcedures: [
      'Calculated Cash Loss = Profit After Tax (PAT) adjusted for non-cash items (Depreciation, Amortization, Deferred Tax, Impairment).'
    ],
    sampleDraft:
      'The Company has not incurred cash losses in the current financial year and in the immediately preceding financial year.',
    evidenceSource: 'Profit & Loss Statement, Cash Flow Statement, Depreciation Schedules',
    groundedAttributes: [
      { label: 'Current FY Cash Loss', value: '₹0.00 (Profitable / Positive Cash Flow)' },
      { label: 'Preceding FY Cash Loss', value: '₹0.00' }
    ]
  },
  'Clause 3(xviii)': {
    title: 'Resignation of Statutory Auditors',
    legalRef: "Companies Act 2013, Section 140(2) & CARO 2020 Clause 3(xviii)",
    wpRef: 'WP-CARO-18 / ADT-3',
    subClauses: [
      {
        code: '(a)',
        label: 'Auditor Resignation & Objections',
        details: 'Whether there has been any resignation of statutory auditors during year; whether issues, objections or concerns raised by outgoing auditors considered.'
      }
    ],
    auditProcedures: ['Checked appointment history and Form ADT-1 / ADT-3 filings on MCA portal.'],
    sampleDraft: 'There has been no resignation of the statutory auditors during the year. Accordingly, reporting under Clause 3(xviii) is not applicable.',
    evidenceSource: 'MCA Portal ADT-1 Filings, AGM Minutes',
    groundedAttributes: [{ label: 'Auditor Resignation', value: 'Nil during FY' }]
  },
  'Clause 3(xix)': {
    title: 'Material Uncertainty on Going Concern (<1 Year)',
    legalRef: "Standards on Auditing SA 570 (Revised) & CARO 2020 Clause 3(xix)",
    wpRef: 'WP-CARO-19 / SA-570-GC',
    subClauses: [
      {
        code: '(a)',
        label: 'Solvency & Payment of Liabilities within 1 Year',
        details: 'Financial ratios, ageing and expected dates of realization of financial assets and payment of financial liabilities, auditor knowledge of Board/management plans; whether material uncertainty exists.'
      }
    ],
    auditProcedures: [
      'Evaluated Current Ratio, Debt-Equity Ratio, Debt Service Coverage Ratio, Return on Equity.',
      'Verified working capital availability and operating cash flows over 12 months rolling forecast.',
      'Confirmed absence of default in statutory dues, vendor payments, or bank loan covenants.'
    ],
    sampleDraft:
      'According to the information and explanations given to us and on the basis of the financial ratios, ageing and expected dates of realization of financial assets and payment of financial liabilities, other information accompanying the financial statements, our knowledge of the Board of Directors and management plans and based on our examination of the evidence supporting the assumptions, nothing has come to our attention, which causes us to believe that any material uncertainty exists as on the date of the audit report that Company is not capable of meeting its liabilities existing at the date of balance sheet as and when they fall due within a period of one year from the balance sheet date. We, however, state that this is not an assurance as to the future viability of the Company.',
    evidenceSource: 'Schedule III 7 Key Ratios, Rolling 12-Month Cash Flow Forecast, Debtor/Creditor Aging',
    groundedAttributes: [
      { label: 'Going Concern Assessment', value: 'Appropriate (No Material Uncertainty)' },
      { label: '12-Month Liquidity', value: 'Adequate Current Assets Coverage' },
      { label: 'SA 570 Standard', value: 'Unmodified Opinion Basis' }
    ]
  },
  'Clause 3(xx)': {
    title: 'Corporate Social Responsibility (CSR Sec 135)',
    legalRef: "Companies Act 2013, Section 135 & Companies (CSR Policy) Rules",
    wpRef: 'WP-CARO-20 / CSR-135',
    subClauses: [
      {
        code: '(a)',
        label: 'Transfer of Unspent CSR (< 6 Months)',
        details: 'Whether company has transferred unspent amount for other than ongoing projects to a Fund specified in Schedule VII within 6 months of financial year end.'
      },
      {
        code: '(b)',
        label: 'Special Bank Account for Ongoing CSR (< 30 Days)',
        details: 'Whether amount remaining unspent under Section 135(5) pursuant to ongoing project has been transferred to special account within 30 days.'
      }
    ],
    auditProcedures: [
      'Calculated 2% average net profit of preceding 3 financial years.',
      'Inspected CSR committee meetings, approved projects, and bank payment receipts.'
    ],
    sampleDraft:
      'The Company has fulfilled its Corporate Social Responsibility obligations in accordance with Section 135 of the Companies Act, 2013. There are no unspent amounts required to be transferred to a Fund specified in Schedule VII or special bank account under Section 135(6).',
    evidenceSource: 'P&L Preceding 3 Years Computations, CSR Committee Minutes, Bank Receipts',
    groundedAttributes: [
      { label: 'CSR Applicability', value: 'Evaluated under Sec 135(1) Net Worth/Profit' },
      { label: 'Unspent Obligation', value: '₹0.00' }
    ]
  },
  'Clause 3(xxi)': {
    title: 'Qualifications in Group CARO Reports',
    legalRef: "CARO 2020 Clause 3(xxi) (Consolidated Financial Statements)",
    wpRef: 'WP-CARO-21 / CFS-CONSOL',
    subClauses: [
      {
        code: '(a)',
        label: 'Adverse Remarks in Subsidiary/Group CARO',
        details: 'Whether there have been any qualifications or adverse remarks by the respective auditors in the CARO reports of the companies included in the consolidated financial statements.'
      }
    ],
    auditProcedures: [
      'Reviewed independent audit reports of group subsidiaries, joint ventures, and associates.',
      'Collated paragraph references of qualifications, if any, for standalone and group entities.'
    ],
    sampleDraft:
      'In our opinion and according to the information and explanations given to us, there are no qualifications or adverse remarks by the respective auditors in the CARO reports of the entities included in the consolidated financial statements.',
    evidenceSource: 'Subsidiary Audit Reports, Group Auditor Clearance Letters',
    groundedAttributes: [
      { label: 'Consolidated Reporting', value: 'Clean Group Clearance' },
      { label: 'Adverse Mentions', value: 'Nil' }
    ]
  },
  'Clause 17': {
    title: 'Transfer of Land/Building < Stamp Duty Value (Sec 43CA / 50C)',
    legalRef: 'Income Tax Act 1961, Section 43CA & Section 50C',
    wpRef: 'WP-3CD-17 / STAMP-VAL',
    subClauses: [
      {
        code: '(a)',
        label: 'Immovable Property Transferred',
        details: 'Full details of land or building or both transferred during the financial year.'
      },
      {
        code: '(b)',
        label: 'Consideration vs Circle Rate',
        details: 'Consideration received or accrued compared against value adopted or assessed by stamp valuation authority (Circle Rate/Guidance Value).'
      },
      {
        code: '(c)',
        label: 'Safe Harbour Tolerance (10%)',
        details: 'Verification whether variance between consideration and stamp duty value exceeds the 10% statutory safe-harbour threshold under Section 43CA/50C.'
      }
    ],
    auditProcedures: [
      'Examined registered conveyance deeds, agreements for sale, and stamp duty valuation certificates for all property transfers during the year.',
      'Cross-verified circle rate applied by the registering authority against the actual recorded transaction consideration.'
    ],
    sampleDraft:
      'During the previous year under audit, no immovable property being land or building was transferred by the assessee for a consideration less than the value adopted or assessed by the stamp valuation authority within the purview of Section 43CA / 50C of the Income Tax Act, 1961.',
    evidenceSource: 'Registered Sale Deeds, Encumbrance Certificates, SRO Valuation Receipts, Bank Credit Advice',
    groundedAttributes: [
      { label: 'Statutory Section', value: 'Section 43CA & 50C of Income Tax Act 1961' },
      { label: 'Safe Harbour Band', value: '110% of declared consideration' },
      { label: 'Audit Result', value: 'No Inadmissible Difference Detected' }
    ]
  },
  'Clause 21(a)': {
    title: 'Amounts Inadmissible under Section 40(a)',
    legalRef: 'Income Tax Act 1961, Section 40(a)(i), 40(a)(ia), 40(a)(ib)',
    wpRef: 'WP-3CD-21A / TDS-DISALLOW',
    subClauses: [
      {
        code: '40(a)(i)',
        label: 'Non-Resident Payments without TDS',
        details: 'Interest, royalty, fees for technical services payable outside India or to non-resident without tax deduction or deposit.'
      },
      {
        code: '40(a)(ia)',
        label: 'Resident Payments (30% Disallowance)',
        details: '30% of sum payable to resident contractors, professionals, interest, commission without tax deduction or deposit on or before due date under Section 139(1).'
      }
    ],
    auditProcedures: [
      'Reconciled Form 26Q and Form 27Q quarterly returns with ledger expense accounts.',
      'Sample tested contractual, professional, interest, and commission payments against Challan ITNS 281 deposits.'
    ],
    sampleDraft:
      'We have examined the payments made to residents and non-residents subject to Chapter XVII-B. Based on our verification of books and TDS quarterly statements, all tax deductible was duly deducted and paid within the prescribed statutory period, and no disallowance under Section 40(a)(ia) or 40(a)(i) is attracted.',
    evidenceSource: 'TRACES 26AS, Form 26Q/27Q Filings, Challan 281 Receipts, General Ledger',
    groundedAttributes: [
      { label: 'Disallowance Rate', value: '30% on resident, 100% on foreign non-deduction' },
      { label: 'Section Ref', value: 'Section 40(a)(ia) / 40(a)(i)' },
      { label: 'Challan Verification', value: 'Matched with NSDL/TRACES Challan Records' }
    ]
  },
  'Clause 21(b)': {
    title: 'Amounts Debited to P&L being Capital / Personal Nature',
    legalRef: 'Income Tax Act 1961, Section 37(1)',
    wpRef: 'WP-3CD-21B / CAP-PERS',
    subClauses: [
      {
        code: '(a)',
        label: 'Capital Expenditure in P&L',
        details: 'Verification of repair, renovation, software, or asset expenditure debited to revenue instead of capitalization.'
      },
      {
        code: '(b)',
        label: 'Personal Expenditure of Partners/Directors',
        details: 'Personal conveyance, personal telephone, club fees, or non-business expenditure debited to profit and loss.'
      },
      {
        code: '(c)',
        label: 'Offence or Prohibited by Law (Penalties)',
        details: 'Fines, penalties, or damages paid for infraction of any law or statute.'
      }
    ],
    auditProcedures: [
      'Scrutinized repair and maintenance, legal and professional charges, and miscellaneous expense ledgers.',
      'Inspected invoices > Materiality threshold to ensure enduring benefit assets are capitalized to Fixed Asset Register.',
      'Verified that no fines, GST penalties, or compoundable sums are claimed as business expenditure under Section 37(1).'
    ],
    sampleDraft:
      'Based on our audit procedures and examination of books of account, no personal expenditure or capital nature expenditure has been debited to the Profit and Loss Account during the year, except as specifically disclosed in the Annexures.',
    evidenceSource: 'Vouchers, Invoices, Board Minutes, P&L Schedule',
    groundedAttributes: [
      { label: 'Capitalization Threshold', value: 'Consistent with Schedule II & AS 10' },
      { label: 'Statutory Penalties Debited', value: '₹0.00 (Nil)' },
      { label: 'Personal Expenses Excluded', value: 'Zero non-business deductions' }
    ]
  },
  'Clause 21(d)': {
    title: 'Cash Payments Exceeding ₹10,000 (Section 40A(3))',
    legalRef: 'Income Tax Act 1961, Section 40A(3) read with Rule 6DD',
    wpRef: 'WP-3CD-21D / CASH-40A3',
    subClauses: [
      {
        code: '40A(3)',
        label: 'Aggregate Cash Payment in a Day > ₹10,000',
        details: 'Payments made in respect of an expenditure otherwise than by account payee cheque, demand draft, or prescribed electronic modes (NEFT/RTGS/IMPS/UPI).'
      },
      {
        code: 'Rule 6DD',
        label: 'Exceptions under Rule 6DD',
        details: 'Payments made to RBI, SBI, agricultural producers, or on bank holidays.'
      }
    ],
    auditProcedures: [
      'Extracted cash daybook and cash journal entries for all payments exceeding ₹10,000.',
      'Verified payment vouchers against Rule 6DD exemption conditions.'
    ],
    sampleDraft:
      'During the financial year, the assessee has not made any payment in respect of an expenditure exceeding ₹10,000 in cash in contravention of the provisions of Section 40A(3) read with Rule 6DD of Income Tax Rules, 1962.',
    evidenceSource: 'Cash Book, Bank Statement, Petty Cash Vouchers, Daybook',
    groundedAttributes: [
      { label: 'Cash Ceiling', value: '₹10,000 per person per day (₹35,000 for transport operators)' },
      { label: 'Violations Detected', value: 'Nil' }
    ]
  },
  'Clause 22': {
    title: 'Interest & Overdue Payments to MSME (Section 43B(h))',
    legalRef: 'Section 43B(h) Income Tax Act 1961 read with Section 15, 16 & 23 of MSMED Act 2006',
    wpRef: 'WP-3CD-22 / MSMED-43BH',
    subClauses: [
      {
        code: '43B(h)',
        label: 'Overdue Payments to Micro & Small Enterprises',
        details: 'Any sum payable to micro or small enterprise beyond the time limit specified in Section 15 of MSMED Act (45 days under written agreement, 15 days in absence of agreement) remaining unpaid at year-end.'
      },
      {
        code: 'Sec 16 MSMED',
        label: 'Mandatory Compound Interest at 3x RBI Bank Rate',
        details: 'Calculation of statutory penal compound interest payable on delayed payments.'
      },
      {
        code: 'Sec 23 MSMED',
        label: 'Interest Inadmissible under Income Tax Act',
        details: 'Statutory interest payable under MSMED Act is expressly inadmissible as deduction in computing taxable income.'
      }
    ],
    auditProcedures: [
      'Obtained and verified Udyam registration certificates and active classification status of all trade suppliers.',
      'Conducted substantive ageing analysis of trade payables outstanding as of 31-March against agreed payment terms.',
      'Calculated disallowance pool for all invoices unpaid beyond 45 days / 15 days as required by Finance Act 2023 amendment.'
    ],
    sampleDraft:
      'We have examined the records of the assessee with respect to suppliers registered under the Micro, Small and Medium Enterprises Development Act, 2006 (MSMED Act). Amounts overdue beyond statutory limits specified in Section 15 of MSMED Act have been identified and tabulated in Annexure to Clause 22 for statutory disallowance under Section 43B(h).',
    evidenceSource: 'Udyam Registration Portal, Trade Payables Ageing Schedule, Purchase Ledgers, Bank Payment Advices',
    groundedAttributes: [
      { label: 'Statutory Timeframe', value: '45 Days (Written Agreement) / 15 Days (No Agreement)' },
      { label: 'Applicable Entity Category', value: 'Micro and Small Enterprises (excluding Traders/Medium)' },
      { label: 'Compound Interest Rate', value: '3x RBI Bank Rate (Non-Deductible under Sec 23)' }
    ]
  },
  'Clause 26': {
    title: 'Payments Subject to Section 43B (Statutory Liabilities)',
    legalRef: 'Income Tax Act 1961, Section 43B',
    wpRef: 'WP-3CD-26 / SEC-43B',
    subClauses: [
      {
        code: '(a)',
        label: 'Taxes, Duties, Cess or Fees',
        details: 'GST, Customs Duty, Municipal Taxes accrued during the year.'
      },
      {
        code: '(b)',
        label: 'Employer Contribution to PF, ESI, Gratuity',
        details: 'Sum payable by the assessee as employer to recognized provident fund, superannuation or gratuity.'
      },
      {
        code: '(c)',
        label: 'Bonus or Commission to Employees',
        details: 'Payment to employees as bonus or commission for services rendered.'
      },
      {
        code: '(d)',
        label: 'Interest to Banks & Financial Institutions',
        details: 'Interest on term loan, working capital or borrowings from scheduled banks/NBFCs.'
      },
      {
        code: '(e)',
        label: 'Leave Encashment Provision',
        details: 'Sum payable in lieu of leave to the credit of his employee.'
      }
    ],
    auditProcedures: [
      'Examined ledger accounts of GST payable, PF payable, ESI payable, bonus payable, and interest on term loans.',
      'Verified bank challans and payment dates to confirm payment on or before the due date of filing return under Section 139(1).'
    ],
    sampleDraft:
      'According to the information and explanations given to us, statutory liabilities including GST, PF, ESI, bonus, and interest payable covered under Section 43B have been duly discharged on or before the specified due date for furnishing the return of income under Section 139(1).',
    evidenceSource: 'Statutory Challans, Bank Statements, Ledger Accounts, Annual Returns',
    groundedAttributes: [
      { label: 'Due Date Reference', value: 'Section 139(1) ITR Filing Date' },
      { label: 'Employee Contributions', value: 'Section 36(1)(va) verified against respective fund due dates' },
      { label: 'Status', value: 'Paid within Due Date' }
    ]
  },
  'Clause 31': {
    title: 'Acceptance/Repayment of Loans in Cash > ₹20,000 (Sec 269SS/269T)',
    legalRef: 'Income Tax Act 1961, Section 269SS & Section 269T',
    wpRef: 'WP-3CD-31 / SEC-269SS-269T',
    subClauses: [
      {
        code: '269SS',
        label: 'Acceptance of Loan/Deposit in Cash > ₹20,000',
        details: 'Verification of loans, deposits or specified sums accepted otherwise than by account payee cheque/draft or electronic clearing.'
      },
      {
        code: '269T',
        label: 'Repayment of Loan/Deposit in Cash > ₹20,000',
        details: 'Verification of repayment of loans, deposits or interest otherwise than by account payee cheque/draft.'
      }
    ],
    auditProcedures: [
      'Scrutinized loan ledgers, directors current accounts, unsecured borrowings, and cash receipts/payments.',
      'Cross-referenced banking transactions to verify non-cash settlement modes.'
    ],
    sampleDraft:
      'During the previous year under audit, the assessee has neither accepted nor repaid any loan, deposit, or specified sum in cash exceeding the limit of ₹20,000 in contravention of the provisions of Section 269SS or Section 269T of the Income Tax Act, 1961.',
    evidenceSource: 'Cash Book, Bank Statements, Unsecured Loan Ledgers, Confirmation Statements',
    groundedAttributes: [
      { label: 'Statutory Threshold', value: '₹20,000 Aggregate per Person per Day' },
      { label: 'Contraventions', value: 'Nil' }
    ]
  },
  'Clause 34': {
    title: 'TDS/TCS Deduction, Deposit and Statement Compliance',
    legalRef: 'Income Tax Act 1961, Chapter XVII-B & XVII-BB read with Section 200',
    wpRef: 'WP-3CD-34 / TDS-TCS-COMPL',
    subClauses: [
      {
        code: '34(a)',
        label: 'Tax Deducted and Paid Compliance',
        details: 'Whether the assessee is required to deduct or collect tax as per Chapter XVII-B or XVII-BB, and whether deducted and paid to credit of Central Government.'
      },
      {
        code: '34(b)',
        label: 'Quarterly Statements Filed in Time',
        details: 'Whether the assessee has furnished the statement of tax deducted or tax collected (Forms 24Q, 26Q, 27Q, 27EQ) within prescribed time.'
      },
      {
        code: '34(c)',
        label: 'Interest Payable under Section 201(1A) / 206C(7)',
        details: 'Whether assessee is liable to pay interest for delayed deduction or delayed payment.'
      }
    ],
    auditProcedures: [
      'Downloaded TRACES Consolidated Statement and Form 26AS/AIS for all four quarters.',
      'Reconciled TDS ledger with Challan ITNS 281 and quarterly statement filing acknowledgment receipts.'
    ],
    sampleDraft:
      'The assessee has complied with the provisions of Chapter XVII-B and XVII-BB with respect to deduction and collection of tax at source, timely remittance into the Government account, and filing of quarterly returns in Form 24Q, 26Q, and 27Q within statutory time limits.',
    evidenceSource: 'TRACES Portal, Form 24Q/26Q/27Q Receipts, Challan 281 Records, General Ledger',
    groundedAttributes: [
      { label: 'Quarterly Forms', value: 'Form 24Q (Salary), 26Q (Resident), 27Q (Non-Resident)' },
      { label: 'Portal Verification', value: 'TRACES TAN Compliance Portal Verified' },
      { label: 'Interest under 201(1A)', value: 'Nil' }
    ]
  },
  'Clause 44': {
    title: 'Breakup of Total Expenditure under GST',
    legalRef: 'Income Tax Act 1961, Section 44AB read with CGST Act 2017',
    wpRef: 'WP-3CD-44 / GST-EXP-RECON',
    subClauses: [
      {
        code: '44(A)',
        label: 'Entities Registered under GST',
        details: 'Expenditure in respect of entities registered under GST: exempt goods/services, composition scheme, registered entities.'
      },
      {
        code: '44(B)',
        label: 'Entities Not Registered under GST',
        details: 'Expenditure in respect of entities not registered under GST (Unregistered vendors).'
      },
      {
        code: '44(C)',
        label: 'Total Expenditure Reconciled with P&L',
        details: 'Reconciliation of aggregate expenditure reported under Clause 44 with total expenditure debited to Profit and Loss Account.'
      }
    ],
    auditProcedures: [
      'Extracted vendor-wise expense ledger and cross-referenced with vendor GSTINs and GSTR-2B portal data.',
      'Classified expenses into GST Registered, Composite, Exempt, and Unregistered categories.',
      'Reconciled total expenditure with Schedule III Profit and Loss Account.'
    ],
    sampleDraft:
      'The breakup of total expenditure of the assessee during the year under audit, classified between entities registered and not registered under GST in accordance with the Guidance Note on Tax Audit issued by ICAI, is set forth in Annexure to Clause 44.',
    evidenceSource: 'GSTR-2B Inward Portal Returns, Vendor Master, General Ledger Expense Accounts',
    groundedAttributes: [
      { label: 'Reconciliation Basis', value: 'ICAI Guidance Note on Tax Audit' },
      { label: 'GSTR-2B Matching', value: 'Reconciled with Portal Tax Credit Records' },
      { label: 'Unregistered Vendor Proportion', value: 'Audited & Documented' }
    ]
  }
};

export const StatutoryClauseDetailModal: React.FC<Props> = ({
  clause,
  companyName = "Active Audit Client",
  financialYear = "FY 2024-25",
  onClose,
  onSave
}) => {
  const [activeTab, setActiveTab] = useState<'checklist' | 'evidence' | 'opinion' | 'signoff'>('checklist');
  const [complianceStatus, setComplianceStatus] = useState<string>(clause?.compliance_status || 'NOT_CHECKED');
  const [auditorRemarks, setAuditorRemarks] = useState<string>(clause?.auditor_remarks || '');
  const [evidenceStatus, setEvidenceStatus] = useState<string>(clause?.evidence_status || 'AVAILABLE');
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  if (!clause) return null;

  const meta = CARO_METADATA_REGISTRY[clause.clause_number] || {
    title: clause.clause_title,
    legalRef: clause.statutory_citation || "Income Tax Act 1961 / Companies Act 2013",
    wpRef: `WP-${clause.form_type}-${clause.clause_number.replace(/[^a-zA-Z0-9]/g, '')}`,
    subClauses: [
      {
        code: 'Item (a)',
        label: 'Statutory Verification Criterion',
        details: clause.auditor_remarks || 'Substantive procedures executed against primary book records and voucher documentation.'
      }
    ],
    auditProcedures: [
      'Verified underlying transaction vouchers, ledger postings, and supporting documentation.',
      'Reconciled balances against statutory filing returns and independent third-party evidence.'
    ],
    sampleDraft: clause.auditor_remarks,
    evidenceSource: 'Primary Ledger Postings, Bank Statements, Statutory Portals',
    groundedAttributes: [
      { label: 'Form Type', value: clause.form_type },
      { label: 'Clause Reference', value: clause.clause_number },
      { label: 'Calculated Amount', value: clause.calculated_amount ? `₹${parseFloat(clause.calculated_amount).toLocaleString('en-IN')}` : '₹0.00' }
    ]
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      const updated = await api.updateStatutoryClause(clause.id, {
        compliance_status: complianceStatus,
        auditor_remarks: auditorRemarks,
        evidence_status: evidenceStatus,
      });
      setSaveSuccess(true);
      if (onSave) onSave(updated);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      let msg = err?.message || err?.error || err?.detail;
      if (!msg && typeof err === 'object') {
        try {
          msg = Object.entries(err)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : JSON.stringify(v)}`)
            .join('; ');
        } catch {
          msg = 'Server error';
        }
      }
      alert(`Failed to save working paper notes: ${msg || 'Server error'}`);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/70 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl max-w-3xl w-full max-h-[90vh] flex flex-col shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-blue-950 p-6 text-white flex items-start justify-between">
          <div className="space-y-1.5 max-w-xl">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold bg-blue-500/20 text-blue-300 border border-blue-400/30 px-2.5 py-0.5 rounded-md">
                {clause.clause_number}
              </span>
              <span className="text-[11px] font-semibold text-slate-300 bg-white/10 px-2 py-0.5 rounded-md">
                {clause.form_type === 'CARO_2020' ? 'CARO 2020 Order' : 'Tax Audit Form 3CD'}
              </span>
              <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md ${
                complianceStatus === 'COMPLIANT'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/30'
                  : complianceStatus === 'EXEMPT'
                  ? 'bg-slate-500/20 text-slate-300 border border-slate-400/30'
                  : 'bg-rose-500/20 text-rose-300 border border-rose-400/30'
              }`}>
                {complianceStatus}
              </span>
            </div>
            <h2 className="text-lg font-bold text-white tracking-tight">{meta.title}</h2>
            <p className="text-xs text-slate-300 font-mono text-[11px]">{meta.legalRef}</p>
          </div>

          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white flex items-center justify-center transition cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Client & Audit Context Banner */}
        <div className="bg-slate-50 px-6 py-2.5 border-b border-slate-200/80 flex items-center justify-between text-xs text-slate-600">
          <div className="flex items-center gap-2">
            <Building2 className="w-3.5 h-3.5 text-blue-600" />
            <span className="font-bold text-slate-800">{companyName}</span>
            <span>&bull;</span>
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <span>{financialYear}</span>
          </div>
          <div className="flex items-center gap-2 font-mono text-[11px] text-slate-500">
            <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
            <span>Working Paper: <strong className="text-slate-800">{meta.wpRef}</strong></span>
          </div>
        </div>

        {/* Modal Navigation Tabs */}
        <div className="px-6 pt-3 border-b border-slate-200 flex gap-2 text-xs font-semibold text-slate-600 bg-white">
          <button
            onClick={() => setActiveTab('checklist')}
            className={`pb-2.5 px-3 border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'checklist'
                ? 'border-blue-600 text-blue-600 font-bold'
                : 'border-transparent hover:text-slate-900'
            }`}
          >
            <CheckSquare className="w-3.5 h-3.5" />
            <span>ICAI Statutory Checklist ({meta.subClauses.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('evidence')}
            className={`pb-2.5 px-3 border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'evidence'
                ? 'border-blue-600 text-blue-600 font-bold'
                : 'border-transparent hover:text-slate-900'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Audit Evidence & Metrics</span>
          </button>
          <button
            onClick={() => setActiveTab('opinion')}
            className={`pb-2.5 px-3 border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'opinion'
                ? 'border-blue-600 text-blue-600 font-bold'
                : 'border-transparent hover:text-slate-900'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Auditor Opinion Draft</span>
          </button>
          <button
            onClick={() => setActiveTab('signoff')}
            className={`pb-2.5 px-3 border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'signoff'
                ? 'border-blue-600 text-blue-600 font-bold'
                : 'border-transparent hover:text-slate-900'
            }`}
          >
            <Scale className="w-3.5 h-3.5" />
            <span>Sign-off & Observations</span>
          </button>
        </div>

        {/* Tab Content */}
        <div className="p-6 overflow-y-auto flex-1 space-y-4 text-xs">
          {/* TAB 1: ICAI Sub-Checklist */}
          {activeTab === 'checklist' && (
            <div className="space-y-4">
              <div className="bg-blue-50/60 border border-blue-200/80 rounded-2xl p-4 text-slate-800 space-y-1">
                <div className="flex items-center gap-2 font-bold text-blue-900">
                  <Info className="w-4 h-4 text-blue-600" />
                  <span>Statutory Compliance Guidance (ICAI Technical Guide on CARO 2020)</span>
                </div>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Every sub-clause below represents mandatory verification questions required under the Order. The auditor must obtain sufficient appropriate audit evidence under SA 500 before reporting.
                </p>
              </div>

              <div className="space-y-3">
                {meta.subClauses.map((sub, i) => (
                  <div key={i} className="bg-white border border-slate-200 rounded-2xl p-4 space-y-1.5 hover:border-slate-300 transition">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 font-bold text-slate-900">
                        <span className="font-mono text-[11px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                          {sub.code}
                        </span>
                        <span>{sub.label}</span>
                      </div>
                      <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>VERIFIED</span>
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-600 leading-relaxed pl-1">{sub.details}</p>
                  </div>
                ))}
              </div>

              <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 space-y-2">
                <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                  <BookOpen className="w-3.5 h-3.5 text-blue-600" />
                  <span>Substantive Audit Procedures Carried Out</span>
                </h4>
                <ul className="list-disc pl-5 space-y-1 text-[11px] text-slate-600">
                  {meta.auditProcedures.map((proc, idx) => (
                    <li key={idx}>{proc}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* TAB 2: Audit Evidence & Metrics */}
          {activeTab === 'evidence' && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-slate-50 border border-slate-200 p-3.5 rounded-2xl">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Evidence Status</span>
                  <span className="text-xs font-bold text-emerald-700 flex items-center gap-1 mt-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>{clause.evidence_status}</span>
                  </span>
                </div>
                <div className="bg-slate-50 border border-slate-200 p-3.5 rounded-2xl">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Calculated Amount</span>
                  <span className="text-xs font-bold text-slate-900 block mt-1">
                    {clause.calculated_amount ? `₹${parseFloat(clause.calculated_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '₹0.00'}
                  </span>
                </div>
                <div className="bg-slate-50 border border-slate-200 p-3.5 rounded-2xl">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Audit Rule Version</span>
                  <span className="text-xs font-bold text-slate-700 block mt-1 font-mono">
                    {clause.rule_version || 'FY2024-25.v1'}
                  </span>
                </div>
                <div className="bg-slate-50 border border-slate-200 p-3.5 rounded-2xl">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Verification Timestamp</span>
                  <span className="text-xs font-bold text-slate-700 block mt-1">
                    {clause.verified_at ? new Date(clause.verified_at).toLocaleDateString() : 'Current FY Run'}
                  </span>
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-2xl p-4 space-y-2">
                <h4 className="font-bold text-slate-900 text-xs">Original Substantive Source Evidence</h4>
                <p className="text-[11px] text-slate-600 font-mono bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                  {meta.evidenceSource}
                </p>
              </div>

              <div className="bg-white border border-slate-200 rounded-2xl p-4 space-y-3">
                <h4 className="font-bold text-slate-900 text-xs">Grounded Client Ledger & Register Parameters</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  {meta.groundedAttributes.map((attr, idx) => (
                    <div key={idx} className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                      <span className="text-slate-500 font-medium">{attr.label}</span>
                      <span className="font-bold text-slate-900">{attr.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: Auditor Opinion Draft */}
          {activeTab === 'opinion' && (
            <div className="space-y-4">
              <div className="bg-emerald-50/50 border border-emerald-200 rounded-2xl p-4 text-slate-800 space-y-1">
                <div className="flex items-center gap-2 font-bold text-emerald-900">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>Statutory Auditor's Report Paragraph (Independent Auditor's Report Annexure)</span>
                </div>
                <p className="text-[11px] text-slate-600">
                  Exact standard statutory wording prepared for formal inclusion in the CARO Annexure to the Audit Report under Section 143(11) of the Companies Act, 2013.
                </p>
              </div>

              <div className="bg-slate-900 text-slate-100 p-5 rounded-2xl font-mono text-[11px] leading-relaxed shadow-inner border border-slate-800">
                "{meta.sampleDraft}"
              </div>

              <p className="text-[10px] text-slate-400 italic">
                * Note: If any qualification, reservation or adverse remark is needed, change the Compliance Status to "EXCEPTION_NOTED" in the Sign-off tab to modify this draft opinion.
              </p>
            </div>
          )}

          {/* TAB 4: Sign-off & Observations */}
          {activeTab === 'signoff' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="block text-xs font-bold text-slate-900">
                  Auditor Statutory Compliance Classification
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(['COMPLIANT', 'EXCEPTION_NOTED', 'EXEMPT'] as const).map((st) => (
                    <button
                      key={st}
                      type="button"
                      onClick={() => setComplianceStatus(st)}
                      className={`p-3 rounded-2xl border text-center font-bold text-xs transition cursor-pointer ${
                        complianceStatus === st
                          ? st === 'COMPLIANT'
                            ? 'bg-emerald-50 border-emerald-500 text-emerald-800 ring-2 ring-emerald-400'
                            : st === 'EXEMPT'
                            ? 'bg-slate-100 border-slate-500 text-slate-800 ring-2 ring-slate-400'
                            : 'bg-rose-50 border-rose-500 text-rose-800 ring-2 ring-rose-400'
                          : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      {st}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="block text-xs font-bold text-slate-900">
                  Evidence Verification Status
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(['AVAILABLE', 'PARTIAL', 'MISSING'] as const).map((ev) => (
                    <button
                      key={ev}
                      type="button"
                      onClick={() => setEvidenceStatus(ev)}
                      className={`p-2.5 rounded-xl border text-center font-semibold text-xs transition cursor-pointer ${
                        evidenceStatus === ev
                          ? 'bg-blue-50 border-blue-500 text-blue-800 ring-1 ring-blue-400'
                          : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      {ev}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="block text-xs font-bold text-slate-900">
                  Auditor Working Paper Observations & Notes
                </label>
                <textarea
                  value={auditorRemarks}
                  onChange={(e) => setAuditorRemarks(e.target.value)}
                  rows={4}
                  className="w-full bg-slate-50 border border-slate-200 rounded-2xl p-3 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 leading-relaxed"
                  placeholder="Enter custom audit observations, reference voucher numbers, or qualification details..."
                />
              </div>

              {saveSuccess && (
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold p-3 rounded-xl flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>Working paper observations successfully updated in audit records!</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="bg-slate-50 px-6 py-4 border-t border-slate-200 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-xl text-xs font-semibold cursor-pointer transition"
          >
            Close
          </button>

          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 cursor-pointer transition shadow-xs disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{isSaving ? 'Saving...' : 'Save & Update Working Paper'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
