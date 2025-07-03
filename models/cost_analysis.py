from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class CostAnalysis(models.Model):
    _name = 'farm.cost.analysis'
    _description = 'Farm Cost Analysis'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, 
                     default=lambda self: 'New')
    date = fields.Date(string='Date', required=True, default=fields.Date.today, tracking=True)
    
    # Project and location information
    project_id = fields.Many2one('farm.cultivation.project', string='Cultivation Project', 
                              required=True, tracking=True, ondelete='cascade')
    farm_id = fields.Many2one('farm.farm', related='project_id.farm_id', 
                           string='Farm', store=True, readonly=True)
    field_id = fields.Many2one('farm.field', related='project_id.field_id', 
                            string='Field', store=True, readonly=True)
    crop_id = fields.Many2one('farm.crop', related='project_id.crop_id', 
                           string='Crop', store=True, readonly=True)
    
    def _get_cost_types(self):
        """Return selection options for cost types with proper translations"""
        return [
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
        ]
    
    # Cost categorization
    cost_type = fields.Selection(
        selection='_get_cost_types',
        string='Cost Type', 
        required=True, 
        tracking=True
    )
    
    # Cost details
    cost_name = fields.Char(string='Cost Description', required=True, tracking=True)
    cost_amount = fields.Monetary(string='Cost Amount', required=True, tracking=True, 
                               currency_field='currency_id')
    cost_unit_amount = fields.Float(string='Unit Cost', compute='_compute_unit_cost', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', 
                               readonly=True)
    company_id = fields.Many2one('res.company', related='project_id.company_id', 
                              readonly=True, store=True)
    
    # Quantity information if applicable
    quantity = fields.Float(string='Quantity', tracking=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', tracking=True)
    
    # Financial data
    invoice_id = fields.Many2one('account.move', string='Invoice', tracking=True)
    payment_id = fields.Many2one('account.payment', string='Payment', tracking=True)
    
    # Analytical accounting
    analytic_account_id = fields.Many2one('account.analytic.account', 
                                        string='Analytic Account',
                                        related='project_id.analytic_account_id', 
                                        store=True, readonly=True)
    
    notes = fields.Html(string='Notes', translate=True)
    
    # Cost per area calculations
    cost_per_area = fields.Monetary(string='Cost per Area', compute='_compute_cost_per_area', 
                                 store=True, currency_field='currency_id')
    field_area = fields.Float(related='field_id.area', string='Field Area', 
                           readonly=True, store=True)
    field_area_unit = fields.Selection(related='field_id.area_unit', 
                                    string='Area Unit', readonly=True, store=True)
    
    # For budgeting and variance analysis
    is_budgeted = fields.Boolean(string='Budgeted Cost', default=False, tracking=True)
    
    def _get_source_types(self):
        """Return selection options for source types with proper translations"""
        return [
            ('daily_report', 'Daily Report'),
            ('bom', 'Bill of Materials'),
            ('manual', 'Manual Entry'),
        ]
    
    # Source tracking for automatic cost entries
    source_type = fields.Selection(
        selection='_get_source_types',
        string='Source Type', 
        default='manual', 
        tracking=True
    )
    source_id = fields.Integer(string='Source Record ID', tracking=True)
    budget_variance = fields.Float(string='Budget Variance %', compute='_compute_budget_variance', 
                               store=True)
    
    def _get_cost_effectiveness(self):
        """Return selection options for cost effectiveness with proper translations"""
        return [
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('average', 'Average'),
            ('poor', 'Poor'),
        ]
    
    # Cost effectiveness
    cost_effectiveness = fields.Selection(
        selection='_get_cost_effectiveness',
        string='Cost Effectiveness', 
        tracking=True
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate unique cost reference number"""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('farm.cost.analysis') or _('New')
        return super().create(vals_list)
        
    def name_get(self):
        """Returns the display name of the record with translations applied at runtime"""
        result = []
        for record in self:
            cost_type_label = record.get_cost_type_label() if record.cost_type else ''
            name = f"{record.name} - {cost_type_label}"
            result.append((record.id, name))
        return result
    
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
                    
    def get_cost_type_label(self):
        """Get translated label for cost type at runtime"""
        cost_type_labels = {
            'seeds': _('Seeds/Seedlings'),
            'fertilizer': _('Fertilizers'),
            'pesticide': _('Pesticides'),
            'herbicide': _('Herbicides'),
            'water': _('Irrigation Water'),
            'labor': _('Labor/Workforce'),
            'machinery': _('Machinery/Equipment'),
            'rent': _('Land Rent'),
            'fuel': _('Fuel'),
            'maintenance': _('Maintenance'),
            'services': _('Services'),
            'transportation': _('Transportation'),
            'storage': _('Storage'),
            'certification': _('Certification'),
            'testing': _('Laboratory Testing'),
            'other': _('Other'),
        }
        return cost_type_labels.get(self.cost_type, self.cost_type)

    def get_source_type_label(self):
        """Get translated label for source type at runtime"""
        source_type_labels = {
            'daily_report': _('Daily Report'),
            'bom': _('Bill of Materials'),
            'manual': _('Manual Entry'),
        }
        return source_type_labels.get(self.source_type, self.source_type)
    
    def get_cost_effectiveness_label(self):
        """Get translated label for cost effectiveness at runtime"""
        cost_effectiveness_labels = {
            'excellent': _('Excellent'),
            'good': _('Good'),
            'average': _('Average'),
            'poor': _('Poor'),
        }
        return cost_effectiveness_labels.get(self.cost_effectiveness, self.cost_effectiveness)
