"""
ArynoxTech AI Agent - Tally ERP 9/Prime Integration Tool
========================================================
Connects to Tally via HTTP XML API (port 9000) for accounting
data export/import, master management, voucher operations,
report generation, and Excel export.
"""

import time
import os
import re
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from tools.base_tool import BaseTool, ToolResult
from config.settings import BASE_DIR, TOOL_CONFIG, DIRS
from utils.logger import get_logger

logger = get_logger(__name__)

REPORTS_DIR = Path("reports")


def _build_tally_request(report_name: str, extra_vars: Optional[Dict[str, str]] = None) -> str:
    vars_xml = ""
    if extra_vars:
        vars_xml = "".join(f"<{k}>{v}</{k}>" for k, v in extra_vars.items())
    return f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY>
<EXPORTDATA>
<REQUESTDESC>
<REPORTNAME>{report_name}</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{vars_xml}
</STATICVARIABLES>
</REQUESTDESC>
</EXPORTDATA>
</BODY>
</ENVELOPE>"""


def _build_voucher_request(
    voucher_type: str,
    from_date: str,
    to_date: str,
    ledger: Optional[str] = None,
) -> str:
    ledger_filter = f"<SVCURRENTLEDGERNAME>{ledger}</SVCURRENTLEDGERNAME>" if ledger else ""
    return f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY>
<EXPORTDATA>
<REQUESTDESC>
<REPORTNAME>Accountbooks.VoucherRegister</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<SVCURRENTVOUCHERTYPENAME>{voucher_type}</SVCURRENTVOUCHERTYPENAME>
<SVFROMDATE>{from_date}</SVFROMDATE>
<SVTODATE>{to_date}</SVTODATE>
{ledger_filter}
</STATICVARIABLES>
</REQUESTDESC>
</EXPORTDATA>
</BODY>
</ENVELOPE>"""


def _build_import_request(xml_payload: str) -> str:
    return f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY>
<IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>All Masters</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
{xml_payload}
</REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>"""


def _parse_xml_response(xml_str: str) -> List[Dict[str, Any]]:
    records = []
    try:
        root = ET.fromstring(xml_str)
        for tally_msg in root.iter("TALLYMESSAGE"):
            for elem in tally_msg:
                rec = {"_type": elem.tag}
                rec.update(_flatten_element(elem))
                records.append(rec)
        if not records:
            for elem in root.iter():
                if elem.tag != "ENVELOPE" and elem.tag != "BODY":
                    rec = {"_type": elem.tag}
                    rec.update(_flatten_element(elem))
                    if len(rec) > 1:
                        records.append(rec)
    except Exception:
        pass
    return records


def _flatten_element(elem: ET.Element, prefix: str = "") -> Dict[str, Any]:
    result = {}
    for child in elem:
        tag = f"{prefix}{child.tag}"
        if child.text and child.text.strip():
            result[tag] = child.text.strip()
        if child.attrib:
            for k, v in child.attrib.items():
                result[f"{tag}.{k}"] = v
        if len(child) > 0:
            result.update(_flatten_element(child, f"{tag}."))
    if elem.attrib:
        for k, v in elem.attrib.items():
            result[f"@{k}"] = v
    return result


def _send_tally_request(xml_body: str, host: str = "localhost", port: int = 9000, timeout: int = 30) -> Optional[str]:
    try:
        import http.client
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        headers = {"Content-Type": "application/xml"}
        conn.request("POST", "/", xml_body.encode("utf-8"), headers)
        response = conn.getresponse()
        data = response.read().decode("utf-8")
        conn.close()
        return data
    except Exception as e:
        logger.error(f"Tally connection failed: {e}")
        return None


def _dicts_to_excel(data: List[Dict[str, Any]], sheet_name: str = "TallyData") -> Optional[Path]:
    try:
        import pandas as pd
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r"[^\w]", "_", sheet_name)[:30]
        path = reports_dir / f"tally_{safe_name}_{timestamp}.xlsx"
        df = pd.DataFrame(data)
        df.to_excel(path, index=False, engine="openpyxl")
        logger.info(f"Exported {len(data)} records to {path}")
        return path
    except Exception as e:
        logger.error(f"Excel export failed: {e}")
        return None


class TallyTool(BaseTool):
    """
    Tally ERP 9/Prime integration tool for accounting operations.
    Connects via HTTP XML API on port 9000 to export/import masters,
    vouchers, reports, and export data to Excel.
    """

    name: str = "tally_tool"
    description: str = (
        "Tally ERP 9/Prime integration: export ledgers, groups, stock items, "
        "vouchers (sales/purchase/payment/receipt/contra/journal), balance sheet, "
        "P&L, trial balance, day book, outstanding reports, create masters/vouchers, "
        "and export Tally data to Excel. Tally must be running with port 9000 enabled."
    )
    version: str = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        config = TOOL_CONFIG.get("tally", {})
        self.host: str = config.get("host", "localhost")
        self.port: int = config.get("port", 9000)
        self.timeout: int = config.get("timeout", 30)

        self.supported_actions = {
            "check_connection": self._check_connection,
            "get_ledgers": self._get_ledgers,
            "get_groups": self._get_groups,
            "get_voucher_types": self._get_voucher_types,
            "get_vouchers": self._get_vouchers,
            "get_stock_items": self._get_stock_items,
            "get_stock_groups": self._get_stock_groups,
            "get_cost_centres": self._get_cost_centres,
            "get_godowns": self._get_godowns,
            "get_balance_sheet": self._get_balance_sheet,
            "get_profit_loss": self._get_profit_loss,
            "get_trial_balance": self._get_trial_balance,
            "get_day_book": self._get_day_book,
            "get_outstandings": self._get_outstandings,
            "get_stock_summary": self._get_stock_summary,
            "create_ledger": self._create_ledger,
            "create_voucher": self._create_voucher,
            "export_to_excel": self._export_to_excel,
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        start = time.time()
        action = kwargs.get("action", "check_connection")

        try:
            handler = self.supported_actions.get(action)
            if handler is None:
                return ToolResult.failure(
                    f"Unknown action: {action}. Available: {list(self.supported_actions.keys())}",
                    execution_time_ms=(time.time() - start) * 1000,
                )
            return await handler(kwargs, start)
        except Exception as e:
            logger.exception(f"Tally tool error: {e}")
            return ToolResult.error_result(
                f"Tally operation failed: {e}",
                execution_time_ms=(time.time() - start) * 1000,
            )

    def _send(self, xml_body: str) -> Optional[str]:
        return _send_tally_request(xml_body, self.host, self.port, self.timeout)

    # ── Connection ──────────────────────────────────────────────────────

    async def _check_connection(self, kwargs: Dict, start: float) -> ToolResult:
        xml = _build_tally_request("Ledger")
        response = self._send(xml)
        if response and "LEDGER" in response:
            return ToolResult.success(
                "Tally is connected and responding.",
                data={"connected": True, "host": self.host, "port": self.port},
                execution_time_ms=(time.time() - start) * 1000,
            )
        return ToolResult.failure(
            f"Tally not reachable at {self.host}:{self.port}. "
            "Ensure Tally is running with 'Allow Tally to connect via HTTP' enabled "
            "(Gateway of Tally > F12 Configure > Mail & Infra > Allow Tally to connect via HTTP).",
            execution_time_ms=(time.time() - start) * 1000,
        )

    # ── Masters ─────────────────────────────────────────────────────────

    async def _get_ledgers(self, kwargs: Dict, start: float) -> ToolResult:
        xml = _build_tally_request("Ledger")
        response = self._send(xml)
        if not response:
            return ToolResult.failure("No response from Tally.", execution_time_ms=(time.time() - start) * 1000)
        records = _parse_xml_response(response)
        ledgers = [r for r in records if r.get("_type") == "LEDGER"]
        if not ledgers:
            return ToolResult.success("No ledgers found.", data={"ledgers": []}, execution_time_ms=(time.time() - start) * 1000)
        return ToolResult.success(
            f"Found {len(ledgers)} ledgers.",
            data={"ledgers": ledgers, "count": len(ledgers)},
            execution_time_ms=(time.time() - start) * 1000,
        )

    async def _get_groups(self, kwargs: Dict, start: float) -> ToolResult:
        xml = _build_tally_request("Group")
        response = self._send(xml)
        if not response:
            return ToolResult.failure("No response from Tally.", execution_time_ms=(time.time() - start) * 1000)
        records = _parse_xml_response(response)
        groups = [r for r in records if r.get("_type") == "GROUP"]
        return ToolResult.success(
            f"Found {len(groups)} groups.",
            data={"groups": groups, "count": len(groups)},
            execution_time_ms=(time.time() - start) * 1000,
        )

    async def _get_voucher_types(self, kwargs: Dict, start: float) -> ToolResult:
        xml = _build_tally_request("VoucherType")
        response = self._send(xml)
        if not response:
            return ToolResult.failure("No response from Tally.", execution_time_ms=(time.time() - start) * 1000)
        records = _parse_xml_response(response)
        vtypes = [r for r in records if r.get("_type") == "VOUCHERTYPE"]
        return ToolResult.success(
            f"Found {len(vtypes)} voucher types.",
            data={"voucher_types": vtypes, "count": len(vtypes)},
            execution_time_ms=(time.time() - start) * 1000,
        )

    async def _get_stock_items(self, kwargs: Dict, start: float) -> ToolResult:
        xml = _build_tally_request("StockItem")
        response = self._send(xml)
        if not response:
            return ToolResult.failure("No response from Tally.", execution_time_ms=(time.time() - start) * 1000)
        records = _parse_xml_response(response)
        items = [r for r in records if r.get("_type") == "STOCKITEM"]
        return ToolResult.success(
            f"Found {len(items)} stock items.",
            data={"stock_items": items, "count": len(items)},
            execution_time_ms=(time.time() - start) * 1000,
        )

    async def _get_stock_groups(self, kwargs: Dict, start: float) -> ToolResult:
        xml = _build_tally_request("StockGroup")
        response = self._send(xml)
        if not response:
            return ToolResult.failure("No response from Tally.", execution_time_ms=(time.time() - start) * 1000)
        records = _parse_xml_response(response)
        groups = [r for r in records if r.get("_type") == "STOCKGROUP"]
        return ToolResult.success(
            f"Found {len(groups)} stock groups.",
            data={"stock_groups": groups, "count": len(groups)},
            execution_time_ms=(time.time() - start) * 1000,
        )

    async def _get_cost_centres(self, kwargs: Dict, start: float) -> ToolResult:
        xml = _build_tally_request("CostCentre")
        response = self._send(xml)
        if not response:
            return ToolResult.failure("No response from Tally.", execution_time_ms=(time.time() - start) * 1000)
        records = _parse_xml_response(response)
        centres = [r for r in records if r.get("_type") == "COSTCENTRE"]
        return ToolResult.success(
            f"Found {len(centres)} cost centres.",
            data={"cost_centres": centres, "count": len(centres)},
            execution_time_ms=(time.time() - start) * 1000,
        )

    async def _get_godowns(self, kwargs: Dict, start: float) -> ToolResult:
        xml = _build_tally_request("Godown")
        response = self._send(xml)
        if not response:
            return ToolResult.failure("No response from Tally.", execution_time_ms=(time.time() - start) * 1000)
        records = _parse_xml_response(response)
        godowns = [r for r in records if r.get("_type") == "GODOWN"]
        return ToolResult.success(
            f"Found {len(godowns)} godowns.",
            data={"godowns": godowns, "count": len(godowns)},
            execution_time_ms=(time.time() - start) * 1000,
        )

    # ── Vouchers ────────────────────────────────────────────────────────

    async def _get_vouchers(self, kwargs: Dict, start: float) -> ToolResult:
        vtype = kwargs.get("voucher_type", "Sales")
        from_date = kwargs.get("from_date", datetime.now().strftime("%Y%m%d"))
        to_date = kwargs.get("to_date", datetime.now().strftime("%Y%m%d"))
        ledger = kwargs.get("ledger", None)

        xml = _build_voucher_request(vtype, from_date, to_date, ledger)
        response = self._send(xml)
        if not response:
            return ToolResult.failure("No response from Tally.", execution_time_ms=(time.time() - start) * 1000)
        records = _parse_xml_response(response)
        vouchers = [r for r in records if r.get("_type") == "VOUCHER"]
        return ToolResult.success(
            f"Found {len(vouchers)} '{vtype}' vouchers ({from_date} to {to_date}).",
            data={"vouchers": vouchers, "count": len(vouchers), "voucher_type": vtype},
            execution_time_ms=(time.time() - start) * 1000,
        )

    # ── Reports ─────────────────────────────────────────────────────────

    async def _get_balance_sheet(self, kwargs: Dict, start: float) -> ToolResult:
        xml = _build_tally_request("BalanceSheet")
        response = self._send(xml)
        if not response:
            return ToolResult.failure("No response from Tally.", execution_time_ms=(time.time() - start) * 1000)
        records = _parse_xml_response(response)
        return ToolResult.success(
            f"Balance sheet data retrieved ({len(records)} entries).",
            data={"balance_sheet": records},
            execution_time_ms=(time.time() - start) * 1000,
        )

    async def _get_profit_loss(self, kwargs: Dict, start: float) -> ToolResult:
        xml = _build_tally_request("Profit&LossA/c")
        response = self._send(xml)
        if not response:
            return ToolResult.failure("No response from Tally.", execution_time_ms=(time.time() - start) * 1000)
        records = _parse_xml_response(response)
        return ToolResult.success(
            f"Profit & Loss data retrieved ({len(records)} entries).",
            data={"profit_loss": records},
            execution_time_ms=(time.time() - start) * 1000,
        )

    async def _get_trial_balance(self, kwargs: Dict, start: float) -> ToolResult:
        xml = _build_tally_request("TrialBalance")
        response = self._send(xml)
        if not response:
            return ToolResult.failure("No response from Tally.", execution_time_ms=(time.time() - start) * 1000)
        records = _parse_xml_response(response)
        return ToolResult.success(
            f"Trial balance data retrieved ({len(records)} entries).",
            data={"trial_balance": records},
            execution_time_ms=(time.time() - start) * 1000,
        )

    async def _get_day_book(self, kwargs: Dict, start: float) -> ToolResult:
        from_date = kwargs.get("from_date", datetime.now().strftime("%Y%m%d"))
        to_date = kwargs.get("to_date", datetime.now().strftime("%Y%m%d"))
        vars_dict = {"SVFROMDATE": from_date, "SVTODATE": to_date}
        xml = _build_tally_request("DayBook", vars_dict)
        response = self._send(xml)
        if not response:
            return ToolResult.failure("No response from Tally.", execution_time_ms=(time.time() - start) * 1000)
        records = _parse_xml_response(response)
        vouchers = [r for r in records if r.get("_type") == "VOUCHER"]
        return ToolResult.success(
            f"Day book: {len(vouchers)} entries ({from_date} to {to_date}).",
            data={"day_book": vouchers, "count": len(vouchers)},
            execution_time_ms=(time.time() - start) * 1000,
        )

    async def _get_outstandings(self, kwargs: Dict, start: float) -> ToolResult:
        xml = _build_tally_request("Outstandings")
        response = self._send(xml)
        if not response:
            return ToolResult.failure("No response from Tally.", execution_time_ms=(time.time() - start) * 1000)
        records = _parse_xml_response(response)
        return ToolResult.success(
            f"Outstandings retrieved ({len(records)} entries).",
            data={"outstandings": records},
            execution_time_ms=(time.time() - start) * 1000,
        )

    async def _get_stock_summary(self, kwargs: Dict, start: float) -> ToolResult:
        xml = _build_tally_request("StockSummary")
        response = self._send(xml)
        if not response:
            return ToolResult.failure("No response from Tally.", execution_time_ms=(time.time() - start) * 1000)
        records = _parse_xml_response(response)
        return ToolResult.success(
            f"Stock summary retrieved ({len(records)} entries).",
            data={"stock_summary": records},
            execution_time_ms=(time.time() - start) * 1000,
        )

    # ── Create / Import ─────────────────────────────────────────────────

    async def _create_ledger(self, kwargs: Dict, start: float) -> ToolResult:
        name = kwargs.get("name", "")
        group_name = kwargs.get("group_name", "Sundry Debtors")
        opening_balance = kwargs.get("opening_balance", "0")
        if not name:
            return ToolResult.failure("Ledger name is required.", execution_time_ms=(time.time() - start) * 1000)

        ob_type = "Dr" if float(opening_balance) >= 0 else "Cr"
        ob_abs = str(abs(float(opening_balance)))

        xml_payload = f"""<TALLYMESSAGE>
