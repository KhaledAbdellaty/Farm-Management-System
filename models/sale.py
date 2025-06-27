from odoo import fields, models, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cultivation_project_id = fields.Many2one(
        'farm.cultivation.project', 
        string='Cultivation Project',
        tracking=True,
        help="The cultivation project this sale order is related to"
    )
