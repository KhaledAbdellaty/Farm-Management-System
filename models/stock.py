from odoo import fields, models, api, _
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    daily_report_id = fields.Many2one('farm.daily.report', string='Daily Report', 
                                    index=True, ondelete='set null')

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'
    
    daily_report_id = fields.Many2one(related='move_id.daily_report_id', string='Farm Operation', 
                                     store=True, index=True)

class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    is_used_in_farm = fields.Boolean(string='Used in Farm', compute='_compute_farm_usage', store=True)
    last_farm_usage_date = fields.Date(string='Last Farm Usage', compute='_compute_farm_usage', store=True)
    
    @api.depends('stock_move_ids.daily_report_id')
    def _compute_farm_usage(self):
        """Compute if product is used in farm operations and the last usage date"""
        for product in self:
            farm_moves = self.env['stock.move'].search([
                ('product_id', '=', product.id),
                ('daily_report_id', '!=', False),
                ('state', '=', 'done')
            ], order='date desc', limit=1)
            
            product.is_used_in_farm = bool(farm_moves)
            product.last_farm_usage_date = farm_moves.date.date() if farm_moves else False

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'
    
    daily_report_id = fields.Many2one('farm.daily.report', string='Daily Report', 
                                    index=True, ondelete='cascade')

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    def button_validate(self):
        """Override button_validate to update daily report state when picking is done."""
        result = super(StockPicking, self).button_validate()
        
        # After validation, update daily reports
        daily_report_pickings = self.filtered(
            lambda p: p.move_ids.filtered(lambda m: hasattr(m, 'daily_report_id') and m.daily_report_id)
        )
        
        for picking in daily_report_pickings:
            if picking.state == 'done':
                # Collect all daily reports from the moves
                daily_reports = self.env['farm.daily.report']
                for move in picking.move_ids:
                    if hasattr(move, 'daily_report_id') and move.daily_report_id:
                        daily_reports |= move.daily_report_id
                
                # Update daily report states and create analytic entries
                for report in daily_reports:
                    if report.state == 'confirmed':
                        stockable_moves = self.env['stock.move'].search([
                            ('daily_report_id', '=', report.id),
                            ('product_id.type', 'in', ['product', 'consu'])
                        ])
                        
                        if not stockable_moves or all(m.state == 'done' for m in stockable_moves):
                            report.state = 'done'
                            if not report.analytic_line_ids:
                                report._create_analytic_entries()
        
        return result
