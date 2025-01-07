import frappe
import json
import random
import string

# import xlsxwriter
from frappe import _
from frappe.model.document import get_controller
from frappe.model import no_value_fields
from pypika import Criterion
from frappe.utils import make_filter_tuple
from frappe.permissions import get_role_permissions
from oms.api.views import get_views
from oms.oms.doctype.oms_form_script.oms_form_script import get_form_script

import openpyxl
from frappe.utils.file_manager import save_file

@frappe.whitelist()
def sort_options(doctype: str):
	fields = frappe.get_meta(doctype).fields
	fields = [field for field in fields if field.fieldtype not in no_value_fields]
	fields = [
		{
			"label": _(field.label),
			"value": field.fieldname,
		}
		for field in fields
		if field.label and field.fieldname
	]

	standard_fields = [
		{"label": "Name", "value": "name"},
		{"label": "Created On", "value": "creation"},
		{"label": "Last Modified", "value": "modified"},
		{"label": "Modified By", "value": "modified_by"},
		{"label": "Owner", "value": "owner"},
	]

	for field in standard_fields:
		field["label"] = _(field["label"])
		fields.append(field)

	return fields


@frappe.whitelist()
def get_filterable_fields(doctype: str):
	allowed_fieldtypes = [
		"Check",
		"Data",
		"Float",
		"Int",
		"Currency",
		"Dynamic Link",
		"Link",
		"Long Text",
		"Select",
		"Small Text",
		"Text Editor",
		"Text",
		"Duration",
		"Date",
		"Datetime",
	]
	c = get_controller(doctype)
	restricted_fields = []
	if hasattr(c, "get_non_filterable_fields"):
		restricted_fields = c.get_non_filterable_fields()

	res = []

	# append DocFields
	DocField = frappe.qb.DocType("DocField")
	doc_fields = get_doctype_fields_meta(DocField, doctype, allowed_fieldtypes, restricted_fields)
	res.extend(doc_fields)

	# append Custom Fields
	CustomField = frappe.qb.DocType("Custom Field")
	custom_fields = get_doctype_fields_meta(CustomField, doctype, allowed_fieldtypes, restricted_fields)
	res.extend(custom_fields)

	# append standard fields (getting error when using frappe.model.std_fields)
	standard_fields = [
		{"fieldname": "name", "fieldtype": "Link", "label": "ID", "options": doctype},
		{
			"fieldname": "owner",
			"fieldtype": "Link",
			"label": "Created By",
			"options": "User"
		},
		{
			"fieldname": "modified_by",
			"fieldtype": "Link",
			"label": "Last Updated By",
			"options": "User",
		},
		{"fieldname": "creation", "fieldtype": "Datetime", "label": "Created On"},
		{"fieldname": "modified", "fieldtype": "Datetime", "label": "Last Updated On"},
	]
	for field in standard_fields:
		if (
			field.get("fieldname") not in restricted_fields and
			field.get("fieldtype") in allowed_fieldtypes
		):
			field["name"] = field.get("fieldname")
			res.append(field)

	for field in res:
		field["label"] = _(field.get("label"))

	return res

def get_doctype_fields_meta(DocField, doctype, allowed_fieldtypes, restricted_fields):
	parent = "parent" if DocField._table_name == "tabDocField" else "dt"
	return (
		frappe.qb.from_(DocField)
		.select(
			DocField.fieldname,
			DocField.fieldtype,
			DocField.label,
			DocField.name,
			DocField.options,
		)
		.where(DocField[parent] == doctype)
		.where(DocField.hidden == False)
		.where(Criterion.any([DocField.fieldtype == i for i in allowed_fieldtypes]))
		.where(Criterion.all([DocField.fieldname != i for i in restricted_fields]))
		.run(as_dict=True)
	)

