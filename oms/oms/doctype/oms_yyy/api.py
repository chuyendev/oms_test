import frappe
from frappe import _
import json
from oms.api.doc import get_fields_meta


@frappe.whitelist()
def create_yyy(ho_va_ten,kieu_check,kieu_date,kieu_datetime,kieu_float,kieu_int,kieu_rating,kieu_select,kieu_small_text,kieu_text,kieu_link,kieu_text_editor):
    try:
        yyy_record = frappe.get_doc({
            "doctype": "oms_yyy",
            "ho_va_ten": ho_va_ten,
            "kieu_check":kieu_check,
            "kieu_date":kieu_date,
            "kieu_datetime":kieu_datetime,
            "kieu_float":kieu_float,
            "kieu_int":kieu_int,
            "kieu_rating":kieu_rating,
            "kieu_select":kieu_select,
            "kieu_small_text":kieu_small_text,
            "kieu_text":kieu_text,
            "kieu_link":kieu_link,
            "kieu_text_editor":kieu_text_editor
        })
        yyy_record.insert()
        frappe.db.commit()

        return {
            "message": "Tạo thành công.",
            "data": yyy_record.name  # Trả về tên (ID) của bản ghi mới
        }
        
    except frappe.exceptions.ValidationError as e:
        # Trường hợp lỗi do xác thực dữ liệu
        frappe.db.rollback()  # Rollback để tránh ghi lỗi vào database
        return {
            "message": "Tạo không thành công.",
            "error": "Validation Error",
            "details": str(e)
        }
    
    except Exception as e:
        # Trường hợp lỗi chung
        frappe.db.rollback()
        return {
            "message": "Tạo không thành công.",
            "error": "Unknown Error",
            "details": str(e)
        }
        

@frappe.whitelist()
def get_yyy(name):
	lst = frappe.qb.DocType("oms_yyy")

	query = frappe.qb.from_(lst).select("*").where(lst.name == name).limit(1)

	lst_data = query.run(as_dict=True)
	if not len(lst_data):
		frappe.throw(_("yyy not found"), frappe.DoesNotExistError)
	lst_data = lst_data.pop()

	lst_data["doctype"] = "oms_yyy"
	lst_data["fields_meta"] = get_fields_meta("oms_yyy")
	print("Test log lst_data : ",lst_data)
	return lst_data


@frappe.whitelist()
def update_yyy(yyyId,ho_va_ten=None,kieu_check=None,kieu_date=None,kieu_datetime=None,kieu_float=None,kieu_int=None
               ,kieu_rating=None,kieu_select=None,kieu_small_text=None,kieu_text=None,kieu_link=None,kieu_text_editor=None):
    # Lấy bản ghi cần cập nhật
    doc = frappe.get_doc('oms_yyy', yyyId)
    
	# Cập nhật các trường nếu có giá trị
    if ho_va_ten:
    	doc.ho_va_ten = ho_va_ten
    if kieu_check:
        doc.kieu_check = kieu_check
    if kieu_date:
        doc.kieu_date = kieu_date
    if kieu_datetime:
        doc.kieu_datetime = kieu_datetime
    if kieu_float:
        doc.kieu_float = kieu_float
    if kieu_int:
        doc.kieu_int = kieu_int
    if kieu_rating:
        doc.kieu_rating = kieu_rating
    if kieu_select:
        doc.kieu_select = kieu_select
    if kieu_small_text:
        doc.kieu_small_text = kieu_small_text    
    if kieu_text:
        doc.kieu_text = kieu_text   
    if kieu_link:
        doc.kieu_link = kieu_link   
    if kieu_text_editor:
        doc.kieu_text_editor = kieu_text_editor 
    doc.save()
    frappe.db.commit()
    return {"message": "yyy updated successfully"}