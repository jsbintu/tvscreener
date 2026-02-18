"""
Bubby Vision — SEC EDGAR Data Client (via EdgarTools)

Provides SEC filings (10-K, 10-Q, 8-K), insider trading (Form 4),
and XBRL financial data.

No API key required. MIT license.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import structlog

from app.models import FilingData

log = structlog.get_logger(__name__)


class EdgarClient:
    """Wrapper around the edgartools library for SEC EDGAR data."""

    def get_company_filings(
        self,
        ticker: str,
        form_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[FilingData]:
        """Fetch SEC filings for a company.

        Args:
            ticker: Stock ticker symbol.
            form_type: Filter by form type (10-K, 10-Q, 8-K, 4, etc.)
            limit: Max filings to return.
        """
        try:
            from edgar import Company

            company = Company(ticker.upper())
            filings = company.get_filings()

            if form_type:
                filings = filings.filter(form=form_type)

            results = []
            for filing in filings[:limit]:
                is_insider = filing.form in ("3", "4", "5")
                results.append(
                    FilingData(
                        ticker=ticker.upper(),
                        form_type=filing.form,
                        filed_date=filing.filing_date,
                        description=str(filing.description) if hasattr(filing, "description") else None,
                        url=filing.filing_url if hasattr(filing, "filing_url") else "",
                        is_insider_trade=is_insider,
                    )
                )
            return results

        except ImportError:
            return []
        except Exception as e:
            log.warning("edgar.fetch_error", ticker=ticker, error=str(e))
            return []

    def get_insider_trades(self, ticker: str, limit: int = 20) -> list[FilingData]:
        """Fetch insider trading (Form 4) filings."""
        return self.get_company_filings(ticker, form_type="4", limit=limit)

    def get_annual_reports(self, ticker: str, limit: int = 5) -> list[FilingData]:
        """Fetch 10-K annual reports."""
        return self.get_company_filings(ticker, form_type="10-K", limit=limit)

    def get_quarterly_reports(self, ticker: str, limit: int = 10) -> list[FilingData]:
        """Fetch 10-Q quarterly reports."""
        return self.get_company_filings(ticker, form_type="10-Q", limit=limit)

    def get_material_events(self, ticker: str, limit: int = 10) -> list[FilingData]:
        """Fetch 8-K material event filings."""
        return self.get_company_filings(ticker, form_type="8-K", limit=limit)

    def get_financials(self, ticker: str) -> dict:
        """Fetch XBRL financial data from the latest 10-K filing."""
        try:
            from edgar import Company

            company = Company(ticker.upper())
            filings = company.get_filings().filter(form="10-K")

            if not filings:
                return {}

            latest = filings[0]
            xbrl = latest.xbrl()
            if not xbrl:
                return {}

            return {
                "revenue": xbrl.get("Revenues") or xbrl.get("RevenueFromContractWithCustomerExcludingAssessedTax"),
                "net_income": xbrl.get("NetIncomeLoss"),
                "total_assets": xbrl.get("Assets"),
                "total_liabilities": xbrl.get("Liabilities"),
                "stockholders_equity": xbrl.get("StockholdersEquity"),
                "eps_basic": xbrl.get("EarningsPerShareBasic"),
                "eps_diluted": xbrl.get("EarningsPerShareDiluted"),
                "shares_outstanding": xbrl.get("CommonStockSharesOutstanding"),
                # Phase 6 — expanded XBRL fields
                "gross_profit": xbrl.get("GrossProfit"),
                "operating_income": xbrl.get("OperatingIncomeLoss"),
                "cost_of_revenue": xbrl.get("CostOfGoodsAndServicesSold") or xbrl.get("CostOfRevenue"),
                "research_development": xbrl.get("ResearchAndDevelopmentExpense"),
                "sga_expense": xbrl.get("SellingGeneralAndAdministrativeExpense"),
                "operating_cash_flow": xbrl.get("NetCashProvidedByUsedInOperatingActivities"),
                "capex": xbrl.get("PaymentsToAcquirePropertyPlantAndEquipment"),
                "cash_and_equivalents": xbrl.get("CashAndCashEquivalentsAtCarryingValue"),
                "long_term_debt": xbrl.get("LongTermDebt") or xbrl.get("LongTermDebtNoncurrent"),
                "short_term_debt": xbrl.get("ShortTermBorrowings"),
                "total_debt": (
                    (xbrl.get("LongTermDebt") or xbrl.get("LongTermDebtNoncurrent") or 0)
                    + (xbrl.get("ShortTermBorrowings") or 0)
                ) or None,
                "dividends_paid": xbrl.get("PaymentsOfDividends"),
                "retained_earnings": xbrl.get("RetainedEarningsAccumulatedDeficit"),
            }

        except Exception as e:
            log.warning("edgar.xbrl_error", ticker=ticker, error=str(e))
            return {}

    # ── Phase 6: Multi-period XBRL ──

    def _extract_xbrl_fields(self, xbrl) -> dict:
        """Extract standardized financial fields from an XBRL document."""
        if not xbrl:
            return {}
        return {
            "revenue": xbrl.get("Revenues") or xbrl.get("RevenueFromContractWithCustomerExcludingAssessedTax"),
            "net_income": xbrl.get("NetIncomeLoss"),
            "gross_profit": xbrl.get("GrossProfit"),
            "operating_income": xbrl.get("OperatingIncomeLoss"),
            "eps_basic": xbrl.get("EarningsPerShareBasic"),
            "eps_diluted": xbrl.get("EarningsPerShareDiluted"),
            "total_assets": xbrl.get("Assets"),
            "total_liabilities": xbrl.get("Liabilities"),
            "stockholders_equity": xbrl.get("StockholdersEquity"),
            "operating_cash_flow": xbrl.get("NetCashProvidedByUsedInOperatingActivities"),
        }

    def get_multi_year_financials(self, ticker: str, years: int = 5) -> list[dict]:
        """Fetch XBRL financials across multiple 10-K filings for trend analysis.

        Args:
            ticker: Stock ticker symbol.
            years: Number of annual filings to retrieve (default 5).
        """
        try:
            from edgar import Company

            company = Company(ticker.upper())
            filings = company.get_filings().filter(form="10-K")

            results = []
            for filing in filings[:years]:
                try:
                    xbrl = filing.xbrl()
                    fields = self._extract_xbrl_fields(xbrl)
                    if fields:
                        fields["period"] = str(filing.filing_date) if hasattr(filing, "filing_date") else "N/A"
                        fields["form"] = "10-K"
                        results.append(fields)
                except Exception:
                    continue
            return results

        except Exception as e:
            log.warning("edgar.multi_year_error", ticker=ticker, error=str(e))
            return []

    def get_quarterly_financials(self, ticker: str, quarters: int = 8) -> list[dict]:
        """Fetch XBRL financials from 10-Q filings for quarterly trend analysis.

        Args:
            ticker: Stock ticker symbol.
            quarters: Number of quarterly filings to retrieve (default 8).
        """
        try:
            from edgar import Company

            company = Company(ticker.upper())
            filings = company.get_filings().filter(form="10-Q")

            results = []
            for filing in filings[:quarters]:
                try:
                    xbrl = filing.xbrl()
                    fields = self._extract_xbrl_fields(xbrl)
                    if fields:
                        fields["period"] = str(filing.filing_date) if hasattr(filing, "filing_date") else "N/A"
                        fields["form"] = "10-Q"
                        results.append(fields)
                except Exception:
                    continue
            return results

        except Exception as e:
            log.warning("edgar.quarterly_error", ticker=ticker, error=str(e))
            return []

