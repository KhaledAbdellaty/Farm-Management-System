from odoo import fields, models, api, _

class CropBOMLineWizard(models.TransientModel):
    _name = 'farm.crop.bom.line.wizard'
    _description = _('Add BOM Line Wizard')
    
    bom_id = fields.Many2one('farm.crop.bom', string=_('BOM'), required=True)
    
    input_type = fields.Selection([
        ('seed', _('Seed/Seedling')),
        ('fertilizer', _('Fertilizer')),
        ('pesticide', _('Pesticide')),
        ('herbicide', _('Herbicide')),
        ('water', _('Water')),
        ('labor', _('Labor')),
        ('machinery', _('Machinery')),
        ('other', _('Other')),
    ], string=_('Input Type'), required=True)
    
    product_id = fields.Many2one('product.product', string=_('Product'), 
                               required=True, domain=[('type', 'in', ['product', 'consu'])])
    quantity = fields.Float(_('Quantity'), required=True, default=1.0)
    apply_days = fields.Integer(_('Apply Days from Planting'), default=0)
    notes = fields.Text(_('Application Notes'))
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.quantity = 1.0
    
    def action_add(self):
        """Safely add the line to the BOM"""
        self.ensure_one()
        
        # Create the line
        vals = {
            'bom_id': self.bom_id.id,
            'input_type': self.input_type,
            'product_id': self.product_id.id,
            'quantity': self.quantity,
            'apply_days': self.apply_days,
            'notes': self.notes,
        }
        
        # Create the line with a complete tracking disable context
        ctx = {
            'tracking_disable': True,
            'lang': False,
            'mail_notrack': True, 
            'mail_create_nolog': True,
            'mail_create_nosubscribe': True,
            'no_reset_password': True,
            'check_move_validity': False
        }
        
        # Ensure we use the safest possible way to create the line
        self.env['farm.crop.bom.line'].with_context(**ctx).create(vals)
        
        return {'type': 'ir.actions.act_window_close'}
