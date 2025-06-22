from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class Farm(models.Model):
    _name = 'farm.farm'
    _description = 'Farm'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char('Farm Name', required=True, tracking=True, translate=True)
    code = fields.Char('Farm Code', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    
    location = fields.Char('Location', translate=True, tracking=True)
    area = fields.Float('Total Area (Feddan)', tracking=True)
    area_unit = fields.Selection([
        ('feddan', 'Feddan'),
        ('acre', 'Acre'),
        ('sqm', 'Square Meter'),
    ], string='Area Unit', default='feddan', required=True, tracking=True)
    
    owner_id = fields.Many2one('res.partner', string='Owner', tracking=True)
    manager_id = fields.Many2one('res.users', string='Farm Manager', tracking=True)
    
    company_id = fields.Many2one('res.company', string='Company', 
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    # Stock location for inventory operations
    location_id = fields.Many2one('stock.location', string=_('Stock Location'),
                               help=_("Location where farm supplies and products are stored"))
    # TODO:-> Delete these field if not needed
    acquisition_date = fields.Date('Acquisition Date', tracking=True)
    property_value = fields.Monetary('Property Value', currency_field='currency_id', tracking=True)
    
    field_ids = fields.One2many('farm.field', 'farm_id', string='Fields')
    field_count = fields.Integer(compute='_compute_field_count', string='Field Count')
    
    cultivation_project_ids = fields.One2many('farm.cultivation.project', 'farm_id', 
                                             string='Cultivation Projects')
    project_count = fields.Integer(compute='_compute_project_count', 
                                  string='Cultivation Project Count')
    
    notes = fields.Html('Notes', translate=True)
    
    # Image field for farm photos/maps
    image = fields.Binary("Farm Image", attachment=True)
    
    # Weather information could connect to an API
    climate_zone = fields.Char("Climate Zone", tracking=True)
    avg_rainfall = fields.Float("Average Annual Rainfall (mm)", tracking=True)
    avg_temperature = fields.Float("Average Temperature (°C)", tracking=True)
    
    # Geolocation
    latitude = fields.Float("Latitude", digits=(16, 10), tracking=True)
    longitude = fields.Float("Longitude", digits=(16, 10), tracking=True)
    
    # Analytic account for cost tracking
    analytic_account_id = fields.Many2one('account.analytic.account', 
                                          string='Analytic Account',
                                          tracking=True)
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Farm code must be unique!'),
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create an analytic account for each farm if none is provided and a stock location"""
        for vals in vals_list:
            if not vals.get('analytic_account_id'):
                analytic_account = self.env['account.analytic.account'].create({
                    'name': vals.get('name', 'New Farm'),
                    'code': vals.get('code', ''),
                    'company_id': vals.get('company_id', self.env.company.id),
                })
                vals['analytic_account_id'] = analytic_account.id
                
        records = super().create(vals_list)
        
        # Create stock locations for farms that don't have one
        for record in records:
            if not record.location_id:
                parent_location = self.env.ref('stock.stock_location_locations', raise_if_not_found=False)
                if not parent_location:
                    parent_location = self.env['stock.location'].search([('usage', '=', 'view')], limit=1)
                
                if parent_location:
                    location = self.env['stock.location'].create({
                        'name': record.name,
                        'usage': 'internal',
                        'location_id': parent_location.id,
                        'company_id': record.company_id.id,
                    })
                    record.location_id = location.id
        
        return records
    
    def _compute_field_count(self):
        """Compute the number of fields in the farm"""
        for farm in self:
            farm.field_count = len(farm.field_ids)
    
    def _compute_project_count(self):
        """Compute the number of cultivation projects in the farm"""
        for farm in self:
            farm.project_count = len(farm.cultivation_project_ids)
    
    def action_view_fields(self):
        """Smart button action to view fields"""
        self.ensure_one()
        return {
            'name': _('Fields'),
            'view_mode': 'tree,form',
            'res_model': 'farm.field',
            'domain': [('farm_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_farm_id': self.id}
        }
    
    def action_view_projects(self):
        """Smart button action to view cultivation projects"""
        self.ensure_one()
        return {
            'name': _('Cultivation Projects'),
            'view_mode': 'tree,form',
            'res_model': 'farm.cultivation.project',
            'domain': [('farm_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_farm_id': self.id}
        }
    
    @api.constrains('area')
    def _check_area(self):
        """Ensure area is positive"""
        for record in self:
            if record.area <= 0:
                raise ValidationError(_("Farm area must be greater than zero."))
