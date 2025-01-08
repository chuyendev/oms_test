import frappe

@frappe.whitelist()
def get_field_child_record(doctype):
	# Lấy danh sách tất cả các field trong doctype
	fields = frappe.get_meta(doctype).fields
	list_infor_column = []

	current_section = None
	current_column = None

	for field in fields:
		if field.fieldtype == 'Section Break':
			# Thêm section trước đó nếu có
			if current_section:
				if current_column:  # Thêm column cuối cùng vào section trước đó nếu có
					current_section['columns'].append(current_column)
				list_infor_column.append(current_section)

			# Tạo section mới
			current_section = {
				'label': field.label,
				'columns': []
			}
			current_column = None  # Reset column khi tạo section mới

		elif field.fieldtype == 'Column Break':
			# Thêm column trước đó vào section hiện tại
			if current_column and current_section:
				current_section['columns'].append(current_column)

			# Tạo column mới
			current_column = {
				'fields': []
			}

		elif current_section and field.label:  # Chỉ xử lý nếu field có label hợp lệ
			# Tạo dữ liệu của field
			field_data = {
				'label': field.label,
				'name': field.fieldname,
				'type': field.fieldtype,
				'options': field.options,
				'mandatory': field.reqd,
			}

			# Nếu field là 'Select', xử lý options
			if field.fieldtype == "Select" and field.options:
				options = field.options.split("\n")
				field_data['options'] = [{"label": option, "value": option} for option in options]
				field_data['options'].insert(0, {"label": "", "value": ""})

			# Thêm field vào column hiện tại
			if current_column:
				current_column['fields'].append(field_data)
			else:
				# Nếu chưa có column thì tạo column đầu tiên trong section
				current_column = {
					'fields': [field_data]
				}

	# Thêm column cuối cùng vào section nếu có
	if current_column and current_section:
		current_section['columns'].append(current_column)

	# Thêm section cuối cùng vào danh sách nếu có
	if current_section:
		list_infor_column.append(current_section)

	return list_infor_column

@frappe.whitelist()
def get_child_record(parent_doctype, parent_name, child_table_field, child_name):
	# Lấy tài liệu cha (parent document)
	parent_doc = frappe.get_doc(parent_doctype, parent_name)
	
	# Lấy bảng con dựa trên tên trường bảng con (child_table_field)
	child_table = parent_doc.get(child_table_field)

	# Kiểm tra và tìm bản ghi con theo child_name
	for row in child_table:
		if row.name == child_name:
			# Nếu tìm thấy, trả về dữ liệu của bản ghi con
			return row.as_dict()

	# Nếu không tìm thấy bản ghi con, báo lỗi
	frappe.throw(f"No child record found with name {child_name} in {child_table_field}")
	
@frappe.whitelist()
def delete_child_record(parent_doctype, parent_name, child_table_field, child_name):
	# Lấy tài liệu cha (parent document)
	parent_doc = frappe.get_doc(parent_doctype, parent_name)
	
	# Lọc danh sách các bản ghi con trong bảng con dựa trên child_name
	child_table = parent_doc.get(child_table_field)  # Sử dụng tên trường bảng con, không phải tên Doctype
	if not child_table:
		frappe.throw(f"No child table {child_table_field} found in {parent_doctype}")

	for row in child_table:
		if row.name == child_name:
			# Xóa bản ghi con
			parent_doc.remove(row)
			break
	else:
		frappe.throw(f"No child record found with name {child_name} in {child_table_field}")

	# Lưu lại tài liệu cha để cập nhật dữ liệu
	parent_doc.save()
	frappe.db.commit()  # Đảm bảo rằng thay đổi được ghi vào cơ sở dữ liệu

	return {"status": "success", "message": f"Deleted {child_table_field} with name {child_name}"}


