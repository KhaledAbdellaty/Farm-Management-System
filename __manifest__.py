{
    'name': 'Farm Management System',
    'version': '18.0.1.0.0',
    'summary': 'Comprehensive farm management for Odoo 18',
    'description': """
        This module provides a complete Farm Management System for Odoo 18.
        Features include:
        - Farm and Field Management
        - Crop Planning and Tracking
        - Cultivation Projects with Cost Analysis
        - Input and Resource Management
        - Seasonal Planning
        - Daily Operations and Reporting
        - Integration with Inventory, Accounting and Project Management
    """,
    'category': 'Agriculture',
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'stock',
        'account',
        'analytic',
        'project',
        'hr_timesheet',
        'web',
    ],
    'data': [
        'security/farm_security.xml',
        'security/ir.model.access.csv',
        'views/farm_views.xml',
        'views/field_views.xml',
        'views/crop_views.xml',
        'views/cultivation_project_views.xml',
        'views/crop_bom_views.xml',
        'views/daily_report_views.xml',
        'views/cost_analysis_views.xml',
        'views/res_config_settings_views.xml',
        'views/farm_menu.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'assets': {
        'web.assets_backend': [
            'farm_management/static/src/scss/farm_management.scss',
        ]
    },
    'images': ['static/description/icon.png'],
    'post_init_hook': '',
    'pre_init_hook': '',
    'post_load': '',
}
