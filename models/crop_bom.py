from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

# Note: We've completely disabled mail.thread/activity.mixin inheritance, tracking, and translations
# to avoid PostgreSQL jsonb_path_query_first compatibility issues.
# This resolves the error: "function jsonb_path_query_first(character varying, unknown) does not exist"


class CropBOM(models.Model):
    _name = 'farm.crop.bom'
    _description = 'Crop Bill of Materials'
    # Completely remove mail.thread inheritance to avoid JSON issues
    # _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char('BOM Name', required=True, translate=False)
    code = fields.Char('BOM Code', required=True)
    active = fields.Boolean(default=True)
    
    crop_id = fields.Many2one('farm.crop', string='Crop', required=True, 
                            ondelete='cascade')
    is_default = fields.Boolean('Default BOM', help="Set as default BOM for this crop")
    
    area = fields.Float('Reference Area', default=1.0, required=True,
                     help="Reference area for input calculations (e.g., 1 feddan)")
    area_unit = fields.Selection([
        ('feddan', 'Feddan'),
        ('acre', 'Acre'),
        ('sqm', 'Square Meter'),
    ], string='Area Unit', default='feddan', required=True)
    
    notes = fields.Html('Notes', translate=False)
    
    # Input lines
    line_ids = fields.One2many('farm.crop.bom.line', 'bom_id', string='Input Lines', copy=True)
    
    # Costing
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                default=lambda self: self.env.company.currency_id)
    total_cost = fields.Monetary('Total Cost', compute='_compute_total_cost', 
                              store=True, currency_field='currency_id')
    company_id = fields.Many2one('res.company', string='Company', 
                                default=lambda self: self.env.company)
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'BOM code must be unique!')
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        """If new BOM is set as default, unset any existing default for the crop"""
        # Create records with no tracking/mail features
        records = super(CropBOM, self.with_context(
            tracking_disable=True,
            lang=False,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
            mail_notrack=True,
            no_reset_password=True
        )).create(vals_list)
        
        for record in records:
            if record.is_default:
                self._unset_other_defaults(record)
        return records
    
    def write(self, vals):
        """If BOM is set as default, unset any existing default for the crop"""
        # Write with no tracking
        res = super(CropBOM, self.with_context(
            tracking_disable=True,
            lang=False,
            mail_notrack=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
            no_reset_password=True
        )).write(vals)
        
        if vals.get('is_default') or vals.get('crop_id'):
            for record in self:
                if record.is_default:
                    self._unset_other_defaults(record)
        return res
    
    def _unset_other_defaults(self, record):
        """Unset default flag on other BOMs for the same crop"""
        other_defaults = self.search([
            ('crop_id', '=', record.crop_id.id),
            ('id', '!=', record.id),
            ('is_default', '=', True)
        ])
        if other_defaults:
            # Update with all features disabled
            other_defaults.with_context(
                tracking_disable=True, 
                lang=False, 
                mail_notrack=True,
                mail_create_nolog=True,
                mail_create_nosubscribe=True,
                no_reset_password=True
            ).write({'is_default': False})
    
    @api.depends('line_ids.subtotal')
    def _compute_total_cost(self):
        """Compute total cost from BOM lines"""
        for bom in self:
            bom.total_cost = sum(bom.line_ids.mapped('subtotal'))
    
    def action_apply_to_project(self):
        """Apply this BOM to a cultivation project"""
        self.ensure_one()
        
        # Create context with all JSON/tracking features disabled
        ctx = {
            'tracking_disable': True,
            'lang': False,
            'mail_notrack': True,
            'mail_create_nolog': True,
            'mail_create_nosubscribe': True,
            'no_reset_password': True,
            'default_bom_id': self.id
        }
                  
        return {
            'name': 'Apply BOM to Project',
            'view_mode': 'form',
            'res_model': 'farm.bom.apply.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': ctx
        }
    
    # Methods removed to simplify and avoid JSON issues


class CropBOMLine(models.Model):
    _name = 'farm.crop.bom.line'
    _description = 'Crop BOM Line'
    _order = 'sequence, id'

    sequence = fields.Integer('Sequence', default=10)
    bom_id = fields.Many2one('farm.crop.bom', string='BOM', required=True, 
                          ondelete='cascade')
    
    input_type = fields.Selection([
        ('seed', 'Seed/Seedling'),
        ('fertilizer', 'Fertilizer'),
        ('pesticide', 'Pesticide'),
        ('herbicide', 'Herbicide'),
        ('water', 'Water'),
        ('labor', 'Labor'),
        ('machinery', 'Machinery'),
        ('other', 'Other'),
    ], string='Input Type', required=True)
    
    product_id = fields.Many2one('product.product', string='Product', 
                               required=True, domain=[('type', 'in', ['product', 'consu'])])
    name = fields.Char(related='product_id.name', string='Name', readonly=True, 
                      store=True)
    
    quantity = fields.Float('Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', 
                           related='product_id.uom_id', readonly=True)
    
    # When to apply this input (days from planting)
    apply_days = fields.Integer('Apply Days from Planting', default=0,
                              help="Number of days from planting when this input should be applied")
    
    # Cost calculation
    unit_cost = fields.Float('Unit Cost', related='product_id.standard_price', 
                           readonly=True)
    currency_id = fields.Many2one('res.currency', related='bom_id.currency_id')
    subtotal = fields.Monetary('Subtotal', compute='_compute_subtotal', 
                             store=True, currency_field='currency_id')
    
    notes = fields.Text('Application Notes', translate=False)  # Explicitly disable translation
    
    @api.depends('quantity', 'unit_cost')
    def _compute_subtotal(self):
        """Compute subtotal cost for this line"""
        for line in self:
            line.subtotal = line.quantity * line.unit_cost
            
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to disable JSON functionality that causes PostgreSQL errors"""
        # Need to use with_context instead of setting env.context directly
        return super(CropBOMLine, self.with_context(
            tracking_disable=True, 
            lang=False,
            mail_notrack=True,
            mail_create_nolog=True, 
            mail_create_nosubscribe=True,
            no_reset_password=True
        )).create(vals_list)
        
    def write(self, vals):
        """Override write to disable JSON functionality that causes PostgreSQL errors"""
        return super(CropBOMLine, self.with_context(
            tracking_disable=True, 
            lang=False,
            mail_notrack=True,
            mail_create_nolog=True, 
            mail_create_nosubscribe=True,
            no_reset_password=True
        )).write(vals)
        
    def unlink(self):
        """Override unlink to disable JSON functionality that causes PostgreSQL errors"""
        return super(CropBOMLine, self.with_context(
            tracking_disable=True,
            lang=False, 
            mail_notrack=True,
            mail_create_nolog=True, 
            mail_create_nosubscribe=True,
            no_reset_password=True
        )).unlink()
