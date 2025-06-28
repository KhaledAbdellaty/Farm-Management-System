from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class Field(models.Model):
    _name = 'farm.field'
    _description = _('Farm Field')
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string=_('Field Name'), required=True, tracking=True, translate=True)
    code = fields.Char(string=_('Field Code'), required=True, tracking=True, readonly=True, default=lambda self: _('New'))
    active = fields.Boolean(default=True, tracking=True)
    
    farm_id = fields.Many2one('farm.farm', string='Farm', required=True, 
                             tracking=True, ondelete='cascade')
    
    area = fields.Float('Area', tracking=True, required=True)
    area_unit = fields.Selection([
        ('feddan', 'Feddan'),
        ('acre', 'Acre'),
        ('sqm', 'Square Meter'),
    ], string='Area Unit', default='feddan', required=True, tracking=True)
    
    
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
    
    company_id = fields.Many2one('res.company', related='farm_id.company_id', 
                                string='Company', store=True, readonly=True)
    
    _sql_constraints = [
        ('farm_code_unique', 'UNIQUE(farm_id, code)', 'Field code must be unique per farm!'),
    ]
    
    
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
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create field and ensure it has a customer location in the hierarchy"""
        fields = super().create(vals_list)
        
        for field in fields:
            # Ensure there's a customer location for this field in the hierarchy
            # First, find the farm's customer location
            customer_location = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
            if not customer_location:
                customer_location = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
                
            if customer_location:
                # Find farm customer location
                farm_dest_location = self.env['stock.location'].search([
                    ('name', '=', field.farm_id.name),
                    ('location_id', '=', customer_location.id),
                    ('company_id', '=', field.company_id.id)
                ], limit=1)
                
                if farm_dest_location:
                    # Check if field destination location exists
                    field_dest_location = self.env['stock.location'].search([
                        ('name', '=', field.name),
                        ('location_id', '=', farm_dest_location.id),
                        ('company_id', '=', field.company_id.id)
                    ], limit=1)
                    
                    if not field_dest_location:
                        self.env['stock.location'].create({
                            'name': field.name,
                            'usage': 'customer',
                            'location_id': farm_dest_location.id,
                            'company_id': field.company_id.id,
                        })
        
        return fields
    
    def write(self, vals):
        """Override write to update location name if field name changes"""
        result = super().write(vals)
        
        # If name is changed, update associated customer location name
        if 'name' in vals:
            for field in self:
                # Find the farm's customer location
                customer_location = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
                if not customer_location:
                    customer_location = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
                    
                if customer_location:
                    # Find farm customer location
                    farm_dest_location = self.env['stock.location'].search([
                        ('name', '=', field.farm_id.name),
                        ('location_id', '=', customer_location.id),
                        ('company_id', '=', field.company_id.id)
                    ], limit=1)
                    
                    if farm_dest_location:
                        # Update field location name if it exists
                        field_locations = self.env['stock.location'].search([
                            ('location_id', '=', farm_dest_location.id),
                            ('company_id', '=', field.company_id.id)
                        ])
                        
                        for location in field_locations:
                            if location.name != field.name and location.name == vals.get('name', ''):
                                location.write({'name': field.name})
        
        return result
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate a unique code for new fields using the sequence"""
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('farm.field') or _('New')
        return super(Field, self).create(vals_list)
