# Copyright (c) 2026, SWE Pioneers and contributors
# For license information, please see license.txt
"""Standalone tests for the COA importer's ODS reader.

No site/bench required (the reader is stdlib-only), so ODS parsing is verified in
CI without a running ERPNext:

    python -m unittest erpnext/accounts/doctype/chart_of_accounts_importer/test_ods_reader.py
"""
import importlib.util
import io
import os
import unittest
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
# Load by path so the test doesn't import the frappe-coupled erpnext package.
_spec = importlib.util.spec_from_file_location("_coa_ods_reader", os.path.join(_HERE, "ods_reader.py"))
ods = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ods)

# Flat ODF content.xml exercising: trailing repeated filler, float vs string,
# rows-repeated, an internal empty gap, and a merged/covered cell.
_CONTENT = (
	'<?xml version="1.0" encoding="UTF-8"?>'
	'<office:document-content'
	' xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
	' xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"'
	' xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
	'<office:body><office:spreadsheet>'
	'<table:table table:name="Data">'
	'<table:table-row>'
	'<table:table-cell office:value-type="string"><text:p>Name</text:p></table:table-cell>'
	'<table:table-cell office:value-type="string"><text:p>Qty</text:p></table:table-cell>'
	'<table:table-cell table:number-columns-repeated="1020"/>'
	'</table:table-row>'
	'<table:table-row>'
	'<table:table-cell office:value-type="string"><text:p>Cash</text:p></table:table-cell>'
	'<table:table-cell office:value-type="float" office:value="5"><text:p>5</text:p></table:table-cell>'
	'</table:table-row>'
	'<table:table-row table:number-rows-repeated="2">'
	'<table:table-cell office:value-type="string"><text:p>Dup</text:p></table:table-cell>'
	'<table:table-cell/>'
	'<table:table-cell office:value-type="string"><text:p>X</text:p></table:table-cell>'
	'</table:table-row>'
	'<table:table-row>'
	'<table:covered-table-cell/>'
	'<table:table-cell office:value-type="string"><text:p>Merged</text:p></table:table-cell>'
	'</table:table-row>'
	'</table:table>'
	'<table:table table:name="Second">'
	'<table:table-row>'
	'<table:table-cell office:value-type="string"><text:p>only</text:p></table:table-cell>'
	'</table:table-row>'
	'</table:table>'
	'</office:spreadsheet></office:body>'
	'</office:document-content>'
).encode("utf-8")


def _zipped(content):
	buf = io.BytesIO()
	with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
		zf.writestr("content.xml", content)
	return buf.getvalue()


class TestOdsReader(unittest.TestCase):
	def test_sheets_and_order(self):
		self.assertEqual(list(ods.read_ods(_CONTENT)), ["Data", "Second"])

	def test_row_parsing(self):
		self.assertEqual(
			ods.read_ods(_CONTENT)["Data"],
			[
				["Name", "Qty", ""],   # trailing 1020-col filler trimmed; padded to width 3
				["Cash", 5.0, ""],     # float cell -> number
				["Dup", "", "X"],      # rows-repeated -> duplicated; internal empty kept
				["Dup", "", "X"],
				["", "Merged", ""],    # covered/merged cell -> empty
			],
		)

	def test_float_typing(self):
		self.assertIsInstance(ods.read_ods(_CONTENT)["Data"][1][1], float)

	def test_attached_file_helper_first_sheet(self):
		self.assertEqual(ods.read_ods_file_from_attached_file(fcontent=_CONTENT)[0], ["Name", "Qty", ""])

	def test_zip_package_path(self):
		self.assertEqual(ods.read_ods_file_from_attached_file(fcontent=_zipped(_CONTENT))[1], ["Cash", 5.0, ""])

	def test_sheet_by_name_and_index(self):
		self.assertEqual(ods.read_ods_sheet(_CONTENT, "Second"), [["only"]])
		self.assertEqual(ods.read_ods_sheet(_CONTENT, 1), [["only"]])


if __name__ == "__main__":
	unittest.main(verbosity=2)
