# Copyright (c) 2024, oms and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class oms_yyy(Document):
	def default_list_data():
		columns = [
			{
				'label': 'Họ và Tên',
				'type': 'Data',
				'key': 'ho_va_ten',
				'width': '16rem'
			},
		]

		rows = [
			"ho_va_ten",
			"name"
		]
		return {'columns': columns, 'rows': rows}
