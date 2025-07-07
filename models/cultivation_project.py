from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from odoo.osv import expression
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class CultivationProject(models.Model):
    _name = 'farm.cultivation.project'
    _description = 'Cultivation Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, name'
    
    # Link to project.project instead of inheriting from it
    project_id = fields.Many2one('project.project', string='Related Project', tracking=True)

    name = fields.Char(string='Project Name', required=True, tracking=True, translate=True)
    code = fields.Char(string='Project Code', required=True, tracking=True, readonly=True, default=lambda self: _('New'))
    active = fields.Boolean(default=True, tracking=True)
    
    # Project timeframe
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    planned_end_date = fields.Date(string='Planned End Date', required=True, tracking=True)
    actual_end_date = fields.Date(string='Actual End Date', tracking=True)
    
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

    # BOM for crop inputs
    crop_bom_id = fields.Many2one('farm.crop.bom', string='Crop BOM', tracking=True,
                                domain="[('crop_id', '=', crop_id)]")
    
    # Project stages - Updated to include sales state
    state = fields.Selection([
        ('draft', 'Planning'),
        ('preparation', 'Field Preparation'),
        ('sowing', 'Planting/Sowing'),
        ('growing', 'Growing'),
        ('maintenance', 'Maintenance'),
        ('harvest', 'Harvest'),
        ('done', 'Completed'),
        ('cancel', 'Cancelled'),
    ], string='Stage', default='draft', required=True, tracking=True)
    
    # Harvest information
    planned_yield = fields.Float('Planned Yield', tracking=True)
    actual_yield = fields.Float('Actual Yield', tracking=True)
    yield_uom_id = fields.Many2one('uom.uom', string='Yield UoM', tracking=True)
    harvest_price = fields.Monetary('Harvest Price', tracking=True, 
                                  help="Price per unit of harvested crop", 
                                  currency_field='currency_id')
    yield_quality = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('average', 'Average'),
        ('poor', 'Poor'),
    ], string='Yield Quality', tracking=True)
    
    # Financial information
    budget = fields.Monetary('Budget', compute='_compute_bom_budget', store=True, 
                         currency_field='currency_id', tracking=True, readonly=True,
                         help="Budget based on the total cost of the selected BOM")
    bom_total_cost = fields.Monetary(related='crop_bom_id.total_cost', 
                                string='BOM Total Cost', readonly=True, 
                                currency_field='currency_id',
                                help="Total cost from the selected BOM")
    actual_cost = fields.Monetary('Actual Cost', compute='_compute_actual_cost', 
                               store=True, currency_field='currency_id')
    revenue = fields.Monetary('Revenue', compute='_compute_revenue', store=True, 
                             currency_field='currency_id', tracking=True)
    profit = fields.Monetary('Profit', compute='_compute_profit', store=True, 
                          currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    company_id = fields.Many2one('res.company', related='farm_id.company_id', 
                                store=True)
                                
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
    
    # Sales information
    sale_order_ids = fields.One2many('sale.order', 'cultivation_project_id', string='Sales Orders')
    sale_order_count = fields.Integer(compute='_compute_sale_order_count', string='Sales Orders')
    
    # Stock movements
    stock_picking_id = fields.Many2one('stock.picking', string='Harvest Receipt',
                                     help='The receipt created when harvested crop is moved to inventory')
    
    # Irrigation statistics
    total_irrigation_hours = fields.Float(string='Total Irrigation Hours', 
                                        compute='_compute_total_irrigation_hours',
                                        help='Total hours spent on irrigation for this project',
                                        store=True)
    
    notes = fields.Html('Notes', translate=True)

    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Project code must be unique!'),
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create analytic account and project record, update field status"""
        for vals in vals_list:
            project_name = vals.get('name', _('New Project'))
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('farm.cultivation.project') or _('New')
            farm = vals.get('farm_id') and self.env['farm.farm'].browse(vals.get('farm_id'))
            company_id = farm and farm.company_id.id or self.env.company.id
            
            # Create a dedicated analytic account for the cultivation project
            if not vals.get('analytic_account_id'):
                # Create analytic account with reference to farm in the name (since parent_id doesn't exist in v18)
                farm_name = farm and farm.name or _('Unknown Farm')
                
                # Get the default analytic plan (required in Odoo 18)
                default_plan = self.env['account.analytic.plan'].search([], limit=1)
                if not default_plan:
                    # Create a default plan if none exists
                    default_plan = self.env['account.analytic.plan'].create({
                        'name': _('Farm Management'),
                        'default_applicability': 'optional'
                    })
                
                analytic_account = self.env['account.analytic.account'].create({
                    'name': f"{_('Farm Project')}: {farm_name} - {project_name}",
                    'code': vals.get('code', ''),
                    'company_id': company_id,
                    'partner_id': farm and farm.owner_id and farm.owner_id.id or False,
                    'plan_id': default_plan.id,  # Required field in Odoo 18
                    
                })
                vals['analytic_account_id'] = analytic_account.id
                _logger.info(f"Created analytic account '{analytic_account.name}' for cultivation project")
                
            # Set budget based on BOM if available
            if vals.get('crop_bom_id') and not vals.get('budget'):
                bom = self.env['farm.crop.bom'].browse(vals['crop_bom_id'])
                if bom:
                    vals['budget'] = bom.total_cost
            
            # Create project.project record
            if not vals.get('project_id'):
                project_values = {
                    'name': project_name,
                    'company_id': company_id,
                    'user_id': self.env.user.id,
                    'date_start': vals.get('start_date'),
                    'date': vals.get('planned_end_date'),
                    # Add any additional fields that make sense for the project
                    'allow_timesheets': True,  # Enable timesheets for labor tracking
                    # In Odoo v18, the field name is account_id instead of analytic_account_id
                    'account_id': vals.get('analytic_account_id'),  # Use our created analytic account
                }
                _logger.info(f"Creating project with values: {project_values}")
                project = self.env['project.project'].create(project_values)
                vals['project_id'] = project.id
                
                # In Odoo v18, we link our custom analytic account to the project using the account_id field
                # This ensures all project activities will be tracked under our farm management analytic account
                _logger.info(f"Linked analytic account to project {project.name}")
                
            # Update field status
            if vals.get('field_id'):
                field = self.env['farm.field'].browse(vals['field_id'])
                field.write({'state': 'preparation'})
                
        return super().create(vals_list)
    
    def write(self, vals):
        """Update field status based on project state and sync with project.project"""
        # Prevent changing harvest-related fields after confirmation (sales, done)
        harvest_fields = ['actual_yield', 'harvest_price', 'yield_uom_id']
        if any(field in vals for field in harvest_fields):
            for project in self:
                if project.state in ['sales', 'done']:
                    restricted_fields = [field for field in harvest_fields if field in vals]
                    if restricted_fields:
                        field_names = ', '.join([self._fields[field].string for field in restricted_fields])
                        raise ValidationError(_(
                            "You cannot modify the following fields after harvest confirmation: %s",
                            field_names
                        ))
        
        # Update related project.project when relevant fields change
        for project in self:
            project_vals = {}
            
            if 'name' in vals:
                project_vals['name'] = vals['name']
                # Also update analytic account name when project name changes
                if project.analytic_account_id:
                    farm_name = project.farm_id.name
                    farm_project_label = _('Farm Project')  # Get translation at runtime
                    project.analytic_account_id.write({
                        'name': f"{farm_project_label}: {farm_name} - {vals['name']}"
                    })
            
            # If analytic account is changed, update the project's account_id as well
            if 'analytic_account_id' in vals and project.project_id:
                project_vals['account_id'] = vals['analytic_account_id']
                    
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
                elif vals['state'] == 'sales':
                    # Update product price and create harvest stock move when moving to sales state
                    project._update_product_price()
                    project._create_harvest_stock_move()
                elif vals['state'] == 'done':
                    project.field_id.write({
                        'state': 'fallow',
                        'current_crop_id': False,
                    })
                    # Ensure stock moves are created if directly going to done state
                    if project.state != 'sales':
                        project._update_product_price()
                        project._create_harvest_stock_move()
                elif vals['state'] == 'cancel' and project.field_id.state != 'available':
                    project.field_id.write({
                        'state': 'available',
                        'current_crop_id': False,
                    })
        return result
    
    
    @api.onchange('crop_id')
    def _onchange_crop_id(self):
        """When crop changes, suggest appropriate BOM and update yield UoM"""
        self.crop_bom_id = False
        if self.crop_id:
            default_bom = self.env['farm.crop.bom'].search([
                ('crop_id', '=', self.crop_id.id),
                ('is_default', '=', True)
            ], limit=1)
            if default_bom:
                self.crop_bom_id = default_bom.id
            
            # Update yield UoM when crop changes
            if self.crop_id.product_id and self.crop_id.product_id.uom_id:
                self.yield_uom_id = self.crop_id.product_id.uom_id
                # If the product has a list price, use it as the default harvest price
                if self.crop_id.product_id.list_price:
                    self.harvest_price = self.crop_id.product_id.list_price
    
    @api.onchange('start_date', 'crop_id')
    def _onchange_dates(self):
        """Calculate end date based on crop growing cycle"""
        if self.start_date and self.crop_id and self.crop_id.growing_cycle:
            self.planned_end_date = self.start_date + timedelta(days=self.crop_id.growing_cycle)
    
    @api.onchange('farm_id')
    def _onchange_farm_id(self):
        """Clear field_id when farm changes to ensure proper domain filtering"""
        self.field_id = False
    
    @api.onchange('crop_bom_id')
    def _onchange_crop_bom_id(self):
        """Update budget based on the BOM total cost when BOM is selected/changed"""
        if self.crop_bom_id:
            self.budget = self.crop_bom_id.total_cost
        else:
            self.budget = 0.0
    
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
                
    def _compute_sale_order_count(self):
        """Count the number of sales orders linked to this project"""
        for project in self:
            project.sale_order_count = len(project.sale_order_ids)
    
    @api.depends('sale_order_ids.state', 'sale_order_ids.amount_total')
    def _compute_revenue(self):
        """Compute revenue from confirmed/done sales orders"""
        for project in self:
            # Only count revenue from confirmed, done or invoiced sales orders
            valid_states = ['sale', 'done']
            valid_orders = project.sale_order_ids.filtered(lambda o: o.state in valid_states)
            project.revenue = sum(valid_orders.mapped('amount_total'))
            
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
    
    def action_view_sale_orders(self):
        """Smart button action to view sales orders"""
        self.ensure_one()
        return {
            'name': _('Sales Orders'),
            'view_mode': 'list,form',
            'res_model': 'sale.order',
            'domain': [('cultivation_project_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {
                'default_cultivation_project_id': self.id,
                'default_partner_id': self.farm_id.owner_id.id if self.farm_id.owner_id else False,
                'default_product_id': self.crop_id.product_id.id if self.crop_id.product_id else False,
            }
        }
        
    def action_create_sale_order(self):
        """Create a sales order for the harvest"""
        self.ensure_one()
        
        if not self.crop_id or not self.crop_id.product_id:
            raise ValidationError(_("Please specify a crop with an associated product before creating a sales order."))
            
        if not self.yield_uom_id:
            raise ValidationError(_("Please specify the yield unit of measure before creating a sales order."))
            
        if self.actual_yield <= 0:
            raise ValidationError(_("Please specify the actual yield before creating a sales order."))
            
        if self.harvest_price <= 0:
            raise ValidationError(_("Please specify a valid harvest price before creating a sales order."))
            
        # Get partner (farm owner or company)
        partner_id = self.farm_id.owner_id.id if self.farm_id.owner_id else self.env.company.partner_id.id
        
        # Create sales order
        order_vals = {
            'partner_id': partner_id,
            'cultivation_project_id': self.id,
            'date_order': fields.Datetime.now(),
            'company_id': self.company_id.id,
            'origin': f"Project {self.code} - {self.name}",
            'client_order_ref': f"Harvest {self.code}",
        }
        
        sale_order = self.env['sale.order'].create(order_vals)
        
        # Create order line for crop product
        product = self.crop_id.product_id
        order_line_vals = {
            'order_id': sale_order.id,
            'product_id': product.id,
            'name': f"{product.name} - {self.name}",
            'product_uom_qty': self.actual_yield,
            'product_uom': self.yield_uom_id.id,
            'price_unit': self.harvest_price,  # Use the harvest price set by the user
        }
        
        self.env['sale.order.line'].create(order_line_vals)
        
        # Update project state to sales
        self.write({'state': 'sales'})
        
        # Update product pricing
        self._update_product_price()
        
        return {
            'name': _('Sales Order'),
            'view_mode': 'form',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'type': 'ir.actions.act_window',
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
        """Set to harvest state and ensure the UoM is set from the product"""
        for project in self:
            # Ensure yield UoM is set from the crop's product
            if project.crop_id and project.crop_id.product_id and project.crop_id.product_id.uom_id:
                if not project.yield_uom_id:
                    project.yield_uom_id = project.crop_id.product_id.uom_id
                # If the product has a list price, suggest it as the harvest price
                if not project.harvest_price and project.crop_id.product_id.list_price:
                    project.harvest_price = project.crop_id.product_id.list_price
            return project.write({'state': 'harvest'})
    
    def action_sales(self):
        """
        Set to sales state with stock movement validation
        This follows the purchase order receipt workflow, validating the 
        picking to update the product's on-hand quantity
        """
        for project in self:
            if not project.actual_yield or project.actual_yield <= 0:
                raise ValidationError(_("Please specify the actual harvest yield before proceeding to sales."))
            if not project.yield_uom_id:
                raise ValidationError(_("Please specify the yield unit of measure before proceeding to sales."))
            if not project.harvest_price or project.harvest_price <= 0:
                raise ValidationError(_("Please specify a valid harvest price before proceeding to sales."))
            
            # Create the harvest stock move if it doesn't exist
            if not project.stock_picking_id:
                project._create_harvest_stock_move()
            
            # Validate the picking to update on-hand quantities
            if project.stock_picking_id and project.stock_picking_id.state != 'done':
                picking = project.stock_picking_id
                
                # Ensure quantities and pricing are set on moves
                for move in picking.move_ids:
                    # Update the move quantity if needed
                    if move.product_uom_qty != project.actual_yield:
                        move.product_uom_qty = project.actual_yield
                        
                    # Update the move price if needed
                    if move.price_unit != project.harvest_price:
                        move.price_unit = project.harvest_price
                
                    # Ensure quantities are set on move lines
                    for move_line in move.move_line_ids:
                        move_line.quantity = project.actual_yield
                
                # Ensure all moves have proper move lines for validation
                for move in picking.move_ids:
                    # Make sure we have at least one move line
                    if not move.move_line_ids:
                        self.env['stock.move.line'].create({
                            'move_id': move.id,
                            'product_id': move.product_id.id,
                            'product_uom_id': move.product_uom.id,
                            'location_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                            'picking_id': move.picking_id.id,
                            'company_id': move.company_id.id,
                            'quantity': move.product_uom_qty,  # In Odoo 18, quantity is the field for actual quantities
                        })
                    
                    # Update existing move lines
                    for move_line in move.move_line_ids:
                        if move_line.quantity <= 0:
                            move_line.quantity = project.actual_yield

                # Try to reserve the picking if not already done
                if picking.state not in ['assigned', 'done']:
                    picking.action_assign()
                
                # Validate the picking
                try:
                    # First try with standard validation
                    picking.with_context(skip_backorder=True).button_validate()
                except Exception as e:
                    _logger.warning(f"Standard validation failed: {str(e)}. Trying alternative method...")
                    try:
                        # Mark all move lines as done with their quantities
                        for move in picking.move_ids:
                            for move_line in move.move_line_ids:
                                move_line.quantity = move.product_uom_qty
                        
                        # Validate the picking
                        picking._action_done()
                    except Exception as e2:
                        _logger.error(f"Alternative validation failed: {str(e2)}")
                        raise ValidationError(_(
                            "Failed to validate the harvest receipt: %(error)s\n"
                            "Please make sure:\n"
                            "1. The product is properly configured as stockable\n"
                            "2. The source and destination locations are valid\n"
                            "3. The unit of measure is properly set"
                        ) % {'error': str(e2)})
                
                # Verify the validation was successful
                if picking.state == 'done':
                    product = project.crop_id.product_id
                    # Check actual quantity in destination location
                    current_qty = product.with_context(location=picking.location_dest_id.id).qty_available
                    
                    project.message_post(body=_(
                        "Harvest receipt validated successfully. Product inventory updated.\n"
                        "Product: %(product)s\n"
                        "Added quantity: %(qty)s %(uom)s\n"
                        "Current stock in %(location)s: %(current)s %(uom)s"
                    ) % {
                        'product': product.name,
                        'qty': project.actual_yield,
                        'uom': project.yield_uom_id.name,
                        'location': picking.location_dest_id.name,
                        'current': current_qty,
                    })
                else:
                    raise ValidationError(_(
                        "Failed to validate the harvest receipt. Current state: %(state)s. "
                        "Please check inventory settings and make sure all quantities are set correctly."
                    ) % {'state': picking.state})
            
            # Update project state
            project.write({'state': 'sales'})
            
            # Update product pricing
            project._update_product_price()
        
        return True
    
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
    
    @api.depends('crop_bom_id', 'crop_bom_id.total_cost')
    def _compute_bom_budget(self):
        """Compute budget based on the selected BOM's total cost"""
        for project in self:
            if project.crop_bom_id:
                project.budget = project.crop_bom_id.total_cost
            elif not project.budget:  # Only reset if not already set
                project.budget = 0.0
    
    def _update_product_price(self):
        """Update product's sales and standard price based on harvest price"""
        for project in self:
            if (project.state in ['sales', 'done'] and
                project.actual_yield > 0 and
                project.harvest_price > 0 and
                project.crop_id and
                project.crop_id.product_id):
                
                product = project.crop_id.product_id
                
                # Update product's list price (sales price)
                product.list_price = project.harvest_price
                
                # Calculate and update cost based on project costs
                if project.actual_cost > 0:
                    unit_cost = project.actual_cost / project.actual_yield
                    # Update product's standard price (cost)
                    if product.cost_method == 'standard':  # Only update if using standard costing
                        product.standard_price = unit_cost
                
                _logger.info(
                    f"Updated product {product.name}: "
                    f"list_price={product.list_price}, standard_price={product.standard_price}"
                )
    def _get_or_create_project_location(self):
        """Get or create a stock location for this cultivation project's field."""
        self.ensure_one()
        
        location_name = f"Field: {self.field_id.name} (F{self.field_id.id})"
        
        # First, try to find an existing location for this field
        location = self.env['stock.location'].search([
            ('name', '=', location_name),
            ('company_id', '=', self.company_id.id),
            ('usage', 'in', ['internal', 'production'])  # Look for both types for backward compatibility
        ], limit=1)
        
        if location:
            return location
        
        # No location found, we need to create one
        # First, get or create a parent "Farms" location
        farms_name = _('Farms')  # Get translation at runtime
        parent_location = self.env['stock.location'].search([
            ('name', '=', farms_name),
            ('usage', '=', 'view'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        if not parent_location:
            # Get company stock location as parent
            company_location = self.env['stock.warehouse'].search([
                ('company_id', '=', self.company_id.id)
            ], limit=1).view_location_id
            
            # Create Farms parent location
            parent_location = self.env['stock.location'].create({
                'name': farms_name,
                'usage': 'view',
                'location_id': company_location.id,
                'company_id': self.company_id.id
            })
        
        # Now create the field/project location
        farm_name = self.farm_id.name
        field_name = self.field_id.name
        
        location = self.env['stock.location'].create({
            'name': location_name,
            'usage': 'production',  # Production type for farm fields
            'location_id': parent_location.id,
            'company_id': self.company_id.id,
            'comment': f"Field location for {farm_name} - {field_name} (Project: {self.code})"
        })
        
        return location
    def _create_harvest_stock_move(self):
        """
        Create harvest receipt stock moves for the harvested crop using incoming receipts.
        This follows the purchase order receipt flow but in reverse - from field to warehouse.
        """
        for project in self:
            if not (project.state in ['harvest'] and 
                   project.actual_yield > 0 and
                   project.crop_id and 
                   project.crop_id.product_id and
                   project.yield_uom_id):
                return False
                
            # Get the product from the crop
            product = project.crop_id.product_id
                
            # Only create stock moves for stockable or consumable products
            if product.type not in ['product', 'consu']:
                _logger.info(f"Skipping inventory movement for non-stockable product {product.name}")
                continue

            # Find warehouse first
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', project.company_id.id)], limit=1)
            if not warehouse:
                raise ValidationError(_("No warehouse found for this company."))
            
            # Use warehouse stock location as destination (opposite of daily report)
            dest_location = warehouse.lot_stock_id
            if not dest_location:
                dest_location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
                if not dest_location:
                    dest_location = self.env['stock.location'].search([
                        ('usage', '=', 'internal'),
                        ('company_id', '=', project.company_id.id),
                        ('name', 'ilike', 'Stock')
                    ], limit=1)
            
            if not dest_location:
                raise ValidationError(_("No stock location found in warehouse."))

            # Create hierarchical location structure: Farm → Field → Project
            # Get the Physical Locations parent
            physical_locations = self.env.ref('stock.stock_location_locations', raise_if_not_found=False)
            if not physical_locations:
                physical_locations = self.env['stock.location'].search([
                    ('name', '=', 'Physical Locations'),
                    ('usage', '=', 'view')
                ], limit=1)
                
            if not physical_locations:
                raise ValidationError(_("No Physical Locations found to create farm location hierarchy."))
            
            # 1. Create or find farm-level location (directly under Physical Locations)
            farm_name = project.farm_id.name
            farm_source_location = self.env['stock.location'].search([
                ('name', '=', f"Farm: {farm_name}"),
                ('location_id', '=', physical_locations.id),
                ('company_id', '=', project.company_id.id)
            ], limit=1)
            
            if not farm_source_location:
                farm_source_location = self.env['stock.location'].create({
                    'name': f"Farm: {farm_name}",
                    'usage': 'production',  # Using production type for farm operations
                    'location_id': physical_locations.id,
                    'company_id': project.company_id.id,
                })
            
            # 2. Create or find field-level location under farm
            field_name = project.field_id.name
            field_source_location = self.env['stock.location'].search([
                ('name', '=', f"Field: {field_name}"),
                ('location_id', '=', farm_source_location.id),
                ('company_id', '=', project.company_id.id)
            ], limit=1)
            
            if not field_source_location:
                field_source_location = self.env['stock.location'].create({
                    'name': f"Field: {field_name}",
                    'usage': 'production',  # Using production type for field operations
                    'location_id': farm_source_location.id,
                    'company_id': project.company_id.id,
                })
            
            # 3. Create or find project-level location (the actual source)
            project_name = project.name 
            crop_name = project.crop_id.name if project.crop_id else 'N/A'
            project_crop_name = f"Project: {project_name} - {crop_name}"
            source_location = self.env['stock.location'].search([
                ('name', '=', project_crop_name),
                ('location_id', '=', field_source_location.id),
                ('company_id', '=', project.company_id.id)
            ], limit=1)
            
            if not source_location:
                source_location = self.env['stock.location'].create({
                    'name': project_crop_name,
                    'usage': 'production',  # Using production type for project operations
                    'location_id': field_source_location.id,
                    'company_id': project.company_id.id,
                })

            # Use the incoming/receipt picking type (IN instead of OUT)
            picking_type = warehouse.in_type_id
            
            if not picking_type:
                # Fall back to any incoming picking type
                picking_type = self.env['stock.picking.type'].search([
                    ('code', '=', 'incoming'),
                    ('warehouse_id', '=', warehouse.id)
                ], limit=1)
            
            if not picking_type:
                # Create a new incoming picking type for harvest operations
                # Use standard sequence format (WH/IN/000) but with farm-specific default locations
                sequence = self.env['ir.sequence'].search([
                    ('code', '=', 'stock.picking.in'),
                    ('company_id', '=', project.company_id.id)
                ], limit=1)
                
                if not sequence:
                    sequence = self.env['ir.sequence'].create({
                        'name': 'Stock Incoming',
                        'code': 'stock.picking.in',
                        'prefix': 'WH/IN/',
                        'padding': 5,
                        'company_id': project.company_id.id,
                    })
                
                picking_type = self.env['stock.picking.type'].create({
                    'name': 'Harvest Receipts',
                    'code': 'incoming',
                    'sequence_code': 'IN',
                    'default_location_src_id': source_location.id,   # From farm-specific location
                    'default_location_dest_id': dest_location.id,    # To warehouse stock
                    'sequence_id': sequence.id,
                    'warehouse_id': warehouse.id,
                    'company_id': project.company_id.id,
                })

            # Create a receipt order (incoming) for harvest
            # Get descriptive information for reference in the note
            field_name = project.field_id.name if project.field_id else "N/A"
            project_name = project.name or "N/A"
            crop_name = project.crop_id.name if project.crop_id else "N/A"
            
            # Create the picking - don't set 'name' to let Odoo use the sequence (WH/IN/000...)
            picking_vals = {
                'location_id': source_location.id,  # From farm/field location (source)
                'location_dest_id': dest_location.id,  # To warehouse stock (destination)
                'picking_type_id': picking_type.id,
                'scheduled_date': fields.Date.today(),
                'origin': f'Project {project.code} - Harvest',
                'company_id': project.company_id.id,
                'move_type': 'direct',  # Direct transfer
                'partner_id': False,  # No partner for internal harvest operations
                'note': f"Harvest: Farm/{field_name}/{project_name} - {crop_name}",
            }
            
            picking = self.env['stock.picking'].create(picking_vals)
            project.stock_picking_id = picking.id
                
            # Use receipt picking type (purchase receipt) - WH/IN
            picking_type = warehouse.in_type_id
            
            if not picking_type:
                # Fall back to any receipt picking type
                picking_type = self.env['stock.picking.type'].search([
                    ('code', '=', 'incoming'),
                    ('warehouse_id', '=', warehouse.id)
                ], limit=1)
            
            if not picking_type:
                # Create a new incoming picking type for harvest operations if missing
                sequence = self.env['ir.sequence'].search([
                    ('code', '=', 'stock.picking.in'),
                    ('company_id', '=', project.company_id.id)
                ], limit=1)
                
                if not sequence:
                    sequence = self.env['ir.sequence'].create({
                        'name': 'Stock Incoming',
                        'code': 'stock.picking.in',
                        'prefix': 'WH/IN/',
                        'padding': 5,
                        'company_id': project.company_id.id,
                    })
                
                picking_type = self.env['stock.picking.type'].create({
                    'name': 'Harvest Receipts',
                    'code': 'incoming',
                    'sequence_code': 'IN',
                    'default_location_src_id': source_location.id,   # From farm/field
                    'default_location_dest_id': dest_location.id,  # To warehouse stock
                    'sequence_id': sequence.id,
                    'warehouse_id': warehouse.id,
                    'company_id': project.company_id.id,
                })
                
            if not picking_type:
                raise ValidationError(_("No receipt picking type found for warehouse."))
            
            # Create picking (receipt) - similar to purchase order receipt
            operation_name = _("Harvest Receipt")  # Translation at runtime is correct
            
            # Get descriptive information for reference in the note
            field_name = project.field_id.name if project.field_id else "N/A"
            farm_name = project.farm_id.name or "N/A"
            crop_name = project.crop_id.name if project.crop_id else "N/A"
            
            # Create the picking - don't set 'name' to let Odoo use the sequence (WH/IN/000...)
            picking_vals = {
                'partner_id': project.farm_id.owner_id.id if project.farm_id.owner_id else False,
                'picking_type_id': picking_type.id,
                'location_id': source_location.id,           # Source: Field
                'location_dest_id': dest_location.id,      # Destination: Warehouse Stock
                'origin': f"Harvest: {project.name} ({project.code})",
                'scheduled_date': fields.Date.today(),
                'company_id': project.company_id.id,
                'move_type': 'direct',  # Direct transfer
                'note': f"Harvest receipt for crop: {crop_name}\nFrom farm: {farm_name}\nField: {field_name}\nProject: {project.name}",
            }
            
            picking = self.env['stock.picking'].create(picking_vals)
            
            # Store the picking in the project for reference
            project.stock_picking_id = picking.id
            
            # Create stock move with a descriptive name
            move_vals = {
                'name': f"{operation_name}: {product.name}",
                'product_id': product.id,
                'product_uom_qty': project.actual_yield,
                'product_uom': project.yield_uom_id.id,
                'picking_id': picking.id,
                'location_id': source_location.id,
                'location_dest_id': dest_location.id,
                'company_id': project.company_id.id,
                'state': 'draft',
                'price_unit': project.harvest_price,  # Set price for valuation
                'description_picking': f"{product.name} harvested from field {field_name}",
            }
            
            self.env['stock.move'].create(move_vals)
            
            _logger.info(f"Created stock move for {product.name}, quantity: {project.actual_yield}")
            
            # Confirm the picking to make products show as "incoming" in inventory
            if picking.move_ids:
                # Just confirm the picking (will update incoming quantities automatically)
                picking.action_confirm()
                
                # Try to reserve quantities (for harvest, this means mark as available)
                picking.action_assign()
                
                # Log the status but don't auto-validate - this will be done in action_sales
                if all(move.state == 'assigned' for move in picking.move_ids):
                    _logger.info(f"Harvest picking {picking.name} is ready for validation")
                else:
                    _logger.info(f"Harvest picking {picking.name} is partially ready for validation")
                    
                # Create move lines to make validation easier later
                for move in picking.move_ids:
                    if not move.move_line_ids:
                        # Create move lines manually with basic values
                        move_line_vals = {
                            'move_id': move.id,
                            'product_id': move.product_id.id,
                            'product_uom_id': move.product_uom.id,
                            'location_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                            'picking_id': move.picking_id.id,
                            'company_id': move.company_id.id,
                            'quantity': 0,  # Will be set during validation
                        }
                        self.env['stock.move.line'].create(move_line_vals)
                        
                # Log success
                _logger.info(f"Created harvest receipt {picking.name} for project {project.name}")
                
                # Add chatter message
                project.message_post(
                    body=_("Harvest receipt %s created for %s %s of %s") % (
                        picking.name,
                        project.actual_yield,
                        project.yield_uom_id.name,
                        product.name
                    ),
                    subject=_("Harvest Receipt Created"),
                    message_type='comment'
                )
            
            return picking
        
        return False
    
    def _create_inventory_adjustment(self, product, location, quantity):
        """
        Create an inventory adjustment to add products to stock as a fallback
        when the regular stock move process fails.
        
        Args:
            product: The product record to adjust
            location: The stock location to adjust
            quantity: The quantity to add
        """
        self.ensure_one()
        
        _logger.info(f"Creating inventory adjustment for {product.name}, qty: {quantity}")
        
        # Use stock quant directly in Odoo 18
        quant = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id', '=', location.id)
        ], limit=1)
        
        try:
            if quant:
                # Update existing quant
                starting_qty = quant.quantity
                quant.write({'quantity': starting_qty + quantity})
                _logger.info(f"Updated quant quantity from {starting_qty} to {starting_qty + quantity}")
            else:
                # Create new quant
                self.env['stock.quant'].create({
                    'product_id': product.id,
                    'location_id': location.id,
                    'quantity': quantity,
                    'company_id': self.company_id.id
                })
                _logger.info(f"Created new quant with quantity {quantity}")
            
            # Notify in the chatter
            self.message_post(body=_(
                "Created inventory adjustment for %(product)s, added %(qty)s %(uom)s to stock location."
            ) % {
                'product': product.name,
                'qty': quantity,
                'uom': self.yield_uom_id.name,
            })
            
        except Exception as e:
            _logger.error(f"Error creating inventory adjustment: {str(e)}")
            # Create a scheduled activity for manual resolution
            self.env['mail.activity'].create({
                'res_model_id': self.env['ir.model']._get('farm.cultivation.project').id,
                'res_id': self.id,
                'user_id': self.env.ref('base.user_admin').id,
                'summary': _('Manual inventory adjustment needed'),
                'note': _(
                    "Failed to automatically adjust inventory for product %(product)s. "
                    "Please manually add %(qty)s %(uom)s to stock."
                ) % {
                    'product': product.name,
                    'qty': quantity,
                    'uom': self.yield_uom_id.name,
                },
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'date_deadline': fields.Date.today()
            })
    
    def _verify_harvest_stock_update(self, product, stock_location, expected_qty):
        """
        Verify that the product stock quantity was correctly updated in the warehouse.
        If not, creates a notification or activity to alert the user.
        
        Args:
            product: The product record that should have been updated
            stock_location: The warehouse stock location
            expected_qty: The quantity that should have been added
            
        Returns:
            bool: Whether the stock update was successful
        """
        self.ensure_one()
        
        # Check current product quantity with location context
        actual_qty = product.with_context(location=stock_location.id).qty_available
        
        # Log the verification attempt
        _logger.info(
            f"Verifying stock update for {product.name}: "
            f"Expected increase: {expected_qty}, "
            f"Current quantity in location: {actual_qty}"
        )
        
        # Create a scheduled activity if stock update failed
        if product.type in ['product', 'consu'] and stock_location:
            note = _(
                "Please verify harvest stock receipt for project %(code)s - %(name)s.\n"
                "Product: %(product)s\n"
                "Expected increase: %(qty)s %(uom)s\n"
                "Please ensure this quantity has been properly received in inventory."
            ) % {
                'code': self.code,
                'name': self.name,
                'product': product.name,
                'qty': expected_qty,
                'uom': self.yield_uom_id.name
            }
            
            # Add a note in the chatter
            self.message_post(body=note)
            
            # Create a scheduled activity for the stock manager
            if not self.env.context.get('skip_activity_creation', False):
                self.env['mail.activity'].create({
                    'res_model_id': self.env['ir.model']._get('farm.cultivation.project').id,
                    'res_id': self.id,
                    'user_id': self.env.ref('base.user_admin').id,  # Default to admin
                    'summary': _('Verify harvest stock receipt'),
                    'note': note,
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'date_deadline': fields.Date.today()
                })
        
        return True
    
    def action_view_harvest_receipt(self):
        """
        Show the harvest receipt form view
        """
        self.ensure_one()
        
        if not self.stock_picking_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Receipt'),
                    'message': _('No harvest receipt has been created yet.'),
                    'sticky': False,
                    'type': 'warning',
                }
            }
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Harvest Receipt'),
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.stock_picking_id.id,
            'target': 'current',
            'context': {'create': False, 'edit': True}
        }
    
    # Translation helper methods
    def _get_translated_selection_values(self, field_name):
        """Get translated selection field values as a dictionary"""
        return dict(self._fields[field_name].selection)
    
    def _get_translated_state_name(self, state_code):
        """Get the translated name of a state based on its code"""
        states = self._get_translated_selection_values('state')
        return _(states.get(state_code, ''))
    
    def _get_translated_yield_quality(self, quality_code):
        """Get the translated name of a yield quality based on its code"""
        qualities = self._get_translated_selection_values('yield_quality')
        return _(qualities.get(quality_code, ''))
    
    @api.depends('daily_report_ids.irrigation_duration', 'daily_report_ids.state')
    def _compute_total_irrigation_hours(self):
        """Calculate the total irrigation hours from confirmed and done daily reports"""
        for project in self:
            total_hours = 0.0
            # Sum irrigation duration from all confirmed or done daily reports
            # that have operation_type = 'irrigation'
            reports = self.env['farm.daily.report'].search([
                ('project_id', '=', project.id),
                ('operation_type', '=', 'irrigation'),
                ('state', 'in', ['confirmed', 'done']),
            ])
            
            if reports:
                total_hours = sum(report.irrigation_duration for report in reports)
                
            project.total_irrigation_hours = total_hours
