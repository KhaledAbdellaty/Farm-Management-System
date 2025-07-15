from odoo import api, fields, models, _
from datetime import datetime, timedelta
from collections import defaultdict
import json
import logging

_logger = logging.getLogger(__name__)

class FarmDashboard(models.Model):
    _name = 'farm.dashboard'
    _description = _('Farm Management Dashboard')
    
    def _default_name(self):
        """Set a default name based on current date"""
        today = fields.Date.today()
        return _("Farm Dashboard - %s") % today.strftime('%Y-%m-%d')
    
    name = fields.Char(string=_('Dashboard Name'), required=False, translate=True, default=_default_name)
    user_id = fields.Many2one('res.users', string=_('User'), default=lambda self: self.env.user, required=True)
    
    # Filter fields
    date_from = fields.Date(string=_('Date From'), default=lambda self: fields.Date.today() - timedelta(days=30))
    date_to = fields.Date(string=_('Date To'), default=lambda self: fields.Date.today())
    farm_ids = fields.Many2many('farm.farm', string=_('Farms'))
    crop_ids = fields.Many2many('farm.crop', string=_('Crops'))
    project_ids = fields.Many2many('farm.cultivation.project', string=_('Projects'))
    
    # Display options
    show_cost_analysis = fields.Boolean(string=_('Show Cost Analysis'), default=True)
    show_yield_comparison = fields.Boolean(string=_('Show Yield Comparison'), default=True)
    show_irrigation_stats = fields.Boolean(string=_('Show Irrigation Statistics'), default=True)
    show_resource_usage = fields.Boolean(string=_('Show Resource Usage'), default=True)
    
    # Dashboard data (stored as JSON)
    dashboard_data = fields.Text(string=_('Dashboard Data'), compute='_compute_dashboard_data')
    json_data = fields.Text(string=_('JSON Dashboard Data'), compute='_compute_json_data')
    
    @api.depends('date_from', 'date_to', 'farm_ids', 'crop_ids', 'project_ids',
                'show_cost_analysis', 'show_yield_comparison', 'show_irrigation_stats', 'show_resource_usage')
    def _compute_dashboard_data(self):
        """Compute all dashboard data and store as JSON"""
        for record in self:
            dashboard_data = {}
            
            # Apply filters
            domain = []
            if record.date_from:
                domain.append(('start_date', '>=', record.date_from))
            if record.date_to:
                domain.append(('start_date', '<=', record.date_to))
            if record.farm_ids:
                domain.append(('farm_id', 'in', record.farm_ids.ids))
            if record.crop_ids:
                domain.append(('crop_id', 'in', record.crop_ids.ids))
            if record.project_ids:
                domain.append(('id', 'in', record.project_ids.ids))
            
            # Get projects based on filters
            projects = self.env['farm.cultivation.project'].search(domain)
            
            # Farm Overview
            dashboard_data['farm_overview'] = self._get_farm_overview(projects)
            
            # Cost Analysis
            if record.show_cost_analysis:
                dashboard_data['cost_analysis'] = self._get_cost_analysis(projects)
                
            # Yield Comparison
            if record.show_yield_comparison:
                dashboard_data['yield_comparison'] = self._get_yield_comparison(projects)
            
            # Irrigation Statistics
            if record.show_irrigation_stats:
                dashboard_data['irrigation_stats'] = self._get_irrigation_stats(projects)
                
            # Resource Usage
            if record.show_resource_usage:
                dashboard_data['resource_usage'] = self._get_resource_usage(projects)
            
            record.dashboard_data = json.dumps(dashboard_data)
    
    def _get_farm_overview(self, projects):
        """Get farm overview metrics"""
        total_area = sum(projects.mapped('field_area'))
        total_budget = sum(projects.mapped('budget'))
        total_cost = sum(projects.mapped('actual_cost'))
        total_revenue = sum(projects.mapped('revenue'))
        total_profit = sum(projects.mapped('profit'))
        
        # Count projects by stage
        stage_counts = {}
        for stage, stage_name in self.env['farm.cultivation.project']._fields['state'].selection:
            count = len(projects.filtered(lambda p: p.state == stage))
            stage_counts[stage] = {'name': stage_name, 'count': count}
            
        # Count projects by crop
        crop_counts = {}
        for crop in projects.mapped('crop_id'):
            crop_projects = projects.filtered(lambda p: p.crop_id.id == crop.id)
            crop_counts[crop.name] = len(crop_projects)
        
        return {
            'total_projects': len(projects),
            'total_area': total_area,
            'total_budget': total_budget,
            'total_cost': total_cost,
            'total_revenue': total_revenue,
            'total_profit': total_profit,
            'budget_usage_percentage': (total_cost / total_budget * 100) if total_budget else 0,
            'profit_margin': (total_profit / total_revenue * 100) if total_revenue else 0,
            'stage_counts': stage_counts,
            'crop_counts': crop_counts,
        }
    
    def _get_cost_analysis(self, projects):
        """Analyze costs across projects"""
        # Get all cost analysis records for these projects
        cost_records = self.env['farm.cost.analysis'].search([
            ('project_id', 'in', projects.ids)
        ])
        
        # Group costs by type
        cost_by_type = defaultdict(float)
        for record in cost_records:
            cost_by_type[record.cost_type] += record.cost_amount
            
        # Calculate budget vs actual by project
        budget_vs_actual = []
        for project in projects:
            budget_vs_actual.append({
                'project_name': project.name,
                'budget': project.budget,
                'actual': project.actual_cost,
                'variance': project.budget - project.actual_cost,
                'variance_percentage': ((project.budget - project.actual_cost) / project.budget * 100) if project.budget else 0,
            })
            
        return {
            'cost_by_type': dict(cost_by_type),
            'budget_vs_actual': budget_vs_actual,
            'total_budget': sum(projects.mapped('budget')),
            'total_actual': sum(projects.mapped('actual_cost')),
            'total_variance': sum(projects.mapped('budget')) - sum(projects.mapped('actual_cost')),
        }
    
    def _get_yield_comparison(self, projects):
        """Compare planned vs actual yield"""
        yield_data = []
        for project in projects:
            if project.planned_yield > 0 or project.actual_yield > 0:
                yield_data.append({
                    'project_name': project.name,
                    'crop_name': project.crop_id.name,
                    'planned_yield': project.planned_yield,
                    'actual_yield': project.actual_yield,
                    'yield_variance': project.actual_yield - project.planned_yield,
                    'yield_variance_percentage': ((project.actual_yield - project.planned_yield) / project.planned_yield * 100) if project.planned_yield else 0,
                    'yield_uom': project.yield_uom_id.name if project.yield_uom_id else '',
                    'yield_quality': dict(self.env['farm.cultivation.project']._fields['yield_quality'].selection).get(project.yield_quality, ''),
                })
                
        return {
            'yield_data': yield_data,
            'total_planned_yield': sum(projects.mapped('planned_yield')),
            'total_actual_yield': sum(projects.mapped('actual_yield')),
            'total_yield_variance': sum(projects.mapped('actual_yield')) - sum(projects.mapped('planned_yield')),
        }
    
    def _get_irrigation_stats(self, projects):
        """Get irrigation statistics from daily reports"""
        # Get all daily reports for these projects that are irrigation operations
        irrigation_reports = self.env['farm.daily.report'].search([
            ('project_id', 'in', projects.ids),
            ('operation_type', '=', 'irrigation'),
        ])
        
        # Group irrigation by project
        irrigation_by_project = defaultdict(list)
        for report in irrigation_reports:
            irrigation_by_project[report.project_id.id].append({
                'date': fields.Date.to_string(report.date),
                'duration': report.irrigation_duration,
            })
            
        # Calculate total irrigation time by project
        total_by_project = []
        for project_id, irrigations in irrigation_by_project.items():
            project = self.env['farm.cultivation.project'].browse(project_id)
            total_duration = sum(item['duration'] for item in irrigations)
            total_by_project.append({
                'project_name': project.name,
                'crop_name': project.crop_id.name,
                'total_irrigation_hours': total_duration,
                'irrigation_count': len(irrigations),
                'irrigations': irrigations,
            })
            
        return {
            'total_irrigation_hours': sum(report.irrigation_duration for report in irrigation_reports),
            'total_irrigation_count': len(irrigation_reports),
            'irrigation_by_project': total_by_project,
        }
    
    def _get_resource_usage(self, projects):
        """Analyze resource usage across projects"""
        # Get all daily reports for these projects
        daily_reports = self.env['farm.daily.report'].search([
            ('project_id', 'in', projects.ids),
        ])
        
        # Get product lines from reports
        product_lines = self.env['farm.daily.report.line'].search([
            ('report_id', 'in', daily_reports.ids),
        ])
        
        # Group by product category
        usage_by_category = defaultdict(float)
        for line in product_lines:
            if line.product_id and line.product_id.categ_id:
                category = line.product_id.categ_id.name
                usage_by_category[category] += line.quantity
                
        # Group by product
        usage_by_product = defaultdict(float)
        for line in product_lines:
            if line.product_id:
                usage_by_product[line.product_id.name] += line.quantity
                
        return {
            'usage_by_category': dict(usage_by_category),
            'usage_by_product': dict(usage_by_product),
        }

    def action_open_dashboard(self):
        """Action to open the dashboard view"""
        self.ensure_one()
        return {
            'name': _('Farm Dashboard'),
            'res_model': 'farm.dashboard',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('farm_management.farm_dashboard_view_form').id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }
        
    @api.depends('dashboard_data')
    def _compute_json_data(self):
        """Compute a clean version of the dashboard data as JSON for the widget"""
        for record in self:
            try:
                # If dashboard_data is computed, use it
                if record.dashboard_data:
                    data = json.loads(record.dashboard_data)
                    record.json_data = json.dumps(data)
                else:
                    # Fallback if dashboard_data is not computed yet
                    record.json_data = '{}'
            except Exception as e:
                _logger.error("Error computing json_data: %s", e)
                record.json_data = '{}'
                
    # HTML representation of the dashboard
    dashboard_html = fields.Html(string=_("Dashboard HTML"), compute="_compute_dashboard_html", sanitize=False)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Ensure all new records have names"""
        for vals in vals_list:
            if 'name' not in vals or not vals['name']:
                vals['name'] = self._default_name()
        return super().create(vals_list)
    
    @api.depends('dashboard_data')
    def _compute_dashboard_html(self):
        """Generate HTML representation of dashboard data"""
        for record in self:
            html = ['<div class="farm-dashboard-container p-3">']
            
            try:
                if record.dashboard_data:
                    data = json.loads(record.dashboard_data)
                    
                    # Farm Overview Section
                    if 'farm_overview' in data:
                        overview = data['farm_overview']
                        html.append('<div class="card mb-4 shadow-sm">')
                        html.append('<div class="card-header bg-light"><h5 class="m-0">Farm Overview</h5></div>')
                        html.append('<div class="card-body">')
                        html.append('<div class="row">')
                        
                        # Project Count
                        html.append(f'''
                            <div class="col-md-3 col-sm-6 mb-3">
                                <div class="card h-100 border-0 shadow-sm">
                                    <div class="card-body text-center">
                                        <i class="fa fa-seedling fa-2x mb-2 text-success"></i>
                                        <h5>Active Projects</h5>
                                        <p class="h3">{overview.get('total_projects', 0)}</p>
                                    </div>
                                </div>
                            </div>
                        ''')
                        
                        # Budget
                        html.append(f'''
                            <div class="col-md-3 col-sm-6 mb-3">
                                <div class="card h-100 border-0 shadow-sm">
                                    <div class="card-body text-center">
                                        <i class="fa fa-coins fa-2x mb-2 text-warning"></i>
                                        <h5>Total Budget</h5>
                                        <p class="h3">${format(overview.get('total_budget', 0), ',.0f')}</p>
                                    </div>
                                </div>
                            </div>
                        ''')
                        
                        # Cost
                        html.append(f'''
                            <div class="col-md-3 col-sm-6 mb-3">
                                <div class="card h-100 border-0 shadow-sm">
                                    <div class="card-body text-center">
                                        <i class="fa fa-receipt fa-2x mb-2 text-danger"></i>
                                        <h5>Total Costs</h5>
                                        <p class="h3">${format(overview.get('total_cost', 0), ',.0f')}</p>
                                    </div>
                                </div>
                            </div>
                        ''')
                        
                        # Profit/Loss
                        profit = overview.get('total_profit', 0)
                        is_profit = profit > 0
                        color_class = 'text-success' if is_profit else 'text-danger'
                        
                        html.append(f'''
                            <div class="col-md-3 col-sm-6 mb-3">
                                <div class="card h-100 border-0 shadow-sm">
                                    <div class="card-body text-center">
                                        <i class="fa fa-chart-line fa-2x mb-2 {color_class}"></i>
                                        <h5>Profit/Loss</h5>
                                        <p class="h3 {color_class}">${format(abs(profit), ',.0f')}</p>
                                    </div>
                                </div>
                            </div>
                        ''')
                        
                        html.append('</div>') # End row
                        html.append('</div>') # End card-body
                        html.append('</div>') # End card
                    
                    # Cost Analysis Section
                    if 'cost_analysis' in data and record.show_cost_analysis:
                        cost_data = data['cost_analysis']
                        html.append('<div class="card mb-4 shadow-sm">')
                        html.append('<div class="card-header bg-light"><h5 class="m-0">Cost Analysis</h5></div>')
                        html.append('<div class="card-body">')
                        
                        html.append(f'''
                            <div class="row mb-3">
                                <div class="col-md-4">
                                    <div class="card border-0 bg-light">
                                        <div class="card-body">
                                            <h6 class="card-subtitle mb-2 text-muted">Total Budget</h6>
                                            <p class="card-text h4">${format(cost_data.get('total_budget', 0), ',.0f')}</p>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="card border-0 bg-light">
                                        <div class="card-body">
                                            <h6 class="card-subtitle mb-2 text-muted">Total Actual</h6>
                                            <p class="card-text h4">${format(cost_data.get('total_actual', 0), ',.0f')}</p>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="card border-0 bg-light">
                                        <div class="card-body">
                                            <h6 class="card-subtitle mb-2 text-muted">Variance</h6>
                                            <p class="card-text h4">${format(cost_data.get('total_variance', 0), ',.0f')}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ''')
                        
                        html.append('</div>') # End card-body
                        html.append('</div>') # End card
                    
                    # Yield Comparison Section
                    if 'yield_comparison' in data and record.show_yield_comparison:
                        yield_data = data['yield_comparison']
                        html.append('<div class="card mb-4 shadow-sm">')
                        html.append('<div class="card-header bg-light"><h5 class="m-0">Yield Comparison</h5></div>')
                        html.append('<div class="card-body">')
                        
                        html.append(f'''
                            <div class="row mb-3">
                                <div class="col-md-4">
                                    <div class="card border-0 bg-light">
                                        <div class="card-body">
                                            <h6 class="card-subtitle mb-2 text-muted">Planned Yield</h6>
                                            <p class="card-text h4">{format(yield_data.get('total_planned_yield', 0), ',.0f')}</p>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="card border-0 bg-light">
                                        <div class="card-body">
                                            <h6 class="card-subtitle mb-2 text-muted">Actual Yield</h6>
                                            <p class="card-text h4">{format(yield_data.get('total_actual_yield', 0), ',.0f')}</p>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="card border-0 bg-light">
                                        <div class="card-body">
                                            <h6 class="card-subtitle mb-2 text-muted">Variance</h6>
                                            <p class="card-text h4">{format(yield_data.get('total_yield_variance', 0), ',.0f')}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ''')
                        
                        html.append('</div>') # End card-body
                        html.append('</div>') # End card
                        
                    # Irrigation Statistics Section
                    if 'irrigation_stats' in data and record.show_irrigation_stats:
                        irr_data = data['irrigation_stats']
                        html.append('<div class="card mb-4 shadow-sm">')
                        html.append('<div class="card-header bg-light"><h5 class="m-0">Irrigation Statistics</h5></div>')
                        html.append('<div class="card-body">')
                        
                        html.append(f'''
                            <div class="row mb-3">
                                <div class="col-md-6">
                                    <div class="card border-0 bg-light">
                                        <div class="card-body">
                                            <h6 class="card-subtitle mb-2 text-muted">Total Irrigation Hours</h6>
                                            <p class="card-text h4">{format(irr_data.get('total_irrigation_hours', 0), ',.1f')} hours</p>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="card border-0 bg-light">
                                        <div class="card-body">
                                            <h6 class="card-subtitle mb-2 text-muted">Total Irrigation Events</h6>
                                            <p class="card-text h4">{irr_data.get('total_irrigation_count', 0)}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <h6>Irrigation by Project</h6>
                            <div class="table-responsive">
                                <table class="table table-sm">
                                    <thead>
                                        <tr>
                                            <th>Project</th>
                                            <th>Crop</th>
                                            <th>Hours</th>
                                            <th>Events</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                        ''')
                        
                        for item in irr_data.get('irrigation_by_project', []):
                            html.append(f'''
                                <tr>
                                    <td>{item.get('project_name', '')}</td>
                                    <td>{item.get('crop_name', '')}</td>
                                    <td>{format(item.get('total_irrigation_hours', 0), ',.1f')}</td>
                                    <td>{item.get('irrigation_count', 0)}</td>
                                </tr>
                            ''')
                            
                        html.append('''
                                    </tbody>
                                </table>
                            </div>
                        ''')
                        
                        html.append('</div>') # End card-body
                        html.append('</div>') # End card
                        
                    # Resource Usage Section
                    if 'resource_usage' in data and record.show_resource_usage:
                        res_data = data['resource_usage']
                        html.append('<div class="card mb-4 shadow-sm">')
                        html.append('<div class="card-header bg-light"><h5 class="m-0">Resource Usage</h5></div>')
                        html.append('<div class="card-body">')
                        
                        # Resources by Category
                        if res_data.get('usage_by_category'):
                            html.append('''
                                <h6 class="mb-3">Usage by Category</h6>
                                <div class="table-responsive mb-4">
                                    <table class="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>Category</th>
                                                <th>Quantity</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                            ''')
                            
                            for category, qty in res_data.get('usage_by_category', {}).items():
                                html.append(f'''
                                    <tr>
                                        <td>{category}</td>
                                        <td>{format(qty, ',.2f')}</td>
                                    </tr>
                                ''')
                                
                            html.append('''
                                        </tbody>
                                    </table>
                                </div>
                            ''')
                        
                        # Resources by Product
                        if res_data.get('usage_by_product') and len(res_data.get('usage_by_product')) <= 10:
                            html.append('''
                                <h6 class="mb-3">Top Products Used</h6>
                                <div class="table-responsive">
                                    <table class="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>Product</th>
                                                <th>Quantity</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                            ''')
                            
                            # Get sorted products by usage
                            sorted_products = sorted(
                                res_data.get('usage_by_product', {}).items(),
                                key=lambda x: x[1], 
                                reverse=True
                            )[:10]
                            
                            for product, qty in sorted_products:
                                html.append(f'''
                                    <tr>
                                        <td>{product}</td>
                                        <td>{format(qty, ',.2f')}</td>
                                    </tr>
                                ''')
                                
                            html.append('''
                                        </tbody>
                                    </table>
                                </div>
                            ''')
                            
                        html.append('</div>') # End card-body
                        html.append('</div>') # End card
                        
                else:
                    html.append('''
                        <div class="alert alert-info">
                            <h4 class="alert-heading">No dashboard data available</h4>
                            <p>Please set the filters and refresh the dashboard to see data.</p>
                        </div>
                    ''')
            except Exception as e:
                _logger.error("Error generating dashboard HTML: %s", e)
                html.append(f'''
                    <div class="alert alert-danger">
                        <h4 class="alert-heading">Error generating dashboard</h4>
                        <p>{e}</p>
                    </div>
                ''')
            
            html.append('</div>')  # End container
            record.dashboard_html = ''.join(html)
    
    @api.model
    def get_dashboard_summary(self, date_from=None, date_to=None, farm_ids=None, project_ids=None):
        """Get dashboard summary statistics"""
        domain_farms = []
        domain_projects = []
        domain_reports = []
        domain_costs = []
        
        # Apply date filters
        if date_from:
            domain_projects.append(('start_date', '>=', date_from))
            domain_reports.append(('date', '>=', date_from))
            domain_costs.append(('date', '>=', date_from))
        if date_to:
            domain_projects.append(('start_date', '<=', date_to))
            domain_reports.append(('date', '<=', date_to))
            domain_costs.append(('date', '<=', date_to))
            
        # Apply farm filters
        if farm_ids:
            domain_farms.append(('id', 'in', farm_ids))
            domain_projects.append(('farm_id', 'in', farm_ids))
            domain_reports.append(('project_id.farm_id', 'in', farm_ids))
            domain_costs.append(('project_id.farm_id', 'in', farm_ids))
            
        # Apply project filters
        if project_ids:
            domain_projects.append(('id', 'in', project_ids))
            domain_reports.append(('project_id', 'in', project_ids))
            domain_costs.append(('project_id', 'in', project_ids))
        
        # Count records
        total_farms = self.env['farm.farm'].search_count(domain_farms)
        active_projects = self.env['farm.cultivation.project'].search_count(
            domain_projects + [('state', 'not in', ['done', 'cancel'])]
        )
        daily_reports = self.env['farm.daily.report'].search_count(domain_reports)
        
        # Calculate total costs
        cost_records = self.env['farm.cost.analysis'].search(domain_costs)
        total_costs = sum(cost_records.mapped('cost_amount'))
        
        return {
            'total_farms': total_farms,
            'active_projects': active_projects,
            'daily_reports': daily_reports,
            'total_costs': total_costs,
        }
    
    @api.model
    def get_chart_data(self, date_from=None, date_to=None, farm_ids=None, project_ids=None):
        """Get chart data for dashboard visualizations"""
        domain_base = []
        
        # Apply date filters
        if date_from:
            domain_base.append(('start_date', '>=', date_from))
        if date_to:
            domain_base.append(('start_date', '<=', date_to))
            
        # Apply farm filters
        if farm_ids:
            domain_base.append(('farm_id', 'in', farm_ids))
            
        # Apply project filters
        if project_ids:
            domain_base.append(('id', 'in', project_ids))
        
        # Get farm statistics
        farm_stats = self._get_farm_stats_data(farm_ids)
        
        # Get crop distribution
        crop_distribution = self._get_crop_distribution_data(domain_base)
        
        # Get cost analysis
        cost_analysis = self._get_cost_analysis_data(date_from, date_to, farm_ids, project_ids)
        
        # Get project status
        project_status = self._get_project_status_data(domain_base)
        
        # Get recent activity
        recent_activity = self._get_recent_activity_data(date_from, date_to, farm_ids)
        
        return {
            'farmStats': farm_stats,
            'cropDistribution': crop_distribution,
            'costAnalysis': cost_analysis,
            'projectStatus': project_status,
            'recentActivity': recent_activity,
        }
    
    def _get_farm_stats_data(self, farm_ids=None):
        """Get farm statistics for chart"""
        domain = []
        if farm_ids:
            domain.append(('id', 'in', farm_ids))
        
        farms = self.env['farm.farm'].search(domain)
        
        labels = []
        areas = []
        project_counts = []
        farm_ids_list = []
        
        for farm in farms:
            labels.append(farm.name)
            areas.append(farm.area or 0)
            project_count = self.env['farm.cultivation.project'].search_count([
                ('farm_id', '=', farm.id),
                ('state', 'not in', ['done', 'cancel'])
            ])
            project_counts.append(project_count)
            farm_ids_list.append(farm.id)
        
        return {
            'labels': labels,
            'areas': areas,
            'projects': project_counts,
            'farm_ids': farm_ids_list,
        }
    
    def _get_crop_distribution_data(self, domain_base):
        """Get crop distribution for pie chart"""
        projects = self.env['farm.cultivation.project'].search(domain_base)
        
        crop_counts = defaultdict(int)
        crop_ids_map = {}
        
        for project in projects:
            if project.crop_id:
                crop_name = project.crop_id.name
                crop_counts[crop_name] += 1
                crop_ids_map[crop_name] = project.crop_id.id
        
        return {
            'labels': list(crop_counts.keys()),
            'values': list(crop_counts.values()),
            'crop_ids': [crop_ids_map[label] for label in crop_counts.keys()],
        }
    
    def _get_cost_analysis_data(self, date_from, date_to, farm_ids, project_ids):
        """Get cost analysis data for line chart"""
        domain = []
        
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        if farm_ids:
            domain.append(('project_id.farm_id', 'in', farm_ids))
        if project_ids:
            domain.append(('project_id', 'in', project_ids))
        
        costs = self.env['farm.cost.analysis'].search(domain, order='date asc')
        
        # Group by date
        date_costs = defaultdict(lambda: {'actual': 0, 'budgeted': 0})
        
        for cost in costs:
            date_str = cost.date.strftime('%Y-%m-%d')
            date_costs[date_str]['actual'] += cost.cost_amount
            # For budgeted costs, you might want to implement a budget system
            # For now, we'll use a simple calculation
            date_costs[date_str]['budgeted'] += cost.cost_amount * 1.1  # 10% buffer
        
        sorted_dates = sorted(date_costs.keys())
        
        return {
            'labels': sorted_dates,
            'actualCosts': [date_costs[date]['actual'] for date in sorted_dates],
            'budgetedCosts': [date_costs[date]['budgeted'] for date in sorted_dates],
        }
    
    def _get_project_status_data(self, domain_base):
        """Get project status distribution"""
        projects = self.env['farm.cultivation.project'].search(domain_base)
        
        status_counts = defaultdict(int)
        status_labels = {
            'draft': _('Draft'),
            'planning': _('Planning'),
            'planting': _('Planting'),
            'growing': _('Growing'),
            'harvest': _('Harvest'),
            'done': _('Done'),
            'cancel': _('Cancelled')
        }
        
        for project in projects:
            status_counts[project.state] += 1
        
        labels = []
        values = []
        statuses = []
        
        for status, count in status_counts.items():
            if count > 0:
                labels.append(status_labels.get(status, status.title()))
                values.append(count)
                statuses.append(status)
        
        return {
            'labels': labels,
            'values': values,
            'statuses': statuses,
        }
    
    def _get_recent_activity_data(self, date_from, date_to, farm_ids):
        """Get recent activity data for the last 7 days"""
        if not date_to:
            date_to = fields.Date.today()
        elif isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)
            
        if not date_from:
            date_from = date_to - timedelta(days=7)
        elif isinstance(date_from, str):
            date_from = fields.Date.from_string(date_from)
        
        # Generate date range for last 7 days
        dates = []
        current_date = date_from
        while current_date <= date_to:
            dates.append(current_date)
            current_date += timedelta(days=1)
        
        labels = [current_date.strftime('%m/%d') for current_date in dates]
        daily_reports = []
        cost_entries = []
        
        for current_date in dates:
            # Count daily reports
            report_domain = [('date', '=', current_date)]
            if farm_ids:
                report_domain.append(('project_id.farm_id', 'in', farm_ids))
            
            report_count = self.env['farm.daily.report'].search_count(report_domain)
            daily_reports.append(report_count)
            
            # Count cost entries
            cost_domain = [('date', '=', current_date)]
            if farm_ids:
                cost_domain.append(('project_id.farm_id', 'in', farm_ids))
            
            cost_count = self.env['farm.cost.analysis'].search_count(cost_domain)
            cost_entries.append(cost_count)
        
        return {
            'labels': labels,
            'dailyReports': daily_reports,
            'costEntries': cost_entries,
        }