<LEDGER NAME="{name}" ACTION="Create">
<NAME>{name}</NAME>
<PARENT>{group_name}</PARENT>
<OPENINGBALANCE>{ob_abs}</OPENINGBALANCE>
<OPENINGBALANCETYPE>{ob_type}</OPENINGBALANCETYPE>
</LEDGER>
</TALLYMESSAGE>"""
        xml = _build_import_request(xml_payload)
        response = self._send(xml)
        if response and "LINE" in response and "1" in response:
            return ToolResult.success(
                f"Ledger '{name}' created under group '{group_name}'.",
                data={"ledger_name": name, "group": group_name},
                execution_time_ms=(time.time() - start) * 1000,
            )
        return ToolResult.failure(
            f"Failed to create ledger '{name}'. Response: {(response or '')[:200]}",
            execution_time_ms=(time.time() - start) * 1000,
        )

    async def _create_voucher(self, kwargs: Dict, start: float) -> ToolResult:
        vtype = kwargs.get("voucher_type", "Sales")
        date_str = kwargs.get("date", datetime.now().strftime("%Y%m%d"))
        entries = kwargs.get("entries", [])
        if not entries:
            return ToolResult.failure(
                "At least one ledger entry is required. "
                "Provide entries as a list of dicts with 'ledger_name' and 'amount'.",
                execution_time_ms=(time.time() - start) * 1000,
            )

        entry_xml = ""
        for i, entry in enumerate(entries):
            ledger = entry.get("ledger_name", "")
            amount = entry.get("amount", "0")
            is_debit = entry.get("is_debit", True)
            entry_type = "Dr" if is_debit else "Cr"
            entry_xml += f"""<ALLOCENTRIES.LIST>
