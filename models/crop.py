from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class Crop(models.Model):
    _name = 'farm.crop'
    _description = 'Crop'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Crop Name', required=True, tracking=True, translate=True)
    code = fields.Char(string='Crop Code', required=True, tracking=True, readonly=True, default=lambda self: 'New')
    active = fields.Boolean(default=True, tracking=True)
    growing_cycle = fields.Integer(string='Growing Cycle (Days)', tracking=True, 
                                  help="Average number of days for the crop's growing cycle")
    
    # Units of Measure for the crop
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', 
                            required=True, tracking=True,
                            default=lambda self: self.env.ref('uom.product_uom_unit').id,
                            help="Default unit of measure for the crop product")
    

    # Product association
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=False,  # Not required on input as we'll auto-create it
        tracking=True,
        readonly=False,  # Not readonly in the model, only in the view
        help="The product associated with this crop for inventory and sales - auto-created on save"
    )
    
    # Cultivation history
    project_ids = fields.One2many('farm.cultivation.project', 'crop_id', 
                                string='Cultivation Projects')
    project_count = fields.Integer(compute='_compute_project_count', 
                                 string='Project Count')
    
    # BOM for inputs needed for this crop
    bom_ids = fields.One2many('farm.crop.bom', 'crop_id', string='Input BOMs', copy=True)
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
            'view_mode': 'list,form',
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
            'view_mode': 'list,form',
            'res_model': 'farm.crop.bom',
            'domain': [('crop_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_crop_id': self.id}
        }
    
    def action_create_product(self):
        """Create a product based on this crop"""
        self.ensure_one()
        
        if self.product_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Product'),
                'res_model': 'product.product',
                'view_mode': 'form',
                'res_id': self.product_id.id,
            }
        
        # Create a product category for agricultural products if it doesn't exist
        crop_category = self.env['product.category'].search([
            ('name', '=', 'Agricultural Products')
        ], limit=1)
        
        if not crop_category:
            crop_category = self.env['product.category'].create({
                'name': 'Agricultural Products',
                'property_cost_method': 'average',
                'property_valuation': 'manual_periodic',  # Use manual_periodic to avoid account errors
            })
        elif crop_category.property_valuation == 'real_time':
            # If the category exists but has real_time valuation, update it to manual_periodic
            crop_category.write({'property_valuation': 'manual_periodic'})
        
        # Create the product with proper defaults
        product = self.env['product.product'].create({
            'name': self.name,
            'type': 'consu',  # Goods (stockable product)
            'categ_id': crop_category.id,
            'sale_ok': True,
            'purchase_ok': False,  # By default, we don't purchase harvested crops
            'is_storable': True,  # Ensure it's a stockable product
            'default_code': f"{self.code}",
            'company_id': self.company_id.id,
            'uom_id': self.uom_id.id,  # Use the crop's UoM
            'uom_po_id': self.uom_id.id,  # Same UoM for purchase
        })
        
        # Link the product to the crop
        self.product_id = product.id
        
        # Show the new product
        return {
            'type': 'ir.actions.act_window',
            'name': _('Product Created'),
            'res_model': 'product.product',
            'view_mode': 'form',
            'res_id': product.id,
            'target': 'current',
        }
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Update product type and settings when selected"""
        if self.product_id:
            # Make sure the product is properly configured for inventory
            if self.product_id.type != 'consu':
                self.product_id.type = 'consu'
                return {
                    'warning': {
                        'title': _('Product Type Updated'),
                        'message': _('The product type has been updated to "Goods" to ensure proper inventory management.')
                    }
                }
    
    def action_configure_routes(self):
        """Configure the sales routes for the product"""
        self.ensure_one()
        
        if not self.product_id:
            raise ValidationError(_("No product associated with this crop. Please select a product first."))
        
        # Get the warehouse
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        if not warehouse:
            raise ValidationError(_("No warehouse found for this company."))
        
        # Configure product
        self.product_id.write({
            'type': 'consu',  # Goods (stockable product)
            'sale_ok': True,
            'route_ids': [(4, warehouse.route_ids.filtered(lambda r: r.name == 'Deliver from Stock').id)] if warehouse.route_ids else []
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Routes Configured'),
                'message': _('Product routes have been configured successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def get_translated_field_labels(self):
        """Return field labels properly translated at runtime"""
        return {
            'crop_name': _('Crop Name'),
            'crop_code': _('Crop Code'),
            'growing_cycle': _('Growing Cycle (Days)'),
            'unit_of_measure': _('Unit of Measure'),
            'product': _('Product')
        }
        
    def get_translated_help_texts(self):
        """Return help texts properly translated at runtime"""
        return {
            'growing_cycle': _("Average number of days for the crop's growing cycle"),
            'uom_id': _("Default unit of measure for the crop product"),
            'product_id': _("The product associated with this crop for inventory and sales - auto-created on save")
        }
        
    @api.model_create_multi
    def create(self, vals_list):
        """Create crop record and auto-create associated product"""
        for vals in vals_list:
            # Assign sequence for code if it's 'New'
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('farm.crop') or 'New'
                
            # If no product_id is provided, create one automatically
            if not vals.get('product_id'):
                # Get product category for crops
                crop_category = self.env['product.category'].search([
                    ('name', '=', 'Agricultural Products')
                ], limit=1)
                
                if not crop_category:
                    crop_category = self.env['product.category'].create({
                        'name': 'Agricultural Products',
                        'property_cost_method': 'average',
                        'property_valuation': 'manual_periodic',  # Use manual_periodic to avoid account errors
                    })
                elif crop_category.property_valuation == 'real_time':
                    # If the category exists but has real_time valuation, update it to manual_periodic
                    crop_category.write({'property_valuation': 'manual_periodic'})
                
                # Create stockable product with crop name
                crop_name = vals.get('name', 'New Crop')
                crop_code = vals.get('code', 'NEW')
                
                # Get UoM from vals or default to Units
                uom_id = vals.get('uom_id', False) or self.env.ref('uom.product_uom_unit').id
                
                product_vals = {
                    'name': crop_name,
                    'type': 'consu',  # Goods (stockable product)
                    'categ_id': crop_category.id,
                    'sale_ok': True,
                    'purchase_ok': False,
                    'is_storable': True,
                    'default_code': f"CROP-{crop_code}",
                    'company_id': vals.get('company_id', self.env.company.id),
                    'uom_id': uom_id,  # Set the selected UoM
                    'uom_po_id': uom_id,  # Set the same UoM for purchase
                }
                
                product = self.env['product.product'].create(product_vals)
                vals['product_id'] = product.id
                
                # Configure product routes
                warehouse = self.env['stock.warehouse'].search([
                    ('company_id', '=', vals.get('company_id', self.env.company.id))
                ], limit=1)
                
                if warehouse and warehouse.route_ids:
                    deliver_route = warehouse.route_ids.filtered(lambda r: r.name == 'Deliver from Stock')
                    if deliver_route:
                        product.write({'route_ids': [(4, deliver_route.id)]})
        
        # Call super to create the records
        return super().create(vals_list)
    
    def copy(self, default=None):
        """When duplicating a crop, create a new product for it"""
        default = default or {}
        default['product_id'] = False  # Force creation of a new product
        return super().copy(default)
    
    def write(self, vals):
        """Update associated product when crop name changes"""
        result = super().write(vals)
        
        # If name is updated, update product name too
        if 'name' in vals:
            for crop in self:
                if crop.product_id:
                    crop.product_id.write({'name': crop.name})
        
        # If UoM is updated, update product UoM too
        if 'uom_id' in vals:
            for crop in self:
                if crop.product_id:
                    crop.product_id.write({
                        'uom_id': crop.uom_id.id,
                        'uom_po_id': crop.uom_id.id
                    })
        
        return result

