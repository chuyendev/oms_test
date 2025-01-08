import frappe

def default_list_data(doctype):
    # Cấu hình mặc định cho từng doctype
    config = {
        "Sales Order": {
            "columns": [
                {"label": "Customer", "type": "Link", "key": "customer", "width": "16rem"},
                {"label": "Status", "type": "Select", "key": "status", "width": "16rem"},
                {"label": "Delivery Date", "type": "Date", "key": "delivery_date", "width": "16rem"},
                {"label": "Grand Total", "type": "Currency", "key": "grand_total", "width": "16rem"},
                {"label": "ID", "type": "Data", "key": "naming_series", "width": "16rem"},

            ],
            "rows": [
                "customer",
                "status",
                "delivery_date",
                "grand_total",
                "naming_series",
                "name",
            ],
        }
        # Thêm cấu hình cho các doctype khác
        # "AnotherDoctype": { ... }
    }

    # Trả về cấu hình của doctype hoặc giá trị mặc định
    return config.get(doctype, {"columns": [], "rows": []})

# Hàm lấy danh sách options từ một doctype khác
def get_options_from_doctype(option_doctype, fieldname="name"):
    options = frappe.get_all(option_doctype, fields=[fieldname])
    return [{"label": opt[fieldname], "value": opt[fieldname]} for opt in options]

# Cấu hình các trường tùy chỉnh cho từng doctype
custom_fields_config = {
    "Sales Order": [
        {
			"label": "ID",
			"name": "name",
			"type": "Data"  # Trường nhập văn bản
		},
    ]
    # Thêm cấu hình cho các doctype khác nếu cần
}