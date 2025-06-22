from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class Field(models.Model):
    _name = 'farm.field'
    _description = 'Farm Field'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char('Field Name', required=True, tracking=True, translate=True)
    code = fields.Char('Field Code', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    
    farm_id = fields.Many2one('farm.farm', string='Farm', required=True, 
                             tracking=True, ondelete='cascade')
    
    area = fields.Float('Area', tracking=True, required=True)
    area_unit = fields.Selection([
        ('feddan', 'Feddan'),
        ('acre', 'Acre'),
        ('sqm', 'Square Meter'),
    ], string='Area Unit', default='feddan', required=True, tracking=True)
    
    field_type = fields.Selection([
        ('open_field', 'Open Field'),
        ('greenhouse', 'Greenhouse'),
        ('hydroponics', 'Hydroponics'),
        ('orchard', 'Orchard'),
    ], string='Field Type', required=True, tracking=True)
    
    soil_type = fields.Selection([
        ('clay', 'Clay'),
        ('silt', 'Silt'),
        ('sand', 'Sand'),
        ('loam', 'Loam'),
        ('mixed', 'Mixed'),
    ], string='Soil Type', tracking=True)
    
    irrigation_method = fields.Selection([
        ('drip', 'Drip Irrigation'),
        ('sprinkler', 'Sprinkler'),
        ('flood', 'Flood Irrigation'),
        ('manual', 'Manual Irrigation'),
        ('none', 'No Irrigation'),
    ], string='Irrigation Method', tracking=True)
    
    current_crop_id = fields.Many2one('farm.crop', string='Current Crop', 
                                     tracking=True)
    
    project_ids = fields.One2many('farm.cultivation.project', 'field_id', 
                                string='Cultivation Projects')
    project_count = fields.Integer(compute='_compute_project_count', 
                                 string='Project Count')
    
    notes = fields.Html('Notes', translate=True)
    
    # Field status
    state = fields.Selection([
        ('available', 'Available'),
        ('preparation', 'In Preparation'),
        ('cultivated', 'Cultivated'),
        ('harvested', 'Harvested'),
        ('fallow', 'Fallow'),
    ], string='Status', default='available', tracking=True)
    
    # Field image or map
    image = fields.Binary("Field Image", attachment=True)
    
    # Geolocation
    latitude = fields.Float("Latitude", digits=(16, 10), tracking=True)
    longitude = fields.Float("Longitude", digits=(16, 10), tracking=True)
    
    # Soil properties for more detailed analysis
    soil_ph = fields.Float('Soil pH', tracking=True)
    organic_matter = fields.Float('Organic Matter %', tracking=True)
    
    company_id = fields.Many2one('res.company', related='farm_id.company_id', 
                                string='Company', store=True, readonly=True)
    
    # Analytic account for field-level cost tracking
    analytic_account_id = fields.Many2one('account.analytic.account', 
                                         string='Analytic Account', 
                                         tracking=True)
    
    _sql_constraints = [
        ('farm_code_unique', 'UNIQUE(farm_id, code)', 'Field code must be unique per farm!'),
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create analytic account for each field if none is provided"""
        for vals in vals_list:
            if not vals.get('analytic_account_id'):
                # Get farm name for the analytic account
                farm_name = 'Unknown'
                if vals.get('farm_id'):
                    farm = self.env['farm.farm'].browse(vals['farm_id'])
                    farm_name = farm.name
                
                analytic_account = self.env['account.analytic.account'].create({
                    'name': f"{farm_name} - {vals.get('name', 'New Field')}",
                    'code': vals.get('code', ''),
                    'company_id': self.env['farm.farm'].browse(vals.get('farm_id')).company_id.id,
                })
                vals['analytic_account_id'] = analytic_account.id
        return super().create(vals_list)
    
    def _compute_project_count(self):
        """Compute the number of cultivation projects on this field"""
        for field in self:
            field.project_count = len(field.project_ids)
    
    def action_view_projects(self):
        """Smart button action to view cultivation projects for this field"""
        self.ensure_one()
        return {
            'name': _('Cultivation Projects'),
            'view_mode': 'tree,form',
            'res_model': 'farm.cultivation.project',
            'domain': [('field_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_field_id': self.id, 'default_farm_id': self.farm_id.id}
        }
    
    @api.constrains('area')
    def _check_area(self):
        """Ensure area is positive"""
        for record in self:
            if record.area <= 0:
                raise ValidationError(_("Field area must be greater than zero."))
