from odoo import api, fields, models, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    # Farm Management settings
    farm_labor_expense_account_id = fields.Many2one(
        'account.account', 
        string='Labor Expense Account',
        config_parameter='farm_management.labor_expense_account_id',
        domain=[('account_type', '=', 'expense')]
    )
    
    farm_machinery_expense_account_id = fields.Many2one(
        'account.account', 
        string='Machinery Expense Account',
        config_parameter='farm_management.machinery_expense_account_id',
        domain=[('account_type', '=', 'expense')]
    )
