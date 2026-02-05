"""
Report generation service for creating XLSX reports from search results.
"""
import io
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from ..models import SearchRequest, ContractResult, SpecComparisonRow, SearchStatus, MatchType


class ReportGenerator:
    """Service for generating XLSX reports from search results."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_search_report(self, search_id: str) -> io.BytesIO:
        """
        Generate XLSX report for a search.
        
        Args:
            search_id: UUID of the search request
            
        Returns:
            BytesIO object containing the XLSX file
        """
        # Get search request
        search_request = self.db.query(SearchRequest).filter(
            SearchRequest.id == search_id
        ).first()
        
        if not search_request:
            raise ValueError(f"Search request with ID {search_id} not found")
        
        # Get all contract results for this search
        contract_results = self.db.query(ContractResult).filter(
            ContractResult.search_id == search_id
        ).all()
        
        # Get spec comparison rows for contracts that have them
        contract_ids = [cr.id for cr in contract_results]
        spec_comparisons = {}
        if contract_ids:
            spec_rows = self.db.query(SpecComparisonRow).filter(
                SpecComparisonRow.contract_result_id.in_(contract_ids)
            ).all()
            
            # Group by contract_result_id
            for row in spec_rows:
                if row.contract_result_id not in spec_comparisons:
                    spec_comparisons[row.contract_result_id] = []
                spec_comparisons[row.contract_result_id].append(row)
        
        # Create workbook
        wb = Workbook()
        
        # Remove default sheet
        if 'Sheet' in wb.sheetnames:
            default_sheet = wb['Sheet']
            wb.remove(default_sheet)
        
        # Create sheets
        self._create_summary_sheet(wb, search_request, contract_results)
        self._create_detailed_sheet(wb, contract_results)
        self._create_comparison_sheet(wb, contract_results, spec_comparisons)
        
        # Save to BytesIO
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        return output
    
    def _create_summary_sheet(self, wb: Workbook, search_request: SearchRequest, 
                             contract_results: List[ContractResult]) -> None:
        """Create summary sheet with search parameters and NMCK."""
        ws = wb.create_sheet(title="Сводка")
        
        # Title
        ws['A1'] = "Отчет по поиску контрактов"
        ws['A1'].font = Font(size=16, bold=True)
        ws.merge_cells('A1:E1')
        
        # Search parameters section
        ws['A3'] = "Параметры поиска:"
        ws['A3'].font = Font(bold=True)
        
        search_data = [
            ("ID поиска:", search_request.id),
            ("Статус:", search_request.status.value),
            ("Дата создания:", search_request.created_at.strftime("%Y-%m-%d %H:%M:%S")),
            ("Наименование объекта:", search_request.object_name),
            ("Код КТРУ:", search_request.ktru_code),
            ("Код ОКПД2:", search_request.okpd2_code or "Не указан"),
            ("Регион заказчика:", search_request.customer_region),
            ("Закон:", search_request.law),
            ("Период с:", search_request.date_from.strftime("%Y-%m-%d")),
            ("Период по:", search_request.date_to.strftime("%Y-%m-%d")),
            ("Статусы исполнения:", ", ".join(search_request.execution_statuses)),
            ("Лимит контрактов:", search_request.limit_contracts),
            ("Источник данных:", search_request.input_source.value),
        ]
        
        for i, (label, value) in enumerate(search_data, start=4):
            ws[f'A{i}'] = label
            ws[f'B{i}'] = value
            ws[f'A{i}'].font = Font(bold=True)
        
        # Results section
        results_row = len(search_data) + 5
        ws[f'A{results_row}'] = "Результаты поиска:"
        ws[f'A{results_row}'].font = Font(bold=True)
        
        # Calculate statistics
        total_contracts = len(contract_results)
        accepted_for_nmc = sum(1 for cr in contract_results if cr.accepted_for_nmc)
        identical_matches = sum(1 for cr in contract_results if cr.match_type == MatchType.IDENTICAL)
        homogeneous_matches = sum(1 for cr in contract_results if cr.match_type == MatchType.HOMOGENEOUS)
        no_matches = sum(1 for cr in contract_results if cr.match_type == MatchType.NO_MATCH)
        
        results_data = [
            ("Всего найдено контрактов:", search_request.found_total or 0),
            ("Обработано контрактов:", search_request.processed_count),
            ("Контрактов в отчете:", total_contracts),
            ("Принято для НМЦК:", accepted_for_nmc),
            ("Идентичных совпадений:", identical_matches),
            ("Однородных совпадений:", homogeneous_matches),
            ("Нет совпадений:", no_matches),
            ("Значение НМЦК:", f"{search_request.nmc_value:,.2f} {contract_results[0].currency if contract_results else 'RUB'}" 
             if search_request.nmc_value else "Не рассчитано"),
        ]
        
        for i, (label, value) in enumerate(results_data, start=results_row + 1):
            ws[f'A{i}'] = label
            ws[f'B{i}'] = value
            ws[f'A{i}'].font = Font(bold=True)
        
        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
    
    def _create_detailed_sheet(self, wb: Workbook, contract_results: List[ContractResult]) -> None:
        """Create detailed sheet with list of all analyzed contracts."""
        ws = wb.create_sheet(title="Детализация")
        
        # Headers
        headers = [
            "№",
            "Реестровый номер",
            "Дата подписания",
            "Тип совпадения",
            "Цена за единицу",
            "Валюта",
            "Оценка ИИ",
            "Производитель (целевой)",
            "Производитель (найденный)",
            "Совпадение производителей",
            "2025+",
            "Принят для НМЦК",
            "Ссылка на контракт",
        ]
        
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # Data rows
        for row_idx, contract in enumerate(contract_results, start=2):
            ws.cell(row=row_idx, column=1, value=row_idx - 1)  # №
            ws.cell(row=row_idx, column=2, value=contract.reestr_number)
            ws.cell(row=row_idx, column=3, value=contract.sign_date.strftime("%Y-%m-%d"))
            ws.cell(row=row_idx, column=4, value=contract.match_type.value)
            
            # Format price with thousands separator
            if contract.unit_price:
                ws.cell(row=row_idx, column=5, value=contract.unit_price)
                ws.cell(row=row_idx, column=5).number_format = '#,##0.00'
            else:
                ws.cell(row=row_idx, column=5, value="Не указана")
            
            ws.cell(row=row_idx, column=6, value=contract.currency)
            ws.cell(row=row_idx, column=7, value=contract.ai_score)
            ws.cell(row=row_idx, column=8, value=contract.manufacturer_target or "")
            ws.cell(row=row_idx, column=9, value=contract.manufacturer_found or "")
            
            # Manufacturer match
            if contract.manufacturer_match is True:
                ws.cell(row=row_idx, column=10, value="Да")
                ws.cell(row=row_idx, column=10).font = Font(color="006400")  # Dark green
            elif contract.manufacturer_match is False:
                ws.cell(row=row_idx, column=10, value="Нет")
                ws.cell(row=row_idx, column=10).font = Font(color="8B0000")  # Dark red
            else:
                ws.cell(row=row_idx, column=10, value="Не определено")
            
            # 2025+
            ws.cell(row=row_idx, column=11, value="Да" if contract.is_2025_plus else "Нет")
            
            # Accepted for NMCK
            if contract.accepted_for_nmc:
                ws.cell(row=row_idx, column=12, value="Да")
                ws.cell(row=row_idx, column=12).font = Font(color="006400", bold=True)
            else:
                ws.cell(row=row_idx, column=12, value="Нет")
                ws.cell(row=row_idx, column=12).font = Font(color="8B0000")
            
            # Contract URL
            ws.cell(row=row_idx, column=13, value=contract.contract_url)
        
        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # Freeze header row
        ws.freeze_panes = "A2"
    
    def _create_comparison_sheet(self, wb: Workbook, contract_results: List[ContractResult],
                                spec_comparisons: Dict[str, List[SpecComparisonRow]]) -> None:
        """Create comparison sheet with detailed spec comparison for selected contracts."""
        ws = wb.create_sheet(title="Сравнение характеристик")
        
        # Get contracts that have spec comparisons
        contracts_with_specs = [
            cr for cr in contract_results 
            if cr.id in spec_comparisons and spec_comparisons[cr.id]
        ]
        
        if not contracts_with_specs:
            ws['A1'] = "Нет данных для сравнения характеристик"
            ws['A1'].font = Font(bold=True, color="FF0000")
            return
        
        # Create a section for each contract
        current_row = 1
        
        for contract in contracts_with_specs:
            # Contract header
            ws.cell(row=current_row, column=1, 
                   value=f"Контракт: {contract.reestr_number} ({contract.match_type.value})")
            ws.cell(row=current_row, column=1).font = Font(bold=True, size=12)
            ws.merge_cells(f'A{current_row}:E{current_row}')
            current_row += 1
            
            # Subheaders
            subheaders = ["Характеристика", "Целевое значение", "Фактическое значение", 
                         "Статус совпадения", "Вес"]
            
            for col_idx, header in enumerate(subheaders, start=1):
                cell = ws.cell(row=current_row, column=col_idx, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="E6E6FA", end_color="E6E6FA", fill_type="solid")
            
            current_row += 1
            
            # Spec comparison rows
            specs = spec_comparisons.get(contract.id, [])
            for spec in specs:
                ws.cell(row=current_row, column=1, value=spec.name)
                ws.cell(row=current_row, column=2, value=spec.target_value or "")
                ws.cell(row=current_row, column=3, value=spec.actual_value or "")
                
                # Match status with color coding
                status_cell = ws.cell(row=current_row, column=4, value=spec.match_status.value)
                if spec.match_status.value == "MATCH":
                    status_cell.font = Font(color="006400")  # Dark green
                elif spec.match_status.value == "DIFF":
                    status_cell.font = Font(color="8B0000")  # Dark red
                else:
                    status_cell.font = Font(color="696969")  # Dim gray
                
                ws.cell(row=current_row, column=5, value=spec.weight)
                current_row += 1
            
            # Add empty row between contracts
            current_row += 1
        
        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width