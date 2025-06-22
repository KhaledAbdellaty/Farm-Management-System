from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import date


class DailyReport(models.Model):
    _name = 'farm.daily.report'
    _description = 'Daily Farm Operation Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char('Reference', required=True, copy=False, readonly=True, 
                     default=lambda self: _('New'))
    date = fields.Date('Date', required=True, default=fields.Date.today, tracking=True)
    
    user_id = fields.Many2one('res.users', string='Reported By', 
                            default=lambda self: self.env.user, tracking=True)
    
    # Project and location information
    project_id = fields.Many2one('farm.cultivation.project', string='Cultivation Project', 
                              required=True, tracking=True, ondelete='cascade')
    farm_id = fields.Many2one('farm.farm', related='project_id.farm_id', 
                           string='Farm', store=True, readonly=True)
    field_id = fields.Many2one('farm.field', related='project_id.field_id', 
                            string='Field', store=True, readonly=True)
    crop_id = fields.Many2one('farm.crop', related='project_id.crop_id', 
                           string='Crop', store=True, readonly=True)
    
    # Operation details
    operation_type = fields.Selection([
        ('preparation', 'Field Preparation'),
        ('planting', 'Planting/Sowing'),
        ('fertilizer', 'Fertilizer Application'),
        ('pesticide', 'Pesticide Application'),
        ('irrigation', 'Irrigation'),
        ('weeding', 'Weeding'),
        ('harvesting', 'Harvesting'),
        ('maintenance', 'Maintenance'),
        ('inspection', 'Inspection'),
        ('other', 'Other'),
    ], string='Operation Type', required=True, tracking=True)
    
    # Progress tracking
    stage = fields.Selection(related='project_id.state', string='Project Stage', 
                          readonly=True, store=True)
    
    # Report status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
    ], string=_('Status'), default='draft', tracking=True)
    
    # Weather information
    temperature = fields.Float('Temperature (°C)', tracking=True)
    humidity = fields.Float('Humidity (%)', tracking=True)
    rainfall = fields.Float('Rainfall (mm)', tracking=True)
    
    # Resource usage
    labor_hours = fields.Float('Labor Hours', tracking=True)
    machinery_hours = fields.Float('Machinery Hours', tracking=True)
    
    # Products used (replacing single product field with multiple product lines)
    product_lines = fields.One2many('farm.daily.report.line', 'report_id',
                                  string=_('Products Used'))
    
    # Cost tracking
    cost_amount = fields.Monetary('Cost', currency_field='currency_id', tracking=True)
    estimated_cost = fields.Monetary(string=_('Estimated Cost'), compute='_compute_estimated_cost',
                                   store=True, currency_field='currency_id')
    actual_cost = fields.Monetary(string=_('Actual Cost'), compute='_compute_actual_cost',
                                store=True, currency_field='currency_id')
    
    # Inventory tracking
    stock_move_ids = fields.One2many('stock.move', 'daily_report_id', string=_('Stock Moves'))
    stock_picking_id = fields.Many2one('stock.picking', string=_('Inventory Operation'))
    
    # Analytic accounting
    analytic_line_ids = fields.One2many('account.analytic.line', 'daily_report_id', 
                                      string=_('Analytic Lines'))
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', 
                               readonly=True)
    company_id = fields.Many2one('res.company', related='project_id.company_id', 
                              readonly=True, store=True)
    
    # Observations and issues
    observation = fields.Text('Observations', translate=True, tracking=True)
    issues = fields.Text('Issues Encountered', translate=True, tracking=True)
    
    # Crop condition
    crop_condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('critical', 'Critical'),
    ], string='Crop Condition', tracking=True)
    
    notes = fields.Html('Notes', translate=True)
    
    # Images for documentation
    image_ids = fields.Many2many('ir.attachment', string='Images')
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate unique report reference number"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('farm.daily.report') or _('New')
        return super().create(vals_list)
    
    @api.onchange('project_id', 'operation_type')
    def _onchange_project_id(self):
        """Set default product based on project context"""
        if self.project_id and self.project_id.crop_bom_id and self.operation_type:
            # Try to find a matching product from BOM lines based on operation type
            matching_operation_types = {
                'planting': 'seed',
                'fertilizer': 'fertilizer',
                'pesticide': 'pesticide',
                'weeding': 'herbicide',
                'irrigation': 'water',
            }
            bom_type = matching_operation_types.get(self.operation_type)
            if bom_type:
                bom_line = self.env['farm.crop.bom.line'].search([
                    ('bom_id', '=', self.project_id.crop_bom_id.id),
                    ('input_type', '=', bom_type)
                ], limit=1)
                if bom_line and not self.product_lines:
                    # Create a new product line with the found product
                    self.product_lines = [(0, 0, {
                        'product_id': bom_line.product_id.id,
                        'quantity': bom_line.quantity
                    })]
    
    @api.onchange('product_lines')
    def _onchange_product_lines(self):
        """Calculate cost based on product lines"""
        if self.product_lines:
            self.cost_amount = sum(line.product_id.standard_price * line.quantity for line in self.product_lines)
    
    @api.onchange('operation_type')
    def _onchange_operation_type(self):
        """Auto-update project state based on operation type if needed"""
        if not self.project_id:
            return
        
        operation_state_map = {
            'preparation': 'preparation',
            'planting': 'sowing',
            'harvesting': 'harvest',
        }
        
        if self.operation_type in operation_state_map:
            if self.project_id.state != 'done' and self.project_id.state != 'cancel':
                suggested_state = operation_state_map[self.operation_type]
                if suggested_state != self.project_id.state:
                    return {
                        'warning': {
                            'title': _('Project Stage Update'),
                            'message': _('Do you want to update the project stage to %s?') % 
                                dict(self.project_id._fields['state'].selection).get(suggested_state)
                        }
                    }
    
    @api.constrains('date')
    def _check_date(self):
        """Ensure report date is within project dates"""
        for report in self:
            if report.date and report.project_id:
                if report.date < report.project_id.start_date:
                    raise ValidationError(_("Report date cannot be before project start date."))
                if report.project_id.actual_end_date and report.date > report.project_id.actual_end_date:
                    raise ValidationError(_("Report date cannot be after project end date."))

    @api.depends('product_lines.estimated_cost', 'labor_hours', 'machinery_hours')
    def _compute_estimated_cost(self):
        """Compute total estimated cost from product lines and labor/machinery"""
        for report in self:
            labor_cost = report.labor_hours * (report.project_id.labor_cost_hour or 0)
            machinery_cost = report.machinery_hours * (report.project_id.machinery_cost_hour or 0)
            product_cost = sum(line.estimated_cost for line in report.product_lines)
            report.estimated_cost = labor_cost + machinery_cost + product_cost
    
    @api.depends('product_lines.actual_cost', 'labor_hours', 'machinery_hours')
    def _compute_actual_cost(self):
        """Compute total actual cost from product lines and labor/machinery"""
        for report in self:
            labor_cost = report.labor_hours * (report.project_id.labor_cost_hour or 0)
            machinery_cost = report.machinery_hours * (report.project_id.machinery_cost_hour or 0)
            product_cost = sum(line.actual_cost for line in report.product_lines)
            report.actual_cost = labor_cost + machinery_cost + product_cost
            
    def action_confirm(self):
        """Confirm the daily report and create stock moves"""
        for report in self:
            # Only process if there are product lines and we haven't created stock moves yet
            if report.product_lines and not report.stock_picking_id:
                report._create_stock_movements()
            
            report.state = 'confirmed'
        return True
    
    def action_set_to_done(self):
        """Set report to done and update analytic accounting"""
        for report in self:
            # Create analytic entries if they don't exist yet
            if not report.analytic_line_ids:
                report._create_analytic_entries()
                
            # Update project actual cost
            report._update_project_cost()
            
            report.state = 'done'
        return True
    
    def action_reset_to_draft(self):
        """Reset to draft and delete any stock moves and analytic entries"""
        for report in self:
            # Only delete stock moves if they exist and are not done yet
            if report.stock_picking_id and report.stock_picking_id.state not in ['done', 'cancel']:
                report.stock_picking_id.action_cancel()
                report.stock_picking_id.unlink()
                
            # Delete analytic lines
            if report.analytic_line_ids:
                report.analytic_line_ids.unlink()
                
            report.state = 'draft'
        return True
    
    def _create_stock_movements(self):
        """Create stock moves for the products used in the report"""
        for report in self:
            if not report.product_lines:
                continue
                
            # Get farm/project locations
            farm_location = report.project_id.farm_id.location_id
            if not farm_location:
                raise ValidationError(_("No location defined for the farm. Please set up a location for this farm."))
            
            # Get the destination location (it should be a virtual/consumption location)
            dest_location = self.env.ref('stock.location_production', raise_if_not_found=False)
            if not dest_location:
                dest_location = self.env['stock.location'].search([('usage', '=', 'production')], limit=1)
                if not dest_location:
                    raise ValidationError(_("No production/consumption location found in the system."))
            
            # Create picking
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('default_location_src_id', '=', farm_location.id)
            ], limit=1)
            
            if not picking_type:
                # Fall back to any internal transfer type
                picking_type = self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1)
                
            if not picking_type:
                raise ValidationError(_("No suitable picking type found for stock transfers."))
            
            picking_vals = {
                'location_id': farm_location.id,
                'location_dest_id': dest_location.id,
                'picking_type_id': picking_type.id,
                'scheduled_date': report.date,
                'origin': f'Daily Report {report.name}',
                'company_id': report.company_id.id,
            }
            
            picking = self.env['stock.picking'].create(picking_vals)
            report.stock_picking_id = picking.id
            
            # Create stock moves
            for line in report.product_lines:
                if not line.product_id.type in ['product', 'consu']:
                    continue
                
                move_vals = {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.uom_id.id,
                    'picking_id': picking.id,
                    'location_id': farm_location.id,
                    'location_dest_id': dest_location.id,
                    'state': 'draft',
                    'company_id': report.company_id.id,
                    'daily_report_id': report.id,
                    'origin': f'Daily Report {report.name}',
                }
                
                self.env['stock.move'].create(move_vals)
            
            # Confirm the picking if products are available
            if picking.move_lines:
                picking.action_confirm()
                # Try to assign products
                picking.action_assign()
                
                # If all products are available, auto-validate the transfer
                if all(move.state == 'assigned' for move in picking.move_lines):
                    for move_line in picking.move_line_ids:
                        move_line.qty_done = move_line.reserved_qty
                    picking.button_validate()
    
    def _create_analytic_entries(self):
        """Create analytic entries for costs related to the daily report"""
        for report in self:
            # Check if project has an analytic account
            if not report.project_id.analytic_account_id:
                continue
                
            analytic_account = report.project_id.analytic_account_id
            
            # Create analytic line for each type of cost
            
            # 1. Product costs
            for line in report.product_lines:
                if line.actual_cost <= 0:
                    continue
                    
                self.env['account.analytic.line'].create({
                    'name': f"{line.product_id.name} - {report.name}",
                    'date': report.date,
                    'account_id': analytic_account.id,
                    'amount': -line.actual_cost,  # Negative amount for costs
                    'unit_amount': line.quantity,
                    'product_id': line.product_id.id,
                    'product_uom_id': line.uom_id.id,
                    'general_account_id': line.product_id.categ_id.property_account_expense_categ_id.id if line.product_id.categ_id.property_account_expense_categ_id else False,
                    'daily_report_id': report.id,
                    'project_id': report.project_id.project_id.id if report.project_id.project_id else False,
                })
                
            # 2. Labor costs
            if report.labor_hours > 0:
                labor_cost = report.labor_hours * (report.project_id.labor_cost_hour or 0)
                if labor_cost > 0:
                    # Get labor expense account from config
                    labor_account_id = self.env['ir.config_parameter'].sudo().get_param(
                        'farm_management.labor_expense_account_id', False)
                    
                    labor_account = False
                    if labor_account_id:
                        labor_account = int(labor_account_id)
                        
                    if not labor_account:
                        # Fallback to a default expense account
                        expense_account = self.env['account.account'].search(
                            [('account_type', '=', 'expense')], limit=1)
                        labor_account = expense_account.id if expense_account else False
                    
                    if labor_account:
                        self.env['account.analytic.line'].create({
                            'name': f"Labor - {report.name}",
                            'date': report.date,
                            'account_id': analytic_account.id,
                            'amount': -labor_cost,  # Negative amount for costs
                            'unit_amount': report.labor_hours,
                            'general_account_id': labor_account,
                            'daily_report_id': report.id,
                            'project_id': report.project_id.project_id.id if report.project_id.project_id else False,
                        })
                        
            # 3. Machinery costs
            if report.machinery_hours > 0:
                machinery_cost = report.machinery_hours * (report.project_id.machinery_cost_hour or 0)
                if machinery_cost > 0:
                    # Get machinery expense account from config
                    machinery_account_id = self.env['ir.config_parameter'].sudo().get_param(
                        'farm_management.machinery_expense_account_id', False)
                    
                    machinery_account = False
                    if machinery_account_id:
                        machinery_account = int(machinery_account_id)
                        
                    if not machinery_account:
                        # Fallback to a default expense account
                        expense_account = self.env['account.account'].search(
                            [('account_type', '=', 'expense')], limit=1)
                        machinery_account = expense_account.id if expense_account else False
                    
                    if machinery_account:
                        self.env['account.analytic.line'].create({
                            'name': f"Machinery - {report.name}",
                            'date': report.date,
                            'account_id': analytic_account.id,
                            'amount': -machinery_cost,  # Negative amount for costs
                            'unit_amount': report.machinery_hours,
                            'general_account_id': machinery_account,
                            'daily_report_id': report.id,
                            'project_id': report.project_id.project_id.id if report.project_id.project_id else False,
                        })
    
    def _update_project_cost(self):
        """Update project's actual cost with costs from this report"""
        for report in self:
            if report.state == 'done' and report.actual_cost > 0:
                # Trigger recomputation of project costs
                report.project_id._compute_actual_cost()