@frappe.whitelist()
def update_child_record(parent_doctype, parent_name, child_table_field, child_name, updates):
	"""
	Cập nhật một bản ghi con trong bảng con của tài liệu cha.
	
	:param parent_doctype: Doctype của tài liệu cha
	:param parent_name: Tên của tài liệu cha
	:param child_table_field: Tên của trường bảng con trong tài liệu cha
	:param child_name: Tên của bản ghi con cần cập nhật
	:param updates: Dữ liệu cần cập nhật (dạng dictionary)
	"""
	# Lấy tài liệu cha (parent document)
	parent_doc = frappe.get_doc(parent_doctype, parent_name)
	
	# Lấy bảng con dựa trên tên trường bảng con (child_table_field)
	child_table = parent_doc.get(child_table_field)

	# Tìm bản ghi con trong bảng con và cập nhật dữ liệu
	for row in child_table:
		if row.name == child_name:
			for field, value in updates.items():
				if hasattr(row, field):
					setattr(row, field, value)
			break
	else:
		frappe.throw(f"Child record {child_name} not found in {child_table_field}")

	# Lưu tài liệu cha để ghi thay đổi
	parent_doc.save()
	frappe.db.commit()

	return {"status": "success", "message": f"Updated {child_table_field} with name {child_name}"}

@frappe.whitelist()
def get_dynamic_data(parent_name, parenttype):
	"""
	Lấy dữ liệu từ tất cả các bảng con của một Doctype cha.

	:param doctype: Tên của Doctype (không sử dụng trong hàm này).
	:param parent_name: ID của bản ghi Doctype cha.
	:param parenttype: Tên của Doctype cha.
	:return: Danh sách chứa thông tin `columns`, `rows` và `child_fieldname` của tất cả bảng con.
	"""
	# Lấy meta thông tin của Doctype cha để xác định các bảng con
	meta = frappe.get_meta(parenttype)

	# Xác định tất cả các bảng con (doctypes) thông qua trường Table
	child_tables = [
		(df.fieldname, df.options)  # Bao gồm cả fieldname và options
		for df in meta.fields
		if df.fieldtype in ["Table"] and df.options
	]

	result = []

	for child_fieldname, child_doctype in child_tables:
		# Nếu không có fields, lấy tất cả các trường
		fields = [
			d.fieldname
			for d in frappe.get_meta(child_doctype).fields
			if d.fieldtype not in ["Section Break", "Column Break", "Tab Break"]
		]

		# Lấy các bản ghi từ bảng con
		records = frappe.get_all(
			child_doctype,
			filters={"parent": parent_name, "parenttype": parenttype},
			fields=['*']
		)

		# Tạo cấu trúc dữ liệu cho columns
		columns = []
		for field in fields:
			field_meta = frappe.get_meta(child_doctype).get_field(field)
			columns.append({
				"label": field_meta.label,
				"key": field,
				"fieldtype": field_meta.fieldtype,
				"doctype": child_doctype
			})

		# Thêm dữ liệu bảng con vào kết quả
		result.append({
			"doctype": child_doctype,
			"child_fieldname": child_fieldname,  # Thêm fieldname đại diện cho bảng con
			"columns": columns,
			"rows": records
		})

	return result

@frappe.whitelist()
def add_child_record(id, doctype, parentfield, **fields):
	"""
	Hàm thêm bản ghi mới vào bảng con của một tài liệu (Doctype chính).
	
	Args:
		id (str): Tên của tài liệu chính (ví dụ: nhân viên).
		doctype (str): Doctype của tài liệu cha (ví dụ: Ivan_Employee).
		parentfield (str): Trường bảng con (ví dụ: "table_uruo").
		**fields: Các trường động được truyền vào cho bản ghi cần thêm.
		
	Returns:
		bool: True nếu thêm bản ghi thành công.
	"""
	
	# Kiểm tra quyền ghi lên Doctype cha
	if not frappe.has_permission(doctype, "write", id):
		frappe.throw(_("Not allowed to add record to {0}".format(doctype)), frappe.PermissionError)

	# Lấy tài liệu Doctype cha dựa trên id ID
	parent_doc = frappe.get_cached_doc(doctype, id)
	
	# Thêm bản ghi mới vào bảng con
	parent_doc.append(parentfield, fields)

	# Lưu tài liệu để cập nhật dữ liệu
	parent_doc.save()

	return True