@frappe.whitelist()
def get_list_data(
	doctype: str,
	filters: dict,
	order_by: str,
	page_length=20,
	page_length_count=20,
	column_field=None,
	title_field=None,
	columns=[],
	rows=[],
	kanban_columns=[],
	kanban_fields=[],
	view=None,
	default_filters=None,
	):
	custom_view = False
	filters = frappe._dict(filters)
	rows = frappe.parse_json(rows or "[]")
	columns = frappe.parse_json(columns or "[]")
	kanban_fields = frappe.parse_json(kanban_fields or "[]")
	kanban_columns = frappe.parse_json(kanban_columns or "[]")

	custom_view_name = view.get('custom_view_name') if view else None
	view_type = view.get('view_type') if view else None
	group_by_field = view.get('group_by_field') if view else None

	for key in filters:
		value = filters[key]
		if isinstance(value, list):
			if "@me" in value:
				value[value.index("@me")] = frappe.session.user
			elif "%@me%" in value:
				index = [i for i, v in enumerate(value) if v == "%@me%"]
				for i in index:
					value[i] = "%" + frappe.session.user + "%"
		elif value == "@me":
			filters[key] = frappe.session.user

	if default_filters:
		default_filters = frappe.parse_json(default_filters)
		filters.update(default_filters)

	is_default = True
	data = []
	_list = get_controller(doctype)
	default_rows = []
	if hasattr(_list, "default_list_data"):
		default_rows = _list.default_list_data().get("rows")

	if view_type != "kanban":
		if columns or rows:
			custom_view = True
			is_default = False
			columns = frappe.parse_json(columns)
			rows = frappe.parse_json(rows)

		if not columns:
			columns = [
				{"label": "Name", "type": "Data", "key": "name", "width": "16rem"},
				{"label": "Last Modified", "type": "Datetime", "key": "modified", "width": "8rem"},
			]

		if not rows:
			rows = ["name"]

		default_view_filters = {
			"dt": doctype,
			"type": view_type or 'list',
			"is_default": 1,
			"user": frappe.session.user,
		}

		# if not custom_view and frappe.db.exists("CRM View Settings", default_view_filters):
		# 	list_view_settings = frappe.get_doc("CRM View Settings", default_view_filters)
		# 	columns = frappe.parse_json(list_view_settings.columns)
		# 	rows = frappe.parse_json(list_view_settings.rows)
		# 	is_default = False
		if not custom_view or is_default and hasattr(_list, "default_list_data"):
			rows = default_rows
			columns = _list.default_list_data().get("columns")

		# check if rows has all keys from columns if not add them
		for column in columns:
			if column.get("key") not in rows:
				rows.append(column.get("key"))
			column["label"] = _(column.get("label"))

		# check if rows has group_by_field if not add it
		if group_by_field and group_by_field not in rows:
			rows.append(group_by_field)

		data = frappe.get_list(
			doctype,
			fields=rows,
			filters=filters,
			order_by=order_by,
			page_length=page_length,
		) or []

	fields = frappe.get_meta(doctype).fields
	fields = [field for field in fields if field.fieldtype not in no_value_fields]
	fields = [
		{
			"label": _(field.label),
			"type": field.fieldtype,
			"value": field.fieldname,
			"options": field.options,
		}
		for field in fields
		if field.label and field.fieldname
	]

	std_fields = [
		{"label": "Name", "type": "Data", "value": "name"},
		{"label": "Created On", "type": "Datetime", "value": "creation"},
		{"label": "Last Modified", "type": "Datetime", "value": "modified"},
		{
			"label": "Modified By",
			"type": "Link",
			"value": "modified_by",
			"options": "User",
		},
	]

	for field in std_fields:
		if field.get('value') not in rows:
			rows.append(field.get('value'))
		if field not in fields:
			field["label"] = _(field["label"])
			fields.append(field)

	# if not is_default and custom_view_name:
	# 	is_default = frappe.db.get_value("CRM View Settings", custom_view_name, "load_default_columns")
	return {
		"data": data,
		"columns": columns,
		"rows": rows,
		"fields": fields,
		"column_field": column_field,
		"title_field": title_field,
		"kanban_columns": kanban_columns,
		"kanban_fields": kanban_fields,
		"group_by_field": group_by_field,
		"page_length": page_length,
		"page_length_count": page_length_count,
		"is_default": is_default,
		"views": get_views(doctype),
		"total_count": len(frappe.get_list(doctype, filters=filters)),
		"row_count": len(data),
		"form_script": get_form_script(doctype),
		"list_script": get_form_script(doctype, "List"),
		"view_type": view_type,
	}