class DailyReportLine(models.Model):
    _name = 'farm.daily.report.line'
    _description = _('Daily Report Line')
    
    report_id = fields.Many2one('farm.daily.report', string=_('Daily Report'), 
                              ondelete='cascade', required=True)
    product_id = fields.Many2one('product.product', string=_('Product'), required=True,
                               domain=[('type', 'in', ['product', 'consu'])])
    quantity = fields.Float(string=_('Quantity Used'), required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string=_('UoM'), related='product_id.uom_id', readonly=True)
    
    estimated_cost = fields.Monetary(string=_('Estimated Cost'), compute='_compute_estimated_cost',
                                   store=True, currency_field='currency_id')
    actual_cost = fields.Monetary(string=_('Actual Cost'), compute='_compute_actual_cost',
                                store=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='report_id.currency_id', string=_('Currency'))
    
    @api.depends('product_id', 'quantity')
    def _compute_estimated_cost(self):
        """Calculate estimated cost based on product standard price"""
        for line in self:
            line.estimated_cost = line.product_id.standard_price * line.quantity
    
    @api.depends('product_id', 'quantity')
    def _compute_actual_cost(self):
        """Calculate actual cost based on latest valuation or standard price"""
        for line in self:
            # Use the latest cost from stock valuation if available
            valuation = self.env['stock.valuation.layer'].search([
                ('product_id', '=', line.product_id.id),
                ('quantity', '>', 0),
                ('company_id', '=', line.report_id.company_id.id)
            ], order='create_date desc', limit=1)
            
            if valuation and valuation.quantity > 0:
                unit_cost = valuation.value / valuation.quantity
            else:
                unit_cost = line.product_id.standard_price
                
            line.actual_cost = unit_cost * line.quantity
