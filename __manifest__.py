{
    'name': 'Seafood Management',
    'version': '1.0',
    'summary': 'Quản lý Thủy Sản: Lô hàng, Hạn sử dụng, Cảnh báo AI',
    'sequence': 10,
    'description': """
Quản lý Công ty Thủy Sản
========================
Module này tích hợp các tính năng:
- Quản lý lô hàng thủy sản
- Tích hợp AI cảnh báo hạn sử dụng
    """,
    'category': 'Custom',
    'website': 'https://www.example.com',
    'depends': ['base', 'stock', 'sale_management', 'product_expiry'],
    'data': [
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/seafood_lot_views.xml',
        'views/seafood_menu.xml',
        'views/website_seafood_template.xml',
        'data/seafood_data.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
