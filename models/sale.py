from odoo import fields, models, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cultivation_project_id = fields.Many2one(
        'farm.cultivation.project', 
        string='Cultivation Project',
        tracking=True,
        help="The cultivation project this sale order is related to"
    )
    
    def _get_cultivation_project_display_name(self):
        """Returns the display name with translation applied at runtime"""
        self.ensure_one()
        if self.cultivation_project_id:
            return _("Cultivation Project: %s") % self.cultivation_project_id.name
        return ""
