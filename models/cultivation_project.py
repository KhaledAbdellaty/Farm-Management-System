from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from odoo.osv import expression
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class CultivationProject(models.Model):
    _name = 'farm.cultivation.project'
    _description = _('Cultivation Project')
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, name'
    
    # Link to project.project instead of inheriting from it
    project_id = fields.Many2one('project.project', string='Related Project', tracking=True)

    name = fields.Char('Project Name', required=True, tracking=True, translate=True)
    code = fields.Char('Project Code', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    
    # Project timeframe
    start_date = fields.Date('Start Date', required=True, tracking=True)
    planned_end_date = fields.Date('Planned End Date', required=True, tracking=True)
    actual_end_date = fields.Date('Actual End Date', tracking=True)
    
    # Farm and field information
    farm_id = fields.Many2one('farm.farm', string='Farm', required=True, 
                            tracking=True, ondelete='restrict')
    field_id = fields.Many2one('farm.field', string='Field', required=True, 
                             tracking=True, ondelete='restrict',
                             domain="[('farm_id', '=', farm_id), "
                                   "('state', 'in', ['available', 'fallow'])]")
    field_area = fields.Float(related='field_id.area', string='Field Area', 
                            readonly=True, store=True)
    field_area_unit = fields.Selection(related='field_id.area_unit', 
                                    string='Area Unit', readonly=True, store=True)
    
    # Crop information
    crop_id = fields.Many2one('farm.crop', string='Crop', required=True, 
                            tracking=True, ondelete='restrict')
    crop_variety = fields.Char('Crop Variety', tracking=True)
    seed_quantity = fields.Float('Seed Quantity', tracking=True)
    seed_uom_id = fields.Many2one('uom.uom', string='Seed UoM', tracking=True)
    
    # BOM for crop inputs
    crop_bom_id = fields.Many2one('farm.crop.bom', string='Crop BOM', tracking=True,
                                domain="[('crop_id', '=', crop_id)]")
    
    # Project stages
    state = fields.Selection([
        ('draft', 'Planning'),
        ('preparation', 'Field Preparation'),
        ('sowing', 'Sowing/Planting'),
        ('growing', 'Growing'),
        ('harvest', 'Harvest'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Stage', default='draft', tracking=True, group_expand='_expand_states')
    
    # Harvest information
    planned_yield = fields.Float('Planned Yield', tracking=True)
    actual_yield = fields.Float('Actual Yield', tracking=True)
    yield_uom_id = fields.Many2one('uom.uom', string='Yield UoM', tracking=True)
    yield_quality = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('average', 'Average'),
        ('poor', 'Poor'),
    ], string='Yield Quality', tracking=True)
    
    # Financial information
    budget = fields.Monetary('Budget', currency_field='currency_id', tracking=True)
    actual_cost = fields.Monetary('Actual Cost', compute='_compute_actual_cost', 
                               store=True, currency_field='currency_id')
    revenue = fields.Monetary('Revenue', currency_field='currency_id', tracking=True)
    profit = fields.Monetary('Profit', compute='_compute_profit', store=True, 
                          currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    company_id = fields.Many2one('res.company', related='farm_id.company_id', 
                                store=True)
                                
    # Hourly rates for cost calculation
    labor_cost_hour = fields.Float('Labor Cost per Hour', default=10.0, tracking=True)
    machinery_cost_hour = fields.Float('Machinery Cost per Hour', default=25.0, tracking=True)
    
    # Daily operations and reporting
    daily_report_ids = fields.One2many('farm.daily.report', 'project_id', 
                                      string='Daily Reports')
    daily_report_count = fields.Integer(compute='_compute_daily_report_count', 
                                     string='Daily Reports')
    
    # Cost analysis
    cost_line_ids = fields.One2many('farm.cost.analysis', 'project_id', 
                                   string='Cost Lines')
    
    # Analytic account
    analytic_account_id = fields.Many2one('account.analytic.account', 
                                        string='Analytic Account', 
                                        tracking=True)
    
    # Related tasks (from project.project inheritance)
    task_count = fields.Integer(compute='_compute_task_count')
    
    notes = fields.Html('Notes', translate=True)
    
    # Weather conditions during cultivation
    avg_temperature = fields.Float('Average Temperature (°C)', tracking=True)
    total_rainfall = fields.Float('Total Rainfall (mm)', tracking=True)
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Project code must be unique!'),
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create analytic account and project record, update field status"""
        for vals in vals_list:
            if not vals.get('analytic_account_id'):
                # Create analytic account
                analytic_account = self.env['account.analytic.account'].create({
                    'name': vals.get('name', 'New Project'),
                    'code': vals.get('code', ''),
                    'company_id': self.env['farm.farm'].browse(vals.get('farm_id')).company_id.id,
                })
                vals['analytic_account_id'] = analytic_account.id
                
            # Create project.project record
            if not vals.get('project_id'):
                project_values = {
                    'name': vals.get('name', 'New Project'),
                    # Make sure to NEVER include analytic_account_id as it doesn't exist in project.project in Odoo v18
                    'company_id': self.env['farm.farm'].browse(vals.get('farm_id')).company_id.id,
                    'user_id': self.env.user.id,
                    'date_start': vals.get('start_date'),
                    'date': vals.get('planned_end_date'),
                }
                # Log for debugging
                _logger.info(f"Creating project with values: {project_values}")
                project = self.env['project.project'].create(project_values)
                vals['project_id'] = project.id
                
                # In Odoo v18, projects automatically create their own analytic accounts
                # We don't need to manually associate our analytic account with the project
                # The comment below is kept for reference
                # if vals.get('analytic_account_id') and project:
                #     analytic_account = self.env['account.analytic.account'].browse(vals['analytic_account_id'])
                
            # Update field status
            if vals.get('field_id'):
                field = self.env['farm.field'].browse(vals['field_id'])
                field.write({'state': 'preparation'})
                
        return super().create(vals_list)
    
    def write(self, vals):
        """Update field status based on project state and sync with project.project"""
        # Update related project.project when relevant fields change
        for project in self:
            project_vals = {}
            
            if 'name' in vals:
                project_vals['name'] = vals['name']
            if 'start_date' in vals:
                project_vals['date_start'] = vals['start_date']
            if 'planned_end_date' in vals:
                project_vals['date'] = vals['planned_end_date']
            
            if project_vals and project.project_id:
                project.project_id.write(project_vals)
        
        result = super().write(vals)
        
        if 'state' in vals:
            for project in self:
                if vals['state'] == 'sowing':
                    project.field_id.write({
                        'state': 'cultivated',
                        'current_crop_id': project.crop_id.id,
                    })
                elif vals['state'] == 'harvest':
                    project.field_id.write({'state': 'harvested'})
                elif vals['state'] == 'done':
                    project.field_id.write({
                        'state': 'fallow',
                        'current_crop_id': False,
                    })
                elif vals['state'] == 'cancel' and project.field_id.state != 'available':
                    project.field_id.write({
                        'state': 'available',
                        'current_crop_id': False,
                    })
        return result
    
    # State field is defined above
    
    @api.onchange('crop_id')
    def _onchange_crop_id(self):
        """When crop changes, suggest appropriate BOM"""
        self.crop_bom_id = False
        if self.crop_id:
            default_bom = self.env['farm.crop.bom'].search([
                ('crop_id', '=', self.crop_id.id),
                ('is_default', '=', True)
            ], limit=1)
            if default_bom:
                self.crop_bom_id = default_bom.id
    
    @api.onchange('start_date', 'crop_id')
    def _onchange_dates(self):
        """Calculate end date based on crop growing cycle"""
        if self.start_date and self.crop_id and self.crop_id.growing_cycle:
            self.planned_end_date = self.start_date + timedelta(days=self.crop_id.growing_cycle)
    
    @api.onchange('farm_id')
    def _onchange_farm_id(self):
        """Clear field_id when farm changes to ensure proper domain filtering"""
        self.field_id = False
    
    @api.depends('cost_line_ids.cost_amount', 'daily_report_ids.actual_cost')
    def _compute_actual_cost(self):
        """Compute actual costs from cost analysis lines and daily reports"""
        for project in self:
            # Get costs from cost lines
            cost_line_total = sum(project.cost_line_ids.mapped('cost_amount'))
            
            # Get costs from confirmed/done daily reports if not already in cost lines
            daily_report_total = 0
            for report in project.daily_report_ids.filtered(lambda r: r.state == 'done'):
                # Only include report costs that haven't been explicitly added as cost lines
                existing_cost_line = project.cost_line_ids.filtered(lambda l: 
                    l.source_type == 'daily_report' and l.source_id == report.id)
                if not existing_cost_line:
                    daily_report_total += report.actual_cost
            
            project.actual_cost = cost_line_total + daily_report_total
    
    @api.depends('actual_cost', 'revenue')
    def _compute_profit(self):
        """Compute profit as revenue minus actual cost"""
        for project in self:
            project.profit = project.revenue - project.actual_cost
    
    def _compute_daily_report_count(self):
        """Count the number of daily reports for this project"""
        for project in self:
            project.daily_report_count = len(project.daily_report_ids)
            
    def _compute_task_count(self):
        """Count the number of tasks in the related project"""
        for record in self:
            if record.project_id:
                record.task_count = self.env['project.task'].search_count([
                    ('project_id', '=', record.project_id.id)
                ])
            else:
                record.task_count = 0
                
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        """
        Override read_group to always display all states and handle aggregated fields correctly.
        This ensures all kanban columns appear even when empty.
        """
        # If we're grouping by state and using the _expand_states method,
        # we can just let the standard approach work
        if groupby and groupby[0] == 'state' and lazy:
            # The _expand_states method will be called automatically
            return super().read_group(domain, fields, groupby, offset, limit, orderby, lazy)
            
        # For other cases or if we need more control:
        # Create a safe copy of the fields to work with
        fields_copy = fields.copy() if fields else []
        
        # Process result with super (original method)
        result = super().read_group(domain, fields_copy, groupby, offset, limit, orderby, lazy)
        
        # Only handle non-lazy state grouping case manually
        if not lazy and groupby and groupby[0] == 'state':
            # First, identify all aggregated fields in the results
            aggregated_fields = set()
            for rec in result:
                aggregated_fields.update(k for k in rec.keys() if ':' in k)
                
            # Get all possible state values
            all_states = [s[0] for s in self._fields['state'].selection]
            
            # Collect states that already have groups
            existing_states = set(rec['state'] for rec in result if rec.get('state'))
            
            # Add missing state groups with count 0
            for state in all_states:
                if state not in existing_states:
                    # Create a new group for this state with proper count field
                    dummy_group = {
                        'state': state,
                        '__count': 0,
                        'state_count': 0,
                        '__domain': expression.AND([domain, [('state', '=', state)]]),
                    }
                    
                    # Make sure all aggregated fields that appear in other groups are added to this one
                    for field in aggregated_fields:
                        dummy_group[field] = 0  # Initialize aggregated fields with 0
                    
                    # Add any requested non-aggregated fields
                    for field in fields_copy:
                        if field != 'state' and ':' not in field and field not in dummy_group:
                            field_obj = self._fields.get(field)
                            if field_obj and field_obj.type in ['integer', 'float', 'monetary']:
                                dummy_group[field] = 0
                            else:
                                dummy_group[field] = False
                    
                    result.append(dummy_group)
                    
        return result
        
        return result
        
    @api.model
    def _expand_states(self, states, domain, order):
        """
        Helper method for kanban view to show all states.
        
        Args:
            states: List of states present in the data
            domain: Domain used for the query
            order: Ordering string
            
        Returns:
            list: Complete list of all possible state values
        """
        return [state[0] for state in self._fields['state'].selection]
    
    def action_view_daily_reports(self):
        """Smart button action to view daily reports"""
        self.ensure_one()
        return {
            'name': _('Daily Reports'),
            'view_mode': 'list,form',
            'res_model': 'farm.daily.report',
            'domain': [('project_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_project_id': self.id}
        }
    
    def action_view_tasks(self):
        """Smart button action to view tasks"""
        self.ensure_one()
        return {
            'name': _('Tasks'),
            'view_mode': 'list,form',
            'res_model': 'project.task',
            'domain': [('project_id', '=', self.project_id.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_project_id': self.project_id.id}
        }
    
    def action_draft(self):
        """Set to draft state"""
        return self.write({'state': 'draft'})
    
    def action_preparation(self):
        """Set to preparation state"""
        return self.write({'state': 'preparation'})
    
    def action_sowing(self):
        """Set to sowing state"""
        return self.write({'state': 'sowing'})
    
    def action_growing(self):
        """Set to growing state"""
        return self.write({'state': 'growing'})
    
    def action_harvest(self):
        """Set to harvest state"""
        return self.write({'state': 'harvest'})
    
    def action_done(self):
        """Set to done state"""
        return self.write({
            'state': 'done',
            'actual_end_date': fields.Date.today()
        })
    
    def action_cancel(self):
        """Set to cancelled state"""
        return self.write({'state': 'cancel'})
    
    @api.constrains('start_date', 'planned_end_date')
    def _check_dates(self):
        """Ensure end date is after start date"""
        for record in self:
            if record.planned_end_date and record.start_date and \
                    record.planned_end_date < record.start_date:
                raise ValidationError(_("End date must be after start date."))
    
    # We're using read_group override for state expansion instead of this method

    @api.model
    def _expand_states(self, states, domain, order=None, context=None):
        """
        Required method for kanban grouping by state.
        
        Args:
            states: List of states present in the data
            domain: Domain used for the query
            order: Ordering string
            context: Context information (added as required by Odoo v18)
            
        Returns:
            list: Complete list of all possible state values
        """
        # Always return all states for kanban grouping
        return [state[0] for state in self._fields['state'].selection]
