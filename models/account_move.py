from odoo import fields, models, _


class AccountMove(models.Model):
    """Extend account.move to link vendor bills back to daily reports"""
    _inherit = 'account.move'
    
    # Link vendor bills back to daily reports
    daily_report_id = fields.Many2one(
        'farm.daily.report',
        string= 'Daily Report',
        help= 'Daily report that generated this vendor bill',
        readonly=True
    )
    
    def _get_name_invoice_report(self):
        """Override to show daily report reference in bill"""
        result = super()._get_name_invoice_report()
        if self.daily_report_id:
            result += _(" (Farm Report: %s)") % self.daily_report_id.name
        return result
