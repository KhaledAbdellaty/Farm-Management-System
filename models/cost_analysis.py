from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class CostAnalysis(models.Model):
    _name = 'farm.cost.analysis'
    _description = 'Farm Cost Analysis'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char('Reference', required=True, copy=False, readonly=True, 
                     default=lambda self: _('New'))
    date = fields.Date('Date', required=True, default=fields.Date.today, tracking=True)
    
    # Project and location information
    project_id = fields.Many2one('farm.cultivation.project', string='Cultivation Project', 
                              required=True, tracking=True, ondelete='cascade')
    farm_id = fields.Many2one('farm.farm', related='project_id.farm_id', 
                           string='Farm', store=True, readonly=True)
    field_id = fields.Many2one('farm.field', related='project_id.field_id', 
                            string='Field', store=True, readonly=True)
    crop_id = fields.Many2one('farm.crop', related='project_id.crop_id', 
                           string='Crop', store=True, readonly=True)
    
    # Cost categorization
    cost_type = fields.Selection([
        ('seeds', 'Seeds/Seedlings'),
        ('fertilizer', 'Fertilizers'),
        ('pesticide', 'Pesticides'),
        ('herbicide', 'Herbicides'),
        ('water', 'Irrigation Water'),
        ('labor', 'Labor/Workforce'),
        ('machinery', 'Machinery/Equipment'),
        ('rent', 'Land Rent'),
        ('fuel', 'Fuel'),
        ('maintenance', 'Maintenance'),
        ('services', 'Services'),
        ('transportation', 'Transportation'),
        ('storage', 'Storage'),
        ('certification', 'Certification'),
        ('testing', 'Laboratory Testing'),
        ('other', 'Other'),
    ], string='Cost Type', required=True, tracking=True)
    
    # Cost details
    cost_name = fields.Char('Cost Description', required=True, tracking=True)
    cost_amount = fields.Monetary('Cost Amount', required=True, tracking=True, 
                               currency_field='currency_id')
    cost_unit_amount = fields.Float('Unit Cost', compute='_compute_unit_cost', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', 
                               readonly=True)
    company_id = fields.Many2one('res.company', related='project_id.company_id', 
                              readonly=True, store=True)
    
    # Quantity information if applicable
    quantity = fields.Float('Quantity', tracking=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', tracking=True)
    
    # Financial data
    invoice_id = fields.Many2one('account.move', string='Invoice', tracking=True)
    payment_id = fields.Many2one('account.payment', string='Payment', tracking=True)
    
    # Analytical accounting
    analytic_account_id = fields.Many2one('account.analytic.account', 
                                        string='Analytic Account',
                                        related='project_id.analytic_account_id', 
                                        store=True, readonly=True)
    
    notes = fields.Html('Notes', translate=True)
    
    # Cost per area calculations
    cost_per_area = fields.Monetary('Cost per Area', compute='_compute_cost_per_area', 
                                 store=True, currency_field='currency_id')
    field_area = fields.Float(related='field_id.area', string='Field Area', 
                           readonly=True, store=True)
    field_area_unit = fields.Selection(related='field_id.area_unit', 
                                    string='Area Unit', readonly=True, store=True)
    
    # For budgeting and variance analysis
    is_budgeted = fields.Boolean('Budgeted Cost', default=False, tracking=True)
    
    # Source tracking for automatic cost entries
    source_type = fields.Selection([
        ('daily_report', 'Daily Report'),
        ('bom', 'Bill of Materials'),
        ('manual', 'Manual Entry'),
    ], string='Source Type', default='manual', tracking=True)
    source_id = fields.Integer('Source Record ID', tracking=True)
    budget_variance = fields.Float('Budget Variance %', compute='_compute_budget_variance', 
                               store=True)
    
    # Cost effectiveness
    cost_effectiveness = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('average', 'Average'),
        ('poor', 'Poor'),
    ], string='Cost Effectiveness', tracking=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate unique cost reference number"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('farm.cost.analysis') or _('New')
        return super().create(vals_list)
    
    @api.depends('cost_amount', 'quantity')
    def _compute_unit_cost(self):
        """Calculate unit cost based on quantity"""
        for cost in self:
            cost.cost_unit_amount = cost.quantity and cost.cost_amount / cost.quantity or 0.0
    
    @api.depends('cost_amount', 'field_area')
    def _compute_cost_per_area(self):
        """Calculate cost per area unit"""
        for cost in self:
            cost.cost_per_area = cost.field_area and cost.cost_amount / cost.field_area or 0.0
    
    @api.depends('cost_amount', 'is_budgeted', 'project_id.budget')
    def _compute_budget_variance(self):
        """Calculate budget variance percentage"""
        for cost in self:
            if cost.is_budgeted and cost.project_id.budget:
                # Calculate what percentage of the total budget this cost represents
                cost.budget_variance = (cost.cost_amount / cost.project_id.budget) * 100
            else:
                cost.budget_variance = 0.0
    
    @api.constrains('date', 'project_id')
    def _check_date(self):
        """Ensure cost date is within project dates"""
        for record in self:
            if record.date and record.project_id:
                if record.date < record.project_id.start_date:
                    raise ValidationError(_("Cost date cannot be before project start date."))
                if record.project_id.actual_end_date and record.date > record.project_id.actual_end_date:
                    raise ValidationError(_("Cost date cannot be after project end date."))
