from erpnext.selling.doctype.sales_order.sales_order import SalesOrder
from frappe  import _
class SalesOrderOverride(SalesOrder):
    def default_list_data():
        columns = [
            {
                'label': _('Title'),
                'type': 'Data',
                'key': 'title',
                'width': '16rem'
            },
        ]

        rows = [
            "title",
            "name"
        ]
        return {'columns': columns, 'rows': rows}