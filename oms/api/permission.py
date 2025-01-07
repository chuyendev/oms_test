import frappe
from frappe.permissions import get_role_permissions, get_user_permissions
from frappe.utils import cint

# Hàm lấy list role của user đang đăng nhập
@frappe.whitelist(allow_guest=True)
def get_user_roles(user=None):
    if not user:
        user = frappe.session.user
    user_roles = frappe.get_roles(frappe.session.user)
    return user_roles

# Hàm check quyền của một user đang đăng nhập
@frappe.whitelist()
def check_user_permissions(doctype=None,user=None,debug=False):
    if not user:
        user = frappe.session.user

    # Bước 1: Lấy tất cả các quyền của doctype
    doctype_permissions = frappe.get_all(
        "Custom DocPerm",
        filters={"parent": doctype},
        fields=["role", "permlevel", "read", "write", "create", "delete", "submit", "cancel", "amend", "print", "email", "report", "import", "export", "share"]
    )

    # Bước 2: Lấy tất cả các role của tài khoản đăng nhập
    user_roles = set(frappe.get_roles(user))

    # Bước 3: Check và lấy permissions của các role trùng khớp
    permissions = {}
    for perm in doctype_permissions:
        if perm.role in user_roles:
            current_level = perm.permlevel
            for perm_type in ['read', 'write', 'create', 'delete', 'submit', 'cancel', 'amend', 'print', 'email', 'report', 'import', 'export', 'share']:
                if perm_type not in permissions:
                    permissions[perm_type] = {}
                
                if current_level not in permissions[perm_type]:
                    permissions[perm_type][current_level] = cint(perm.get(perm_type))
                else:
                    # Nếu đã có permission ở level này, chỉ cập nhật nếu giá trị mới là True
                    permissions[perm_type][current_level] |= cint(perm.get(perm_type))

    # Tổng hợp permissions, ưu tiên level thấp nhất
    final_permissions = {}
    for perm_type in permissions:
        if permissions[perm_type]:
            min_level = min(permissions[perm_type].keys())
            final_permissions[perm_type] = permissions[perm_type][min_level]

    # Remove permissions that are not applicable
    doctype_meta = frappe.get_meta(doctype)
    if not doctype_meta.is_submittable:
        final_permissions.pop('submit', None)
        final_permissions.pop('cancel', None)
        final_permissions.pop('amend', None)

    # Đoạn code check nếu doctype có quyền import thì mới hiển thị quyền import
    if not doctype_meta.allow_import:
        final_permissions.pop('import', None)
        
    # Convert to boolean
    final_permissions = {k: bool(v) for k, v in final_permissions.items()}

    result = {
        "user": user,
        "roles": list(user_roles),
        "permissions": final_permissions
    }
    if debug:
        frappe.log(f"Permissions for user {user} on doctype {doctype}: {frappe.as_json(result, indent=4)}")
    return result