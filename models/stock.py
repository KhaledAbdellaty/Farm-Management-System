from odoo import fields, models, api, _

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    daily_report_id = fields.Many2one('farm.daily.report', string=_('Daily Report'), 
                                    index=True, ondelete='set null')

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'
    
    daily_report_id = fields.Many2one('farm.daily.report', string=_('Daily Report'), 
                                    index=True, ondelete='cascade')
