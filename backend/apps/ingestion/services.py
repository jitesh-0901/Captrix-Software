import logging
from decimal import Decimal
from django.utils import timezone
from django.db import models
from .models import Document, DocumentStatus, DocumentType, ProcessingJob, ExtractedRecord
from .parsers import DocumentParserService, parse_indian_amount, parse_flexible_date

logger = logging.getLogger(__name__)

class IngestionPipelineService:
    @classmethod
    def _dispatch_document_to_subsystems(cls, doc: Document, extracted_objs: list, job: ProcessingJob = None):
        """
        Dispatches normalized extracted records into corresponding accounting and audit subsystems.
        Covers TRIAL_BALANCE, GENERAL_LEDGER, FIXED_ASSET_REGISTER, SUBLEDGER_AGING, BANK_STATEMENT, and GSTR_2B.
        """
        engagement = doc.engagement
        if not engagement:
            return

        as_of = engagement.financial_year.end_date if engagement.financial_year and engagement.financial_year.end_date else timezone.now().date()
        doc_type = doc.document_type
        rows = [dict(o.raw_data, **o.normalized_data) for o in extracted_objs]

        # 1. TRIAL BALANCE
        if doc_type == DocumentType.TRIAL_BALANCE:
            from apps.accounting.services import TrialBalanceService
            tb_res = TrialBalanceService.calculate_trial_balance(
                rows=rows,
                as_of_date=as_of,
                engagement=engagement,
                document=doc
            )
            if job:
                job.logs.append({
                    "time": timezone.now().isoformat(),
                    "message": f"Trial balance generated. Balanced: {tb_res['is_balanced']}, Variance: ₹{tb_res['difference_amount']}"
                })

        # 2. GENERAL LEDGER
        elif doc_type == DocumentType.GENERAL_LEDGER:
            from apps.accounting.services import GeneralLedgerScrutinyService
            gl_txns = GeneralLedgerScrutinyService.import_and_scrutinize(
                engagement=engagement,
                document=doc,
                extracted_objs=extracted_objs
            )
            if job:
                job.logs.append({
                    "time": timezone.now().isoformat(),
                    "message": f"General ledger scrutiny completed across {len(gl_txns)} vouchers. Audit procedures executed."
                })

        # 3. FIXED ASSET REGISTER
        elif doc_type == DocumentType.FIXED_ASSET_REGISTER:
            from apps.audit.far_depreciation import FixedAssetAuditEngine
            far_res = FixedAssetAuditEngine.import_and_validate_far(
                engagement=engagement,
                far_records=rows,
                document=doc
            )
            dep_variance = Decimal(str(far_res.get('depreciation_variance', '0.00')))
            if dep_variance > Decimal('0.00'):
                from apps.reporting.models import ProposedAdjustment, AdjustmentStatus
                ProposedAdjustment.objects.update_or_create(
                    engagement=engagement,
                    adjustment_number="AJE-01",
                    defaults={
                        'title': "Depreciation Adjustment (Schedule II Recalculation)",
                        'reason': "To align unrecorded book depreciation with Companies Act 2013 Schedule II SLM recalculation.",
                        'status': AdjustmentStatus.PROPOSED,
                        'is_posted': False,
                        'posted_at': None,
                        'journal_entries': [
                            {'account': 'Depreciation Expense (P&L)', 'debit': str(dep_variance), 'credit': '0.00'},
                            {'account': 'Accumulated Depreciation (PPE)', 'debit': '0.00', 'credit': str(dep_variance)}
                        ],
                        'total_debit': dep_variance,
                        'total_credit': dep_variance,
                        'is_balanced': True,
                        'pnl_impact': -dep_variance,
                    }
                )
            if job:
                job.logs.append({
                    "time": timezone.now().isoformat(),
                    "message": f"Fixed Asset Register processed. {far_res.get('total_assets', 0)} assets. Sch II Dep: ₹{far_res.get('recalculated_schedule_ii_depreciation', 0)}"
                })

        # 4. SUBLEDGER AGING (DEBTORS / CREDITORS / MSME)
        elif doc_type == DocumentType.SUBLEDGER_AGING:
            from apps.audit.subledger_analytics import SubledgerAnalyticsEngine
            sub_res = SubledgerAnalyticsEngine.process_subledger_items(
                engagement=engagement,
                aging_records=rows,
                as_of_date=as_of
            )
            if job:
                msme_comp = sub_res.get('msme_compliance', {})
                job.logs.append({
                    "time": timezone.now().isoformat(),
                    "message": f"Subledger aging processed. MSME Overdue: {msme_comp.get('overdue_count', 0)} invoices (₹{msme_comp.get('overdue_amount_section_43bh', '0.00')})"
                })

        # 5. BANK STATEMENT
        elif doc_type == DocumentType.BANK_STATEMENT:
            from apps.reconciliation.services import BankReconciliationEngine
            bank_items = []
            for idx, r in enumerate(rows, start=1):
                w_amt = (
                    parse_indian_amount(r.get('Debit_INR')) or
                    parse_indian_amount(r.get('Debit')) or
                    parse_indian_amount(r.get('Withdrawal (Debit)')) or
                    parse_indian_amount(r.get('Withdrawal (INR)')) or
                    parse_indian_amount(r.get('Withdrawal')) or
                    parse_indian_amount(r.get('Withdrawal (Dr)')) or
                    parse_indian_amount(r.get('Debit (INR)')) or
                    Decimal('0.00')
                )
                d_amt = (
                    parse_indian_amount(r.get('Credit_INR')) or
                    parse_indian_amount(r.get('Credit')) or
                    parse_indian_amount(r.get('Deposit (Credit)')) or
                    parse_indian_amount(r.get('Deposit (INR)')) or
                    parse_indian_amount(r.get('Deposit')) or
                    parse_indian_amount(r.get('Deposit (Cr)')) or
                    parse_indian_amount(r.get('Credit (INR)')) or
                    Decimal('0.00')
                )
                is_dep = d_amt > 0
                amt = d_amt if is_dep else w_amt
                if amt > 0:
                    ref_val = (
                        r.get('Bank_Reference') or r.get('Bank Ref') or
                        r.get('Chq / Ref No') or r.get('Chq No') or
                        r.get('Ref No') or r.get('Instrument No') or
                        r.get('UTR') or f"BNK-{idx}"
                    )
                    desc_val = (
                        r.get('Description') or r.get('Particulars') or
                        r.get('Particulars / Narration') or r.get('Narration') or f"Item {idx}"
                    )
                    dt_val = (
                        r.get('Transaction_Date') or r.get('Value_Date') or
                        r.get('Txn Date') or r.get('Date', '2025-04-01')
                    )
                    bank_items.append({
                        'date': dt_val,
                        'ref': str(ref_val),
                        'desc': str(desc_val),
                        'amount': str(amt),
                        'type': 'DEPOSIT' if is_dep else 'WITHDRAWAL'
                    })

            # Check GL vouchers for bank accounts
            book_items = []
            gl_doc = Document.objects.filter(engagement=engagement, document_type=DocumentType.GENERAL_LEDGER).first()
            if gl_doc:
                for idx, g_rec in enumerate(gl_doc.extracted_records.all(), start=1):
                    gdata = g_rec.normalized_data or g_rec.raw_data
                    acc_code = str(gdata.get('Account_Code', gdata.get('Account Code', ''))).strip()
                    acc_name = str(gdata.get('Account_Name', gdata.get('Account Name', ''))).lower()
                    is_bank_acc = (acc_code == '100100' or 'main bank' in acc_name or ('bank' in acc_name and not acc_code.startswith(('2', '3', '4', '5'))))
                    if is_bank_acc:
                        dr_amt = parse_indian_amount(gdata.get('Debit_INR') or gdata.get('Debit') or gdata.get('Debit (INR)')) or Decimal('0.00')
                        cr_amt = parse_indian_amount(gdata.get('Credit_INR') or gdata.get('Credit') or gdata.get('Credit (INR)')) or Decimal('0.00')
                        is_dep = dr_amt > Decimal('0.00')
                        amt = dr_amt if is_dep else cr_amt
                        if amt > Decimal('0.00'):
                            b_ref = (
                                gdata.get('Document_Ref') or gdata.get('Document Ref') or
                                gdata.get('Voucher_No') or gdata.get('Voucher No') or f"GL-{idx}"
                            )
                            book_items.append({
                                'date': gdata.get('Posting_Date') or gdata.get('Date', '2025-04-01'),
                                'ref': str(b_ref),
                                'desc': str(gdata.get('Narration') or gdata.get('Counterparty') or f"GL Entry {idx}"),
                                'amount': str(amt),
                                'type': 'DEPOSIT' if is_dep else 'WITHDRAWAL'
                            })

            # Derive starting balance from Bank ledger account or TB
            bank_acc = engagement.company.ledger_accounts.filter(
                models.Q(code='100100') | models.Q(coa__schedule_iii_group='CASH_CASH_EQUIVALENTS') | models.Q(name__icontains='bank')
            ).first()
            starting_bal = Decimal('0.00')
            if bank_acc and bank_acc.closing_balance > Decimal('0.00'):
                starting_bal = bank_acc.closing_balance
            else:
                tb = engagement.trial_balances.first()
                if tb and tb.accounts_snapshot:
                    for acc in tb.accounts_snapshot:
                        if acc.get('code') == '100100' or 'bank' in str(acc.get('name', '')).lower():
                            s_bal = parse_indian_amount(acc.get('closing_balance') or acc.get('debit'))
                            if s_bal:
                                starting_bal = s_bal
                                break

            # Derive statement closing balance from last transaction running balance
            actual_statement_bal = starting_bal
            if rows:
                last_r = rows[-1]
                last_bal = parse_indian_amount(last_r.get('Running_Balance_INR') or last_r.get('Balance') or last_r.get('Closing Balance'))
                if last_bal is not None:
                    actual_statement_bal = last_bal

            rec_run = BankReconciliationEngine.execute_reconciliation(
                engagement=engagement,
                as_of_date=as_of,
                cashbook_items=book_items,
                bank_items=bank_items,
                starting_cashbook_balance=starting_bal,
                actual_statement_balance=actual_statement_bal
            )
            if job:
                job.logs.append({
                    "time": timezone.now().isoformat(),
                    "message": f"Bank reconciliation executed: {rec_run.matched_count} matched, {rec_run.unmatched_count} timing diffs/unmatched (Status: {rec_run.status})"
                })

    @classmethod
    def trigger_cross_reconciliations_and_statutory_matrix(cls, engagement, job: ProcessingJob = None):
        """
        Executes cross-document reconciliations, CARO 2020 & Form 3CD clauses, and updates workpapers.
        """
        if not engagement:
            return

        try:
            from apps.reconciliation.services import CrossDocumentReconciliationEngine
            cross_runs = CrossDocumentReconciliationEngine.run_all_cross_reconciliations(engagement)
            if job:
                job.logs.append({
                    "time": timezone.now().isoformat(),
                    "message": f"Cross-document reconciliation completed across {len(cross_runs)} schedules."
                })
        except Exception as e:
            logger.warning(f"Cross reconciliation execution failed: {e}")

        try:
            from apps.audit.statutory_forms import StatutoryFormMatrixEngine
            stat_clauses = StatutoryFormMatrixEngine.initialize_and_audit_clauses(engagement)
            if job:
                job.logs.append({
                    "time": timezone.now().isoformat(),
                    "message": f"Statutory audit matrix evaluated across {len(stat_clauses)} CARO 2020 and Form 3CD clauses."
                })
        except Exception as e:
            logger.warning(f"Statutory form matrix execution failed: {e}")

        try:
            from apps.reporting.services import WorkpaperDraftingService
            wps = WorkpaperDraftingService.draft_workpapers(engagement)
            if job:
                job.logs.append({
                    "time": timezone.now().isoformat(),
                    "message": f"Compiled {len(wps)} SA 230 audit workpapers with latest audit evidence."
                })
        except Exception as e:
            logger.warning(f"Workpaper drafting failed: {e}")

    @staticmethod
    def process_document(document: Document) -> ProcessingJob:
        job = ProcessingJob.objects.create(
            document=document,
            stage='STARTING_PARSER',
            progress_percent=10,
            logs=[{"time": timezone.now().isoformat(), "message": f"Processing initialized for {document.original_filename}"}]
        )

        try:
            file_path = document.file.path
            parsed_data = DocumentParserService.parse_file(file_path, document.original_filename)

            detected_type = parsed_data.get('doc_type', 'UNKNOWN')
            if document.document_type == DocumentType.UNKNOWN and detected_type != 'UNKNOWN':
                document.document_type = detected_type

            headers = parsed_data.get('headers', [])
            records = parsed_data.get('records', [])

            # Check if this was a scanned PDF or unsupported image without OCR
            if parsed_data.get('is_scanned_pdf') or parsed_data.get('is_image_without_ocr') or len(records) == 0:
                warning_msg = parsed_data.get('warning_message') or (
                    "No tabular financial records could be extracted from this document. "
                    "Scanned image/PDF without digital text layer detected. Image-based OCR is not configured for scanned photocopies. "
                    "Please upload digital accounting exports (.xlsx, .xls, .csv, or searchable PDF) directly exported from Tally, SAP, Zoho Books, Busy, or QuickBooks."
                )
                document.status = DocumentStatus.REVIEW_REQUIRED
                document.error_message = warning_msg
                document.extracted_summary = {
                    'total_rows': 0,
                    'valid_rows': 0,
                    'review_required_rows': 0,
                    'detected_type': document.document_type,
                    'headers': headers,
                    'warning': warning_msg
                }
                document.save()

                job.stage = 'COMPLETED_WITH_WARNINGS'
                job.progress_percent = 100
                job.total_records = 0
                job.valid_records = 0
                job.review_records = 0
                job.completed_at = timezone.now()
                job.logs.append({
                    "time": timezone.now().isoformat(),
                    "message": warning_msg
                })
                job.save()
                return job

            job.total_records = len(records)
            job.stage = 'EXTRACTING_RECORDS'
            job.progress_percent = 40
            job.logs.append({"time": timezone.now().isoformat(), "message": f"Parsed {len(records)} raw records from {detected_type}"})
            job.save()

            extracted_objs = []
            valid_count = 0
            review_count = 0

            # Delete any existing extracted records if re-running
            ExtractedRecord.objects.filter(document=document).delete()

            for rec in records:
                raw_dict = rec['raw']
                normalized = {}
                validation_status = 'VALID'
                validation_notes = []

                # Attempt normalization on fields
                for k, v in raw_dict.items():
                    k_lower = k.lower()
                    if any(term in k_lower for term in ['amount', 'debit', 'credit', 'balance', 'value', 'tax', 'total', 'cost', 'depn', 'depreciation']):
                        dec_val = parse_indian_amount(v)
                        if dec_val is not None:
                            normalized[k] = str(dec_val)
                        else:
                            normalized[k] = v
                            if v and v != '-':
                                validation_notes.append(f"Ambiguous numeric value in {k}: '{v}'")
                                validation_status = 'REVIEW_REQUIRED'
                    elif any(term in k_lower for term in ['date']):
                        dt_val = parse_flexible_date(v)
                        if dt_val:
                            normalized[k] = dt_val
                        else:
                            normalized[k] = v
                            if v:
                                validation_notes.append(f"Ambiguous date format in {k}: '{v}'")
                                validation_status = 'REVIEW_REQUIRED'
                    else:
                        normalized[k] = v

                if validation_status == 'VALID':
                    valid_count += 1
                else:
                    review_count += 1

                extracted_objs.append(ExtractedRecord(
                    document=document,
                    row_index=rec['row_index'],
                    source_location=rec['source_location'],
                    raw_data=raw_dict,
                    normalized_data=normalized,
                    validation_status=validation_status,
                    validation_notes='; '.join(validation_notes),
                    confidence_score=Decimal('0.95') if validation_status == 'VALID' else Decimal('0.60')
                ))

            ExtractedRecord.objects.bulk_create(extracted_objs, batch_size=500)

            document.status = DocumentStatus.VERIFIED if review_count == 0 else DocumentStatus.REVIEW_REQUIRED
            document.extracted_summary = {
                'total_rows': len(records),
                'valid_rows': valid_count,
                'review_required_rows': review_count,
                'detected_type': document.document_type,
                'headers': headers,
            }
            document.save()

            # Dispatch primary document to its audit subsystem
            if document.engagement:
                IngestionPipelineService._dispatch_document_to_subsystems(document, extracted_objs, job)

                # If multi-sheet workbook, spawn and dispatch sibling Document entries for each extra sheet
                if parsed_data.get('is_multi_sheet'):
                    for sheet in parsed_data.get('sheets', []):
                        if sheet['sheet_name'] == parsed_data.get('sheet_name') or sheet['doc_type'] == 'UNKNOWN':
                            continue

                        s_name = sheet['sheet_name']
                        s_type = sheet['doc_type']
                        s_records = sheet['records']
                        s_headers = sheet['headers']

                        sibling_filename = f"{document.original_filename} [{s_name}]"
                        sibling_hash = f"{document.file_hash}_{s_name}"

                        sibling_doc, _ = Document.objects.get_or_create(
                            engagement=document.engagement,
                            original_filename=sibling_filename,
                            defaults={
                                'file': document.file,
                                'file_hash': sibling_hash,
                                'file_size_bytes': document.file_size_bytes,
                                'mime_type': document.mime_type,
                                'document_type': s_type,
                                'status': DocumentStatus.VERIFIED
                            }
                        )
                        sibling_doc.document_type = s_type
                        sibling_doc.save(update_fields=['document_type'])

                        # Extract records for sibling
                        ExtractedRecord.objects.filter(document=sibling_doc).delete()
                        s_extracted_objs = []
                        for s_rec in s_records:
                            raw_dict = s_rec['raw']
                            norm = {}
                            for k, v in raw_dict.items():
                                k_lower = k.lower()
                                if any(term in k_lower for term in ['amount', 'debit', 'credit', 'balance', 'value', 'tax', 'total', 'cost', 'depn', 'depreciation']):
                                    dec_val = parse_indian_amount(v)
                                    norm[k] = str(dec_val) if dec_val is not None else v
                                elif any(term in k_lower for term in ['date']):
                                    norm[k] = parse_flexible_date(v) or v
                                else:
                                    norm[k] = v
                            s_extracted_objs.append(ExtractedRecord(
                                document=sibling_doc,
                                row_index=s_rec['row_index'],
                                source_location=s_rec['source_location'],
                                raw_data=raw_dict,
                                normalized_data=norm,
                                validation_status='VALID',
                                confidence_score=Decimal('0.95')
                            ))
                        ExtractedRecord.objects.bulk_create(s_extracted_objs, batch_size=500)
                        sibling_doc.extracted_summary = {
                            'total_rows': len(s_records),
                            'valid_rows': len(s_records),
                            'review_required_rows': 0,
                            'detected_type': s_type,
                            'headers': s_headers,
                        }
                        sibling_doc.save()

                        # Dispatch downstream logic for sibling sheet
                        IngestionPipelineService._dispatch_document_to_subsystems(sibling_doc, s_extracted_objs, job)

                        job.logs.append({
                            "time": timezone.now().isoformat(),
                            "message": f"Successfully unpacked and audited workbook tab '{s_name}' as {s_type} ({len(s_records)} records)."
                        })

                # Trigger cross reconciliations and statutory clauses across all ingested documents
                IngestionPipelineService.trigger_cross_reconciliations_and_statutory_matrix(document.engagement, job)

            job.stage = 'COMPLETED'
            job.progress_percent = 100
            job.valid_records = valid_count
            job.review_records = review_count
            job.completed_at = timezone.now()
            job.logs.append({"time": timezone.now().isoformat(), "message": "Extraction and audit execution completed successfully"})
            job.save()

            return job

        except Exception as e:
            logger.exception(f"Error processing document {document.id}: {str(e)}")
            document.status = DocumentStatus.FAILED
            document.error_message = str(e)
            document.save()

            job.stage = 'FAILED'
            job.progress_percent = 100
            job.completed_at = timezone.now()
            job.logs.append({"time": timezone.now().isoformat(), "message": f"Pipeline failure: {str(e)}"})
            job.save()
            raise

        except Exception as e:
            logger.exception(f"Error processing document {document.id}: {str(e)}")
            document.status = DocumentStatus.FAILED
            document.error_message = str(e)
            document.save()

            job.stage = 'FAILED'
            job.progress_percent = 100
            job.completed_at = timezone.now()
            job.logs.append({"time": timezone.now().isoformat(), "message": f"Pipeline failure: {str(e)}"})
            job.save()
            raise
