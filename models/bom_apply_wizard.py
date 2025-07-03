from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BomApplyWizard(models.TransientModel):
    _name = 'farm.bom.apply.wizard'
    _description = 'Apply Crop BOM to Project'
    
    bom_id = fields.Many2one('farm.crop.bom', string='BOM', required=True)
    project_id = fields.Many2one('farm.cultivation.project', string='Project', required=True)
    crop_id = fields.Many2one('farm.crop', related='bom_id.crop_id', readonly=True)
    scale_by_area = fields.Boolean(string='Scale by Field Area', default=True,
                                  help="If checked, quantities will be scaled based on field area")
    
    @api.constrains('bom_id', 'project_id')
    def _check_crop_match(self):
        for record in self:
            if record.bom_id.crop_id != record.project_id.crop_id:
                raise ValidationError(_("The BOM crop must match the project crop."))
    
    def action_apply(self):
        """Apply the BOM to generate cost analysis records for the project"""
        self.ensure_one()
        
        # Get scale factor if needed
        scale_factor = 1.0
        if self.scale_by_area:
            # Convert areas to the same unit if needed
            bom_area = self.bom_id.area
            field_area = self.project_id.field_area
            
            # Simple conversion factor between common units
            # For a proper implementation, a more comprehensive unit conversion would be needed
            # This is simplified for demo purposes
            if self.bom_id.area_unit != self.project_id.field_area_unit:
                # Conversions for feddan (1 feddan ≈ 4,200 sqm ≈ 1.038 acres)
                if self.bom_id.area_unit == 'feddan' and self.project_id.field_area_unit == 'acre':
                    bom_area = bom_area * 1.038
                elif self.bom_id.area_unit == 'feddan' and self.project_id.field_area_unit == 'sqm':
                    bom_area = bom_area * 4200
                elif self.bom_id.area_unit == 'acre' and self.project_id.field_area_unit == 'feddan':
                    bom_area = bom_area * 0.963
                elif self.bom_id.area_unit == 'acre' and self.project_id.field_area_unit == 'sqm':
                    bom_area = bom_area * 4046.86
                elif self.bom_id.area_unit == 'sqm' and self.project_id.field_area_unit == 'feddan':
                    bom_area = bom_area * 0.000238
                elif self.bom_id.area_unit == 'sqm' and self.project_id.field_area_unit == 'acre':
                    bom_area = bom_area * 0.000247
            
            # Calculate scale factor based on area ratio
            if bom_area > 0:
                scale_factor = field_area / bom_area
        
        # Map BOM input_type to cost_analysis cost_type fields
        cost_type_mapping = {
            'seed': 'seeds',
            'fertilizer': 'fertilizer',
            'pesticide': 'pesticide',
            'herbicide': 'herbicide',
            'water': 'water',
            'labor': 'labor',
            'machinery': 'machinery',
            'other': 'other',
        }
        
        # Now create cost records for each BOM line
        for line in self.bom_id.line_ids:
            # Scale quantity according to field area if needed
            quantity = line.quantity * scale_factor if self.scale_by_area else line.quantity
            
            # Get the corresponding cost_type from the mapping
            cost_type = cost_type_mapping.get(line.input_type, 'other')
            
            # Create cost analysis record with disabled tracking/translation
            ctx = dict(self.env.context, 
                      tracking_disable=True, 
                      lang=False,
                      mail_create_nolog=True,
                      mail_create_nosubscribe=True,
                      mail_notrack=True)
                      
            self.env['farm.cost.analysis'].with_context(ctx).create({
                'project_id': self.project_id.id,
                'date': self.project_id.start_date,
                'cost_type': cost_type,
                'cost_name': line.product_id.name,
                'quantity': quantity,
                'uom_id': line.uom_id.id,
                'cost_amount': line.unit_cost * quantity,
                'is_budgeted': True,  # These are budgeted costs from the BOM
                'source_type': 'bom',
                'source_id': line.bom_id.id,
            })
        
        # Update project with the BOM ID - disable tracking to avoid JSON issues
        ctx = dict(tracking_disable=True, lang=False, mail_notrack=True)
        self.project_id.with_context(ctx).write({'crop_bom_id': self.bom_id.id})
        
        # Create success message
        message = _('BOM "%s" has been applied to project "%s"') % (self.bom_id.name, self.project_id.name)
        
        # Return an action to close the wizard and display a notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('BOM Applied'),
                'message': message,
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