<LEDGERNAME>{ledger}</LEDGERNAME>
<AMOUNT>{'-' if not is_debit else ''}{amount}</AMOUNT>
</ALLOCENTRIES.LIST>"""

        xml_payload = f"""<TALLYMESSAGE>
<VOUCHER ACTION="Create">
<VOUCHERTYPENAME>{vtype}</VOUCHERTYPENAME>
<DATE>{date_str}</DATE>
{entry_xml}
</VOUCHER>
</TALLYMESSAGE>"""
        xml = _build_import_request(xml_payload)
        response = self._send(xml)
        if response and "LINE" in response:
            return ToolResult.success(
                f"{vtype} voucher created on {date_str} with {len(entries)} entries.",
                data={"voucher_type": vtype, "date": date_str, "entries": entries},
                execution_time_ms=(time.time() - start) * 1000,
            )
        return ToolResult.failure(
            f"Failed to create voucher. Response: {(response or '')[:200]}",
            execution_time_ms=(time.time() - start) * 1000,
        )

    # ── Export to Excel ─────────────────────────────────────────────────

    async def _export_to_excel(self, kwargs: Dict, start: float) -> ToolResult:
        action = kwargs.get("export_action", "ledgers")
        sheet_name = kwargs.get("sheet_name", f"Tally_{action}")

        action_map = {
            "ledgers": ("Ledger", _build_tally_request("Ledger")),
            "groups": ("Group", _build_tally_request("Group")),
            "stock_items": ("StockItem", _build_tally_request("StockItem")),
            "stock_groups": ("StockGroup", _build_tally_request("StockGroup")),
            "cost_centres": ("CostCentre", _build_tally_request("CostCentre")),
            "godowns": ("Godown", _build_tally_request("Godown")),
            "balance_sheet": ("BalanceSheet", _build_tally_request("BalanceSheet")),
            "profit_loss": ("Profit&LossA/c", _build_tally_request("Profit&LossA/c")),
            "trial_balance": ("TrialBalance", _build_tally_request("TrialBalance")),
            "stock_summary": ("StockSummary", _build_tally_request("StockSummary")),
            "outstandings": ("Outstandings", _build_tally_request("Outstandings")),
        }

        if action not in action_map:
            return ToolResult.failure(
                f"Unknown export action: {action}. Available: {list(action_map.keys())}",
                execution_time_ms=(time.time() - start) * 1000,
            )

        label, xml = action_map[action]
        response = self._send(xml)
        if not response:
            return ToolResult.failure(
                f"No response from Tally for {label}.",
                execution_time_ms=(time.time() - start) * 1000,
            )

        records = _parse_xml_response(response)
        target_tag = label.upper().replace("&", "").replace("-", "")
        filtered = [r for r in records if r.get("_type") == target_tag] or records

        path = _dicts_to_excel(filtered, sheet_name)
        if not path:
            return ToolResult.failure(
                "Failed to export to Excel.",
                execution_time_ms=(time.time() - start) * 1000,
            )

        return ToolResult.success(
            f"✅ Exported {len(filtered)} {label} records to Excel.\n📄 File: {path.name}\n📁 Location: {path.parent}",
            data={"path": str(path), "filename": path.name, "record_count": len(filtered), "type": label},
            execution_time_ms=(time.time() - start) * 1000,
        )
