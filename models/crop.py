from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class Crop(models.Model):
    _name = 'farm.crop'
    _description = 'Crop'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char('Crop Name', required=True, tracking=True, translate=True)
    code = fields.Char('Crop Code', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    
    crop_type = fields.Selection([
        ('grain', 'Grain'),
        ('vegetable', 'Vegetable'),
        ('fruit', 'Fruit'),
        ('root', 'Root'),
        ('forage', 'Forage'),
        ('oil', 'Oil Crop'),
        ('fiber', 'Fiber Crop'),
        ('spice', 'Spice'),
        ('other', 'Other'),
    ], string='Crop Type', required=True, tracking=False)
    
    # Season information
    planting_season = fields.Selection([
        ('spring', 'Spring'),
        ('summer', 'Summer'),
        ('fall', 'Fall'),
        ('winter', 'Winter'),
        ('year_round', 'Year-round'),
    ], string='Planting Season', tracking=False)
    

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
    
    @api.onchange('crop_type')
    def _onchange_crop_type(self):
        """Set default values based on crop type"""
        if self.crop_type == 'grain':
            self.water_req = 'medium'
        elif self.crop_type in ['vegetable', 'fruit']:
            self.water_req = 'high'
