from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import date
import logging

_logger = logging.getLogger(__name__)


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
            # Check if there's sufficient stock for all product lines
            if report.product_lines:
                unavailable_products = []
                
                # Force recompute of available_stock to ensure it's up to date
                for line in report.product_lines:
                    line._compute_available_stock()
                
                for line in report.product_lines:
                    # Skip services as they don't need inventory validation
                    if line.product_id.type == 'service':
                        continue
                    
                    # Only validate inventory for stockable and consumable products
                    if line.product_id.type in ['product', 'consu']:
                        # Check if we have enough quantity available
                        if line.quantity > line.available_stock:
                            unavailable_products.append({
                                'name': line.product_id.name,
                                'requested': line.quantity,
                                'available': line.available_stock,
                                'uom': line.uom_id.name
                            })
                
                # If any products are unavailable, show a validation error
                if unavailable_products:
                    error_message = _("Cannot confirm report due to insufficient inventory:\n\n")
                    for product in unavailable_products:
                        error_message += _("- %s: Requested %s %s, Available: %s %s\n") % (
                            product['name'], product['requested'], product['uom'],
                            product['available'], product['uom']
                        )
                    raise ValidationError(error_message)
                
                # If all products are available and we haven't created stock moves yet
                if not report.stock_picking_id:
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
        """Create delivery stock moves for the products used in the report using outgoing delivery orders"""
        for report in self:
            if not report.product_lines:
                continue
                
            # Find the warehouse first
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', report.company_id.id)], limit=1)
            if not warehouse:
                raise ValidationError(_("No warehouse found for this company."))
            
            # Use warehouse stock location as source (just like in sales orders)
            source_location = warehouse.lot_stock_id
            if not source_location:
                source_location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
                if not source_location:
                    source_location = self.env['stock.location'].search([
                        ('usage', '=', 'internal'),
                        ('company_id', '=', report.company_id.id),
                        ('name', 'ilike', 'Stock')
                    ], limit=1)
            
            if not source_location:
                raise ValidationError(_("No stock location found in warehouse."))
                
            # Still keep track of farm location for references, but don't use it as source
            farm_location = report.project_id.farm_id.location_id
            if not farm_location:
                # Auto-create a location for the farm if missing
                parent_location = self.env.ref('stock.stock_location_locations', raise_if_not_found=False)
                if not parent_location:
                    parent_location = self.env['stock.location'].search([('usage', '=', 'view')], limit=1)
                
                if not parent_location:
                    raise ValidationError(_("No parent stock location found to create farm location."))
                    
                farm_location = self.env['stock.location'].create({
                    'name': report.project_id.farm_id.name,
                    'usage': 'internal',
                    'location_id': parent_location.id,
                    'company_id': report.project_id.farm_id.company_id.id,
                })
                # Update the farm record
                report.project_id.farm_id.location_id = farm_location.id
            
            # Create a clean hierarchical location structure: Farm → Field → Project
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
            farm_name = report.farm_id.name
            farm_dest_location = self.env['stock.location'].search([
                ('name', '=', f"Farm: {farm_name}"),
                ('location_id', '=', physical_locations.id),
                ('company_id', '=', report.company_id.id)
            ], limit=1)
            
            if not farm_dest_location:
                farm_dest_location = self.env['stock.location'].create({
                    'name': f"Farm: {farm_name}",
                    'usage': 'production',  # Using production type for farm operations
                    'location_id': physical_locations.id,
                    'company_id': report.company_id.id,
                })
            
            # 2. Create or find field-level location under farm
            field_name = report.field_id.name
            field_dest_location = self.env['stock.location'].search([
                ('name', '=', f"Field: {field_name}"),
                ('location_id', '=', farm_dest_location.id),
                ('company_id', '=', report.company_id.id)
            ], limit=1)
            
            if not field_dest_location:
                field_dest_location = self.env['stock.location'].create({
                    'name': f"Field: {field_name}",
                    'usage': 'production',  # Using production type for field operations
                    'location_id': farm_dest_location.id,
                    'company_id': report.company_id.id,
                })
            
            # 3. Create or find project-level location (the actual destination)
            project_name = report.project_id.name 
            crop_name = report.crop_id.name if report.crop_id else 'N/A'
            project_crop_name = f"Project: {project_name} - {crop_name}"
            dest_location = self.env['stock.location'].search([
                ('name', '=', project_crop_name),
                ('location_id', '=', field_dest_location.id),
                ('company_id', '=', report.company_id.id)
            ], limit=1)
            
            if not dest_location:
                dest_location = self.env['stock.location'].create({
                    'name': project_crop_name,
                    'usage': 'production',  # Using production type for project operations
                    'location_id': field_dest_location.id,
                    'company_id': report.company_id.id,
                })
            
            # Find the warehouse
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', report.company_id.id)], limit=1)
            if not warehouse:
                raise ValidationError(_("No warehouse found for this company."))
                
            # Use the outgoing/delivery picking type
            picking_type = warehouse.out_type_id
            
            if not picking_type:
                # Fall back to any outgoing picking type
                picking_type = self.env['stock.picking.type'].search([
                    ('code', '=', 'outgoing'),
                    ('warehouse_id', '=', warehouse.id)
                ], limit=1)
            
            if not picking_type:
                # Create a new outgoing picking type for farm operations
                # Use standard sequence format (WH/OUT/000) but with farm-specific default locations
                sequence = self.env['ir.sequence'].search([
                    ('code', '=', 'stock.picking.out'),
                    ('company_id', '=', report.company_id.id)
                ], limit=1)
                
                if not sequence:
                    sequence = self.env['ir.sequence'].create({
                        'name': 'Stock Outgoing',
                        'code': 'stock.picking.out',
                        'prefix': 'WH/OUT/',
                        'padding': 5,
                        'company_id': report.company_id.id,
                    })
                
                picking_type = self.env['stock.picking.type'].create({
                    'name': 'Farm Operations',
                    'code': 'outgoing',
                    'sequence_code': 'OUT',
                    'default_location_src_id': source_location.id,  # From warehouse stock
                    'default_location_dest_id': dest_location.id,   # To farm-specific location
                    'sequence_id': sequence.id,
                    'warehouse_id': warehouse.id,
                    'company_id': report.company_id.id,
                })
            
            # Create a delivery order (outgoing) for farm consumption
            operation_name = dict(report._fields['operation_type'].selection).get(report.operation_type, 'Consumption')
            
            # Get descriptive information for reference in the note
            field_name = report.field_id.name if report.field_id else "N/A"
            project_name = report.project_id.name or "N/A"
            crop_name = report.crop_id.name if report.crop_id else "N/A"
            
            # Create the picking - don't set 'name' to let Odoo use the sequence (WH/OUT/000...)
            picking_vals = {
                'location_id': source_location.id,  # Use warehouse stock location as source
                'location_dest_id': dest_location.id,
                'picking_type_id': picking_type.id,
                'scheduled_date': report.date,
                'origin': f'Report {report.name} - {operation_name}',
                'company_id': report.company_id.id,
                'move_type': 'direct',  # Direct transfer (as opposed to 'one' which is partial)
                'partner_id': False,  # No partner is fine for farm operations
                'note': f"Farm/{field_name}/{project_name} - {crop_name} - {operation_name}",
                # Don't set name - let Odoo use the standard sequence (WH/OUT/000)
            }
            
            picking = self.env['stock.picking'].create(picking_vals)
            report.stock_picking_id = picking.id
            
            # Create stock moves for the delivery order
            for line in report.product_lines:
                # Only create stock moves for stockable/consumable products
                if not line.product_id.type in ['product', 'consu']:
                    continue
                    
                # Make sure quantity is always > 0
                if line.quantity <= 0:
                    continue
                    
                operation_name = dict(report._fields['operation_type'].selection).get(report.operation_type, 'Consumption')
                
                # Include field/project/crop in the move description
                field_name = report.field_id.name if report.field_id else "N/A"
                project_name = report.project_id.name or "N/A"
                crop_name = report.crop_id.name if report.crop_id else "N/A"
                
                move_vals = {
                    'name': f"{line.product_id.name}",
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.uom_id.id,
                    'picking_id': picking.id,
                    'location_id': source_location.id,  # Use warehouse stock location as source
                    'location_dest_id': dest_location.id,
                    'state': 'draft',
                    'company_id': report.company_id.id,
                    'daily_report_id': report.id,
                    'origin': f'Report {report.name}',
                    'description_picking': f"{line.product_id.name} - Farm/{field_name}/{project_name}",
                }
                
                self.env['stock.move'].create(move_vals)
                
            # Confirm the picking to make products show as "outgoing" in inventory
            if picking.move_ids:
                # Just confirm the picking (will update outgoing quantities automatically)
                picking.action_confirm()
                
                # Try to reserve quantities
                picking.action_assign()
                
                # Log the status but don't auto-validate - this will be done manually
                if all(move.state == 'assigned' for move in picking.move_ids):
                    _logger.info(f"Picking {picking.name} is ready for manual validation")
                else:
                    _logger.info(f"Picking {picking.name} is partially ready for manual validation")
                    
                # Create move lines to make validation easier later
                for move in picking.move_ids:
                    if not move.move_line_ids:
                        move._create_move_line()
                        
                    # Set quantities on move lines
                    for line in move.move_line_ids:
                        if line.quantity <= 0:
                            line.quantity = move.product_uom_qty
    
    def _create_analytic_entries(self):
        """Create analytic entries for costs related to the daily report"""
        for report in self:
            # Get the analytic account from the cultivation project's analytic_account_id field
            # not from project.project which doesn't have this field in Odoo v18
            if not report.project_id or not report.project_id.analytic_account_id:
                continue
                
            analytic_account = report.project_id.analytic_account_id
            
            # Create analytic line for each type of cost
            
            # 1. Product costs
            for line in report.product_lines:
                # Force recompute of estimated cost to ensure it's properly calculated
                line._compute_estimated_cost()
                
                # Calculate the product cost - make sure it's never zero for used products
                product_cost = line.estimated_cost
                if product_cost <= 0 and line.quantity > 0:
                    # If estimated cost is zero but product is used, use a fallback cost
                    # Try to get a reasonable cost from the product's standard price
                    product_cost = line.product_id.standard_price * line.quantity
                    _logger.warning(f"Using fallback cost calculation for {line.product_id.name}: {product_cost}")
                
                # For products that have no cost elsewhere in the system, we need to ensure we use
                # a minimal cost value to ensure analytic entries are created
                if product_cost <= 0 and line.quantity > 0:
                    # Set minimum default value (1.0 per unit) if all other cost calculations fail
                    product_cost = line.quantity * 1.0
                    _logger.warning(f"Using minimum default cost of 1.0/unit for {line.product_id.name}: {product_cost}")
                
                if product_cost <= 0:
                    _logger.warning(f"Skipping analytic entry for product {line.product_id.name} with zero cost")
                    continue
                    
                # Look for validated stock moves for this product to get actual cost
                stock_cost = 0.0
                validated_moves = self.env['stock.move'].search([
                    ('daily_report_id', '=', report.id),
                    ('product_id', '=', line.product_id.id),
                    ('state', '=', 'done')
                ])
                
                if validated_moves:
                    # Calculate actual cost from validated stock moves
                    stock_qty = sum(move.product_uom_qty for move in validated_moves)
                    if stock_qty > 0:
                        # Try to get actual cost
                        try:
                            # Try different approaches to get the actual cost from stock moves in Odoo 18
                            
                            # First approach: Get cost from accounting entries
                            for move in validated_moves:
                                try:
                                    if hasattr(move, 'account_move_ids') and move.account_move_ids:
                                        expense_lines = move.account_move_ids.mapped('line_ids').filtered(
                                            lambda l: l.account_id.account_type == 'expense'
                                        )
                                        if expense_lines:
                                            move_cost = sum(expense_lines.mapped('balance'))
                                            stock_cost += abs(move_cost)  # Use absolute value to ensure positive cost
                                except Exception as e:
                                    _logger.error(f"Error accessing account move data: {str(e)}")
                            
                            _logger.info(f"Actual cost from account entries for {line.product_id.name}: {stock_cost}")
                            
                            # Second approach: Try to get from stock valuation layer if available
                            if stock_cost <= 0:
                                try:
                                    # Check if the model exists before trying to use it
                                    if 'stock.valuation.layer' in self.env:
                                        StockValuationLayer = self.env['stock.valuation.layer']
                                        layers = StockValuationLayer.search([
                                            ('stock_move_id', 'in', validated_moves.ids)
                                        ])
                                        if layers:
                                            stock_cost = sum(layer.value for layer in layers)
                                            _logger.info(f"Cost from stock valuation layers for {line.product_id.name}: {stock_cost}")
                                except Exception as val_error:
                                    _logger.error(f"Error getting valuation layers: {str(val_error)}")
                            
                            # Third approach: Try to get unit cost * quantity
                            if stock_cost <= 0:
                                try:
                                    for move in validated_moves:
                                        move_cost = 0
                                        if hasattr(move, 'price_unit') and move.price_unit:
                                            move_cost = move.price_unit * move.product_qty
                                        # Use careful attribute checking to avoid AttributeError
                                        stock_cost += move_cost
                                    _logger.info(f"Cost from move price_unit for {line.product_id.name}: {stock_cost}")
                                except Exception as price_error:
                                    _logger.error(f"Error calculating cost from price_unit: {str(price_error)}")
                            
                            # Last resort: use standard price
                            if stock_cost <= 0:
                                stock_cost = line.product_id.standard_price * line.quantity
                                _logger.info(f"Using standard price for {line.product_id.name}: {stock_cost}")
                        except Exception as e:
                            _logger.error(f"Error calculating stock cost: {str(e)}")
                            stock_cost = 0
                
                # Determine final cost - prefer actual cost from stock moves, then computed actual cost,
                # then estimated cost from product
                if stock_cost > 0:
                    analytic_amount = -stock_cost
                    _logger.info(f"Using validated stock move cost for {line.product_id.name}: {stock_cost}")
                elif line.actual_cost > 0:
                    analytic_amount = -line.actual_cost
                    _logger.info(f"Using computed actual cost for {line.product_id.name}: {line.actual_cost}")
                else:
                    analytic_amount = -product_cost
                    _logger.info(f"Using estimated cost for {line.product_id.name}: {product_cost}")
                
                # Create the analytic entry
                self.env['account.analytic.line'].create({
                    'name': f"{line.product_id.name} - {report.name}",
                    'date': report.date,
                    'account_id': analytic_account.id,
                    'amount': analytic_amount,  # Negative amount for costs
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


class StockMove(models.Model):
    _inherit = 'stock.move'
    
    # Add link to daily report
    daily_report_id = fields.Many2one('farm.daily.report', string='Daily Report',
                                    index=True, ondelete='set null')
    
    def write(self, vals):
        """Override write to update daily report state when stock moves are validated"""
        result = super(StockMove, self).write(vals)
        
        # If state changed to 'done', update associated daily report
        if 'state' in vals and vals['state'] == 'done':
            # Get all unique daily reports from these moves
            report_ids = self.mapped('daily_report_id')
            
            if report_ids:
                # Log the state change for debugging
                _logger.info(f"Stock moves validated for daily reports: {report_ids.mapped('name')}")
                
                # In Odoo 18, make sure move line quantities are confirmed properly
                for move in self:
                    if move.state == 'done':
                        # Log accounting information for debugging
                        _logger.info(f"Validated move {move.id} for product {move.product_id.name}, "
                                    f"quantity: {move.product_uom_qty}")
                        
                        # If this is a valued move, log additional details
                        try:
                            if hasattr(move, 'account_move_ids'):
                                account_moves = move.account_move_ids
                                if account_moves:
                                    _logger.info(f"Move {move.id} has accounting entries: "
                                                f"{account_moves.mapped('name')}")
                                    for amove in account_moves:
                                        if hasattr(amove, 'line_ids'):
                                            for line in amove.line_ids:
                                                _logger.info(f"Account move line: {line.name}, "
                                                            f"account: {line.account_id.name}, "
                                                            f"balance: {line.balance}")
                        except Exception as e:
                            _logger.error(f"Error accessing accounting data: {str(e)}")
                
                # Process each related daily report
                for report in report_ids.filtered(lambda r: r.state == 'confirmed'):
                    # If all stock moves for this report are done, set report to done
                    related_moves = self.env['stock.move'].search([
                        ('daily_report_id', '=', report.id)
                    ])
                    
                    done_moves = related_moves.filtered(lambda m: m.state == 'done')
                    
                    # If all required moves are done
                    if all(move.state == 'done' for move in related_moves if move.product_id.type in ['product', 'consu']):
                        _logger.info(f"Setting daily report {report.name} to 'done' due to stock move validation")
                        report.state = 'done'
                        
                        # Force recompute of product line costs based on validated stock moves before creating analytic entries
                        for line in report.product_lines:
                            validated_moves = done_moves.filtered(lambda m: m.product_id.id == line.product_id.id)
                            if validated_moves:
                                _logger.info(f"Product {line.product_id.name} has {len(validated_moves)} validated moves")
                        
                        # Create analytic entries with updated costs
                        if not report.analytic_line_ids:
                            report._create_analytic_entries()
        
        return result


class DailyReportLine(models.Model):
    _name = 'farm.daily.report.line'
    _description = 'Daily Report Product Line'
    
    report_id = fields.Many2one('farm.daily.report', string='Report', 
                             required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string=_('Product'), required=True)
    quantity = fields.Float(string=_('Quantity'), default=1.0)
    uom_id = fields.Many2one('uom.uom', string=_('UoM'), 
                         related='product_id.uom_id', readonly=True)
                         
    # Stock availability
    available_stock = fields.Float(string=_('On Hand'), compute='_compute_available_stock',
                                store=False, digits='Product Unit of Measure')
    product_availability = fields.Selection([
        ('not_tracked', 'Not Tracked'),
        ('no_stock', 'No Stock'),
        ('low_stock', 'Low Stock'),
        ('available', 'Available'),
    ], string=_('Availability'), compute='_compute_available_stock', store=False)
    
    # Cost information
    estimated_cost = fields.Monetary(string=_('Estimated Cost'), 
                                   compute='_compute_estimated_cost', store=True,
                                   currency_field='currency_id')
    actual_cost = fields.Monetary(string=_('Actual Cost'), 
                               compute='_compute_actual_cost', store=True,
                               currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='report_id.currency_id')
    
    @api.depends('product_id', 'quantity')
    def _compute_estimated_cost(self):
        """Calculate estimated cost based on product standard price"""
        for line in self:
            if line.product_id:
                standard_price = line.product_id.standard_price or 0.0
                line.estimated_cost = standard_price * line.quantity
            else:
                line.estimated_cost = 0.0
    
    @api.depends('product_id', 'quantity', 'report_id.stock_move_ids.state')
    def _compute_actual_cost(self):
        """Calculate actual cost from validated stock moves or fallback to standard price"""
        for line in self:
            if not line.product_id:
                line.actual_cost = 0.0
                continue
                
            # For services, use standard pricing as they're not tracked in inventory
            if line.product_id.type == 'service':
                line.actual_cost = line.estimated_cost
                continue
                
            # Look for validated stock moves for this product in this report
            moves = self.env['stock.move'].search([
                ('daily_report_id', '=', line.report_id.id),
                ('product_id', '=', line.product_id.id),
                ('state', '=', 'done')
            ])
            
            if moves:
                # Use the actual valuation from the stock moves
                # This gets the real cost from accounting entries
                try:
                    total_cost = sum(move.product_price_value_unit * move.product_qty for move in moves)
                    total_qty = sum(move.product_qty for move in moves)
                    # If we have quantities, calculate unit cost and multiply by line qty
                    if total_qty > 0:
                        unit_cost = total_cost / total_qty
                        line.actual_cost = unit_cost * line.quantity
                    else:
                        line.actual_cost = line.estimated_cost
                except Exception as e:
                    _logger.warning(f"Error calculating actual cost from stock moves: {str(e)}")
                    line.actual_cost = line.estimated_cost
            else:
                # Fallback to estimated cost if no validated moves exist
                line.actual_cost = line.estimated_cost
                
    @api.depends('product_id', 'quantity', 'report_id.company_id')
    def _compute_available_stock(self):
        """Compute available stock for the product with accurate on-hand quantities"""
        for line in self:
            # For services or non-tracked products, set appropriate values
            if not line.product_id:
                line.available_stock = 0.0
                line.product_availability = 'not_tracked'
                continue
                
            # Services are always considered available and not tracked in inventory
            if line.product_id.type == 'service':
                line.available_stock = line.quantity  # Consider services as always available
                line.product_availability = 'available'
                continue
                
            # For stockable and consumable products, check actual inventory
            if line.product_id.type in ['product', 'consu']:
                company_id = line.report_id.company_id.id
                
                try:
                    # DIRECT QUERY APPROACH - Get real-time quantity from product
                    # This is the most reliable method and accesses the same data
                    # that Odoo shows in the product form view
                    product = line.product_id.with_company(company_id)
                    
                    # Get warehouse stock location quantity - exactly like sales orders do
                    warehouse = self.env['stock.warehouse'].search([('company_id', '=', company_id)], limit=1)
                    available_qty = 0.0
                    
                    if warehouse and warehouse.lot_stock_id:
                        # Get quantity specifically from the warehouse stock location
                        product = product.with_context(location=warehouse.lot_stock_id.id)
                        available_qty = product.qty_available
                        _logger.info(f"Warehouse stock quantity for {product.name}: {available_qty} at location {warehouse.lot_stock_id.name}")
                    else:
                        # Get overall company quantity as fallback
                        available_qty = product.qty_available
                        _logger.info(f"Company-wide quantity for {product.name}: {available_qty}")
                    
                    # For consumables, we'll always show the quantity available company-wide
                    if line.product_id.type == 'consu':
                        product = line.product_id.with_company(company_id)
                        available_qty = product.qty_available
                        
                    # Log information for debugging
                    _logger.info(f"Product {product.name} (ID: {product.id}) has {available_qty} units available for company {company_id}")
                    
                    # Store the result
                    line.available_stock = available_qty
                    
                except Exception as e:
                    _logger.error(f"Error calculating available stock: {str(e)}")
                    # Fallback to standard qty_available in case of error
                    line.available_stock = line.product_id.with_company(company_id).qty_available
                
                # Set availability status based on available quantity
                # Simplified logic - check if we have enough stock regardless of product type
                if line.available_stock <= 0:
                    line.product_availability = 'no_stock'
                elif line.available_stock < line.quantity:
                    line.product_availability = 'low_stock'
                else:
                    line.product_availability = 'available'
            else:
                # For any other product types
                line.available_stock = 0.0
                line.product_availability = 'not_tracked'
                
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Set default quantity and recompute costs"""
        if self.product_id:
            self._compute_available_stock()
            
    @api.onchange('quantity')
    def _onchange_quantity(self):
        """Recompute costs when quantity changes"""
        if self.quantity:
            self._compute_estimated_cost()
            self._compute_actual_cost()
            self._compute_available_stock()
