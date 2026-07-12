# Copyright (c) 2026, SWE Pioneers and contributors
# For license information, please see license.txt
"""OpenDocument spreadsheet (.ods / .fods) reader for the Chart of Accounts Importer.

Frappe's ``xlsxutils`` covers XLSX/XLS; this adds OpenDocument Format support so
``.ods`` files import the same way. Standard library only (no odfpy / pandas), and
it returns the same list-of-rows shape as ``read_xlsx_file_from_attached_file`` so
it drops straight into ``generate_data_from_excel``.

Handles ``.ods``/``.odf`` (zipped ``content.xml``) and ``.fods`` (flat XML), plus
the fiddly ODF bits: repeated cells/rows, internal empty gaps vs trailing filler,
merged/covered cells, and numeric-vs-text cell typing.
"""
from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile

_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"

_Q_TABLE = "{%s}table" % _TABLE
_Q_ROW = "{%s}table-row" % _TABLE
_Q_CELL = "{%s}table-cell" % _TABLE
_Q_COVERED = "{%s}covered-table-cell" % _TABLE
_Q_P = "{%s}p" % _TEXT
_A_NAME = "{%s}name" % _TABLE
_A_COLS_REP = "{%s}number-columns-repeated" % _TABLE
_A_ROWS_REP = "{%s}number-rows-repeated" % _TABLE
_A_VALTYPE = "{%s}value-type" % _OFFICE
_A_VALUE = "{%s}value" % _OFFICE
_A_BOOL = "{%s}boolean-value" % _OFFICE
_A_DATE = "{%s}date-value" % _OFFICE
_A_TIME = "{%s}time-value" % _OFFICE

# Bounds so a pathological repeated-empty run can't blow up memory.
_MAX_COLS = 1024
_MAX_ROWS = 1048576


def _content_xml(source):
	if isinstance(source, (bytes, bytearray)):
		data = bytes(source)
	else:
		with open(source, "rb") as fh:
			data = fh.read()
	if data[:2] == b"PK":  # packaged ODF is a zip; flat .fods is raw XML
		with zipfile.ZipFile(io.BytesIO(data)) as zf:
			return zf.read("content.xml")
	return data


def _cell_text(cell):
	# Direct-child paragraphs only (avoids <office:annotation> comment text).
	parts = []
	for child in cell:
		if child.tag == _Q_P:
			parts.append("".join(child.itertext()))
	return "\n".join(parts)


def _cell_value(cell):
	vtype = cell.get(_A_VALTYPE)
	if vtype in ("float", "percentage", "currency"):
		try:
			return float(cell.get(_A_VALUE))
		except (TypeError, ValueError):
			return _cell_text(cell)
	if vtype == "boolean":
		return 1.0 if cell.get(_A_BOOL) == "true" else 0.0
	if vtype == "date":
		return cell.get(_A_DATE) or _cell_text(cell)
	if vtype == "time":
		return cell.get(_A_TIME) or _cell_text(cell)
	return _cell_text(cell)


def _is_empty_cell(cell):
	return cell.get(_A_VALTYPE) is None and len(cell) == 0


def _parse_row(row_el):
	out = []
	pending = 0
	for cell in row_el:
		if cell.tag not in (_Q_CELL, _Q_COVERED):
			continue
		rep = int(cell.get(_A_COLS_REP, "1") or "1")
		rep = max(1, min(rep, _MAX_COLS))
		if cell.tag == _Q_COVERED or _is_empty_cell(cell):
			pending += rep
			continue
		if pending:
			out.extend([""] * pending)
			pending = 0
		out.extend([_cell_value(cell)] * rep)
		if len(out) >= _MAX_COLS:
			return out[:_MAX_COLS]
	return out  # trailing pending is filler -> dropped


def read_ods(source):
	"""Parse all sheets -> ``{sheet_name: [[cell, ...], ...]}``."""
	root = ET.fromstring(_content_xml(source))
	sheets = {}
	for table in root.iter(_Q_TABLE):
		name = table.get(_A_NAME) or ("Sheet%d" % (len(sheets) + 1))
		rows = []
		pending_blank = 0
		for row_el in table.iter(_Q_ROW):
			rrep = int(row_el.get(_A_ROWS_REP, "1") or "1")
			rrep = max(1, min(rrep, _MAX_ROWS))
			cells = _parse_row(row_el)
			if not cells:
				pending_blank += rrep
				continue
			if pending_blank:
				rows.extend([] for _ in range(pending_blank))
				pending_blank = 0
			for _ in range(rrep):
				rows.append(list(cells))
			if len(rows) >= _MAX_ROWS:
				break
		width = max((len(r) for r in rows), default=0)
		for r in rows:
			if len(r) < width:
				r.extend([""] * (width - len(r)))
		sheets[name] = rows
	return sheets


def read_ods_sheet(source, sheet=None):
	"""Rows of one sheet: by name, 0-based index, or the first sheet (default)."""
	sheets = read_ods(source)
	if sheet is None:
		return next(iter(sheets.values()), [])
	if isinstance(sheet, int):
		return list(sheets.values())[sheet]
	return sheets[sheet]


def read_ods_file_from_attached_file(fcontent=None, filepath=None):
	"""Mirror of ``read_xlsx_file_from_attached_file`` — the first sheet's rows.

	Pass ``fcontent`` (bytes, as the COA importer does) or a ``filepath``.
	"""
	source = fcontent if fcontent is not None else filepath
	return read_ods_sheet(source)
