from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class Crop(models.Model):
    _name = 'farm.crop'
    _description = 'Crop'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char('Crop Name', required=True, tracking=True, translate=True)
    code = fields.Char('Crop Code', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    growing_cycle = fields.Integer('Growing Cycle (Days)', tracking=True, 
                                  help="Average number of days for the crop's growing cycle")
    
    # Fields crop_type and planting_season removed as they are no longer needed
    

    # Product association
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        tracking=False,
        # domain="[('type', '=', 'product'), ('sale_ok', '=', True)]"
    )
    
    # Cultivation history
    project_ids = fields.One2many('farm.cultivation.project', 'crop_id', 
                                string='Cultivation Projects')
    project_count = fields.Integer(compute='_compute_project_count', 
                                 string='Project Count')
    
    # BOM for inputs needed for this crop
    bom_ids = fields.One2many('farm.crop.bom', 'crop_id', string='Input BOMs')
    bom_count = fields.Integer(compute='_compute_bom_count', string='BOM Count')
    
    notes = fields.Html('Notes', translate=False)
    
    # Crop image
    image = fields.Binary("Crop Image", attachment=True)
    
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company)
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Crop code must be unique!'),
    ]
    
    def _compute_project_count(self):
        """Compute the number of cultivation projects for this crop"""
        for crop in self:
            crop.project_count = len(crop.project_ids)
    
    def _compute_bom_count(self):
        """Compute the number of BOMs for this crop"""
        for crop in self:
            crop.bom_count = len(crop.bom_ids)
    
    def action_view_projects(self):
        """Smart button action to view cultivation projects for this crop"""
        self.ensure_one()
        return {
            'name': _('Cultivation Projects'),
            'view_mode': 'tree,form',
            'res_model': 'farm.cultivation.project',
            'domain': [('crop_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_crop_id': self.id}
        }
    
    def action_view_boms(self):
        """Smart button action to view BOMs for this crop"""
        self.ensure_one()
        return {
            'name': _('Crop BOMs'),
            'view_mode': 'tree,form',
            'res_model': 'farm.crop.bom',
            'domain': [('crop_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_crop_id': self.id}
        }
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create crop record with product configuration"""
        crops = super().create(vals_list)
        for crop in crops:
            if crop.product_id:
                crop._configure_product_routes()
        return crops
        
    def write(self, vals):
        """Update crop record and configure product if changed"""
        result = super().write(vals)
        if 'product_id' in vals:
            for crop in self:
                if crop.product_id:
                    crop._configure_product_routes()
        return result
    
    def _configure_product_routes(self):
        """Configure proper route settings for the associated product"""
        self.ensure_one()
        if not self.product_id:
            return
            1.00
        # Ensure the product is configured as a storable product
        if self.product_id.type != 'product':
            self.product_id.type = 'product'
            
        # Ensure the product is saleable
        if not self.product_id.sale_ok:
            self.product_id.sale_ok = True
            
        # Get the stock routes needed for proper replenishment
        route_mto = self.env.ref('stock.route_warehouse0_mto', raise_if_not_found=False)
        route_manufacture = self.env.ref('mrp.route_warehouse0_manufacture', raise_if_not_found=False)
        buy_route = self.env.ref('purchase_stock.route_warehouse0_buy', raise_if_not_found=False)
        
        # Get standard warehouse routes (like warehouse stock rule)
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
        warehouse_routes = self.env['stock.route']
        if warehouse:
            # Add standard warehouse route for proper replenishment
            warehouse_route = warehouse.route_ids.filtered(lambda r: r.name.startswith(warehouse.name))
            if warehouse_route:
                warehouse_routes += warehouse_route
                
        # Build list of routes to apply (use available ones)
        routes_to_apply = self.env['stock.route']
        
        # Apply warehouse routes first (most important for basic functionality)
        routes_to_apply += warehouse_routes
        
        # Add Make To Order route if available
        if route_mto:
            routes_to_apply += route_mto
            
        # Add Buy route if available (for purchasing crops)
        if buy_route and self.env['ir.module.module'].search([('name', '=', 'purchase'), ('state', '=', 'installed')]):
            routes_to_apply += buy_route
            
        # Add Manufacturing route if MRP is installed (for producing crops)
        if route_manufacture and self.env['ir.module.module'].search([('name', '=', 'mrp'), ('state', '=', 'installed')]):
            routes_to_apply += route_manufacture
            
        # Update product routes
        if routes_to_apply:
            self.product_id.route_ids = [(6, 0, routes_to_apply.ids)]
            
        # Enable reordering rules
        if hasattr(self.product_id, 'use_warehouse_reordering_rules'):
            self.product_id.use_warehouse_reordering_rules = True
            
        # Configure additional product settings for proper stock behavior
        if hasattr(self.product_id, 'tracking'):
            self.product_id.tracking = 'none'  # No lot/serial tracking by default
            
        # Set appropriate replenishment policy
        if hasattr(self.product_id, 'procure_method'):
            self.product_id.procure_method = 'make_to_stock'  # Default to make to stock
            
        # For sales order stock behavior
        if hasattr(self.product_id, 'invoice_policy'):
            self.product_id.invoice_policy = 'order'  # Invoice based on ordered quantity
            
        _logger.info(f"Configured routes for product {self.product_id.name}: {self.product_id.route_ids.mapped('name')}")