@frappe.whitelist()
def get_quick_filters(doctype: str):
	meta = frappe.get_meta(doctype)
	fields = [field for field in meta.fields if field.in_standard_filter]
	quick_filters = []

	for field in fields:

		if field.fieldtype == "Select":
			field.options = field.options.split("\n")
			field.options = [{"label": option, "value": option} for option in field.options]
			field.options.insert(0, {"label": "", "value": ""})
		quick_filters.append({
			"label": _(field.label),
			"name": field.fieldname,
			"type": field.fieldtype,
			"options": field.options,
		})

	# if doctype == "oms_yyy":
	# 	quick_filters = [filter for filter in quick_filters if filter.get("employee_name") != "converted"]

	return quick_filters

# Hàm lấy all field trong doctype (Sử dụng khi trong doctype đó có chia làm các tab)
@frappe.whitelist()
def get_value_modal(doctype):
    # Lấy danh sách tất cả các field trong doctype
    fields = frappe.get_meta(doctype).fields
    list_infor_column = []
    
    current_tab = None
    current_section = None
    current_column = None

    for field in fields:
        # Fix lại và bổ sung những trường nào type là 'Attach Image', 'Table' thì không hiển thị
        if field.fieldtype in ['Attach Image']:
            continue
        if field.name == 'title' :
            continue
        if field.fieldtype == 'Tab Break':
            # Thêm tab trước đó nếu có
            if current_tab:
                if current_section:  # Thêm section trước đó nếu có
                    if current_column:  # Thêm column cuối cùng vào section trước đó nếu có
                        current_section['columns'].append(current_column)
                    current_tab['sections'].append(current_section)
                list_infor_column.append(current_tab)

            # Tạo tab mới
            current_tab = {
                'label': field.label or field.name or 'Untitled',
                "name": field.label or field.name or 'Untitled',
                'sections': []
            }
            current_section = None  # Reset section và column khi tạo tab mới
            current_column = None

        elif field.fieldtype == 'Section Break':
            # Thêm section trước đó vào tab hiện tại
            if current_section:
                if current_column:  # Thêm column cuối cùng vào section trước đó nếu có
                    current_section['columns'].append(current_column)
                current_tab['sections'].append(current_section)

            # Tạo section mới
            current_section = {
                'label': field.label,
                'columns': []
            }
            current_column = None  # Reset column khi tạo section mới

        elif field.fieldtype == 'Column Break':
            # Thêm column trước đó vào section hiện tại
            if current_column:
                current_section['columns'].append(current_column)

            # Tạo column mới
            current_column = {
                'fields': []
            }

        elif current_tab and current_section and field.label:  # Chỉ xử lý nếu field có label hợp lệ

            # Tạo dữ liệu của field
            field_data = {
                'label': _(field.label),
                
                'name': field.fieldname,
                'type': field.fieldtype,
                'options': field.options,
                'mandatory': field.reqd,
                "placeholder": field.label,
                "read_only": field.read_only,
                'hidden' : field.hidden,
                'default': field.default,
                "mandatory_depends_on": field.mandatory_depends_on,
                "read_only_depends_on": field.read_only_depends_on,
                "depends_on": field.depends_on,
                "all_properties": field,
				# "link_filters": field.get("link_filters"),
				# "placeholder": field.get("placeholder"),
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

    # Thêm section cuối cùng vào tab nếu có
    if current_section and current_tab:
        current_tab['sections'].append(current_section)

    # Thêm tab cuối cùng vào danh sách nếu có
    if current_tab:
        list_infor_column.append(current_tab)

    return list_infor_column


# Hàm lấy all field trong doctype (Sử dụng khi trong doctype đó không có chia làm các tab)
@frappe.whitelist()
def get_column_doctype(doctype: str):
# Lấy danh sách tất cả các field trong doctype
	fields = frappe.get_meta(doctype).fields
	list_infor_column = []

	current_section = None
	current_column = None

	for field in fields:
		# Bỏ qua các trường có fieldtype không cần thiết
		if field.fieldtype in ['Attach Image']:
			continue
		if field.name == 'title':
			continue

		# Xử lý Section Break
		if field.fieldtype == 'Section Break':
			# Thêm section trước đó vào danh sách nếu có
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

		# Xử lý Column Break
		elif field.fieldtype == 'Column Break':
			# Thêm column trước đó vào section hiện tại nếu có
			if current_column:
				current_section['columns'].append(current_column)

			# Tạo column mới
			current_column = {
				'fields': []
			}

		# Xử lý các field thông thường
		elif current_section and field.label and field.fieldname != "thuoc_ho_so":  # Chỉ xử lý nếu field có label hợp lệ
			# Tạo dữ liệu của field
			field_data = {
				'label': _(field.label),
                'name': field.fieldname,
                'type': field.fieldtype,
                'options': field.options,
                'mandatory': field.reqd,
                "placeholder": field.label,
                "read_only": field.read_only,
                'default': field.default,
                "mandatory_depends_on": field.mandatory_depends_on,
                "read_only_depends_on": field.read_only_depends_on,
                "depends_on": field.depends_on,
                "all_properties": field,
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
def get_field_doctype(doctype):
    # Lấy danh sách tất cả các field trong doctype
    fields = frappe.get_meta(doctype).fields
    return fields
     
@frappe.whitelist()
def create_yyy_record(data):
    """
    Tạo mới bản ghi yyy trong doctype oms_yyy
    :param data: Dữ liệu của bản ghi (json)
    """
    try:
        # Chuyển dữ liệu JSON thành đối tượng dictionary
        employee_data = frappe.parse_json(data)

        # Lấy metadata của Doctype (lấy tất cả các trường)
        doc_meta = frappe.get_meta("oms_yyy")
        doc_fields = doc_meta.fields

        # Tạo dictionary chứa dữ liệu cho việc tạo document
        new_employee_data = {
            "doctype": "oms_yyy"
        }

        # Kiểm tra các trường bắt buộc và thêm dữ liệu vào new_employee_data
        for field in doc_fields:
            fieldname = field.fieldname

            # Kiểm tra nếu dữ liệu đã được gửi từ frontend
            if fieldname in employee_data:
                new_employee_data[fieldname] = employee_data[fieldname]

            # Kiểm tra các trường bắt buộc (is_mandatory)
            # elif field.reqd:
            #     if not employee_data.get(fieldname):
            #         return {
            #             "status": "error",
            #             "message": _("Field {0} is mandatory").format(fieldname)
            #         }

        # Tạo bản ghi mới trong doctype oms_yyy
        new_employee = frappe.get_doc(new_employee_data)

        # Lưu bản ghi
        new_employee.insert()
        frappe.db.commit()

        return {
            "status": "success",
            "message": _("Employee record created successfully"),
            "employee_name": new_employee.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "yyy Creation Error")
        return {
            "status": "error",
            "message": str(e)
        }
        
@frappe.whitelist()
def get_fields_meta(doctype, restricted_fieldtypes=None, as_array=False):
	not_allowed_fieldtypes = [
		"Tab Break",
		"Section Break",
		"Column Break",
	]

	if restricted_fieldtypes:
		restricted_fieldtypes = frappe.parse_json(restricted_fieldtypes)
		not_allowed_fieldtypes += restricted_fieldtypes

	fields = frappe.get_meta(doctype).fields
	fields = [field for field in fields if field.fieldtype not in not_allowed_fieldtypes]

	standard_fields = [
		{"fieldname": "name", "fieldtype": "Link", "label": "ID", "options": doctype},
		{
			"fieldname": "owner",
			"fieldtype": "Link",
			"label": "Created By",
			"options": "User"
		},
		{
			"fieldname": "modified_by",
			"fieldtype": "Link",
			"label": "Last Updated By",
			"options": "User",
		},
		{"fieldname": "_user_tags", "fieldtype": "Data", "label": "Tags"},
		{"fieldname": "_liked_by", "fieldtype": "Data", "label": "Like"},
		{"fieldname": "_comments", "fieldtype": "Text", "label": "Comments"},
		{"fieldname": "_assign", "fieldtype": "Text", "label": "Assigned To"},
		{"fieldname": "creation", "fieldtype": "Datetime", "label": "Created On"},
		{"fieldname": "modified", "fieldtype": "Datetime", "label": "Last Updated On"},
	]

	for field in standard_fields:
		if not restricted_fieldtypes or field.get('fieldtype') not in restricted_fieldtypes:
			fields.append(field)

	if as_array:
		return fields

	fields_meta = {}
	for field in fields:
		fields_meta[field.get('fieldname')] = field

	return fields_meta

# Hàm check quyền của một user đang đăng nhập
@frappe.whitelist()
def check_user_permissions(doctype):
    user = frappe.session.user  # Lấy người dùng hiện tại
    roles = frappe.get_roles(user)  # Lấy các vai trò của người dùng
    
    # Tạo một đối tượng Meta cho DocType để dùng với hàm get_role_permissions
    meta = frappe.get_meta(doctype)

    # Lấy quyền chi tiết dựa trên vai trò từ hàm get_role_permissions
    role_permissions = get_role_permissions(meta, user=user)

    # Khởi tạo biến lưu kết quả cuối cùng về quyền của người dùng trên DocType
    user_permissions = {
        "can_read": bool(role_permissions.get("read")),
        "can_write": bool(role_permissions.get("write")),
        "can_create": bool(role_permissions.get("create")),
        "can_delete": bool(role_permissions.get("delete"))
    }
   
    return role_permissions


@frappe.whitelist()
def get_sidebar_fields(doctype, name):
	if not frappe.db.exists("oms Fields Layout", {"dt": doctype, "type": "Side Panel"}):
		return []
	layout = frappe.get_doc("oms Fields Layout", {"dt": doctype, "type": "Side Panel"}).layout

	if not layout:
		return []
	
	layout = json.loads(layout)

	not_allowed_fieldtypes = [
		"Tab Break",
		"Section Break",
		"Column Break",
	]

	fields = frappe.get_meta(doctype).fields
	fields = [field for field in fields if field.fieldtype not in not_allowed_fieldtypes]

	doc = frappe.get_cached_doc(doctype, name)
	has_high_permlevel_fields = any(df.permlevel > 0 for df in fields)
	if has_high_permlevel_fields:
		has_read_access_to_permlevels = doc.get_permlevel_access("read")
		has_write_access_to_permlevels = doc.get_permlevel_access("write")

	for section in layout:
		section["name"] = section.get("name") or section.get("label")
		for field in section.get("fields") if section.get("fields") else []:
			field_obj = next((f for f in fields if f.fieldname == field), None)
			if field_obj:
				if field_obj.permlevel > 0:
					field_has_write_access = field_obj.permlevel in has_write_access_to_permlevels
					field_has_read_access = field_obj.permlevel in has_read_access_to_permlevels
					if not field_has_write_access and field_has_read_access:
						field_obj.read_only = 1
					if not field_has_read_access and not field_has_write_access:
						field_obj.hidden = 1
				section["fields"][section.get("fields").index(field)] = get_field_obj(field_obj)

	fields_meta = {}
	for field in fields:
		fields_meta[field.fieldname] = field

	return layout

def get_field_obj(field):
    obj = {
        "label": field.label,
        "type": get_type(field),
        "name": field.fieldname,
        "hidden": field.hidden,
        "reqd": field.reqd,
        "read_only": field.read_only,
        "all_properties": field,
    }

    obj["placeholder"] = field.get("placeholder") or "Add " + field.label + "..."

    if field.fieldtype == "Link":
        obj["placeholder"] = field.get("placeholder") or "Select " + field.label + "..."
        obj["doctype"] = field.options
    elif field.fieldtype == "Select" and field.options:
        obj["placeholder"] = field.get("placeholder") or "Select " + field.label + "..."
        obj["options"] = [{"label": option, "value": option} for option in field.options.split("\n")]

    if field.read_only:
        obj["tooltip"] = "This field is read only and cannot be edited."

    return obj
def get_type(field):
    if field.fieldtype == "Data" and field.options == "Phone":
        return "phone"
    elif field.fieldtype == "Data" and field.options == "Email":
        return "email"
    elif field.fieldtype == "Check":
        return "checkbox"
    elif field.fieldtype == "Int":
        return "number"
    elif field.fieldtype in ["Small Text", "Text", "Long Text"]:
        return "textarea"
    elif field.read_only:
        return "read_only"
    return field.fieldtype.lower()

def get_assigned_users(doctype, name, default_assigned_to=None):
	assigned_users = frappe.get_all(
		"ToDo",
		fields=["allocated_to"],
		filters={
			"reference_type": doctype,
			"reference_name": name,
			"status": ("!=", "Cancelled"),
		},
		pluck="allocated_to",
	)

	users = list(set(assigned_users))

	# if users is empty, add default_assigned_to
	if not users and default_assigned_to:
		users = [default_assigned_to]
	return users

@frappe.whitelist()
def get_group_by_fields(doctype: str):
	allowed_fieldtypes = [
		"Check",
		"Data",
		"Float",
		"Int",
		"Currency",
		"Dynamic Link",
		"Link",
		"Select",
		"Duration",
		"Date",
		"Datetime",
	]

	fields = frappe.get_meta(doctype).fields
	fields = [field for field in fields if field.fieldtype not in no_value_fields and field.fieldtype in allowed_fieldtypes]
	fields = [
		{
			"label": _(field.label),
			"value": field.fieldname,
		}
		for field in fields
		if field.label and field.fieldname
	]

	standard_fields = [
		{"label": "Name", "value": "name"},
		{"label": "Created On", "value": "creation"},
		{"label": "Last Modified", "value": "modified"},
		{"label": "Modified By", "value": "modified_by"},
		{"label": "Owner", "value": "owner"},
		{"label": "Liked By", "value": "_liked_by"},
		{"label": "Assigned To", "value": "_assign"},
		{"label": "Comments", "value": "_comments"},
		{"label": "Created On", "value": "creation"},
		{"label": "Modified On", "value": "modified"},
	]

	for field in standard_fields:
		field["label"] = _(field["label"])
		fields.append(field)

	return fields


@frappe.whitelist()
def get_value_modal_no_tab(doctype):
	 # Lấy danh sách tất cả các field trong doctype
	fields = frappe.get_meta(doctype).fields
	list_infor_column = []
	
	current_tab = None
	current_section = None
	current_column = None

	for field in fields:
		# Bỏ qua các loại field không cần thiết
		# if field.fieldtype in ['Attach Image']:
		# 	continue
		if field.name == 'title':
			continue

		if field.fieldtype == 'Tab Break':
			# Thêm tab trước đó nếu có
			if current_tab:
				if current_section:  # Thêm section trước đó nếu có
					if current_column:  # Thêm column cuối cùng vào section trước đó nếu có
						current_section['columns'].append(current_column)
					current_tab['sections'].append(current_section)
				list_infor_column.append(current_tab)

			# Tạo tab mới
			current_tab = {
				'label': field.label or field.name or 'Untitled',
				"name": field.label or field.name or 'Untitled',
				'sections': []
			}
			current_section = None  # Reset section và column khi tạo tab mới
			current_column = None

		elif field.fieldtype == 'Section Break':
			# Nếu không có tab hiện tại, tạo section ở cấp cao nhất
			if current_section:
				if current_column:  # Thêm column cuối cùng vào section trước đó nếu có
					current_section['columns'].append(current_column)
				if current_tab:  # Nếu có tab, thêm section vào tab
					current_tab['sections'].append(current_section)
				else:  # Nếu không có tab, thêm section trực tiếp vào danh sách
					list_infor_column.append(current_section)

			# Tạo section mới
			current_section = {
				'label': field.label,
				'columns': []
			}
			current_column = None  # Reset column khi tạo section mới

		elif field.fieldtype == 'Column Break':
			# Thêm column trước đó vào section hiện tại nếu có
			if current_column and current_section:
				current_section['columns'].append(current_column)

			# Tạo column mới
			current_column = {
				'fields': []
			}

		elif field.label:  # Chỉ xử lý nếu field có label hợp lệ
			# Tạo dữ liệu của field
			field_data = {
				'label': _(field.label),
				'name': field.fieldname,
				'type': field.fieldtype,
				'options': field.options,
				'mandatory': field.reqd,
				"placeholder": field.label,
				"read_only": field.read_only,
				"all_properties": field,
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

	# Thêm section cuối cùng vào tab nếu có
	if current_section:
		if current_tab:  # Nếu có tab, thêm section vào tab
			current_tab['sections'].append(current_section)
		else:  # Nếu không có tab, thêm section trực tiếp vào danh sách
			list_infor_column.append(current_section)

	# Thêm tab cuối cùng vào danh sách nếu có
	if current_tab:
		list_infor_column.append(current_tab)

	return list_infor_column