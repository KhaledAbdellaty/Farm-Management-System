/** @odoo-module */

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Farm Management Dashboard
 * Interactive dashboard with Chart.js visualizations and navigation capabilities
 */
export class FarmDashboard extends Component {
    static template = "farm_management.FarmDashboard";
    static props = {};

    setup() {
        // Services
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");

        // Chart references
        this.chartRefs = {
            farmStats: useRef("farmStatsChart"),
            cropDistribution: useRef("cropDistributionChart"),
            costAnalysis: useRef("costAnalysisChart"),
            projectStatus: useRef("projectStatusChart"),
            recentActivity: useRef("recentActivityChart")
        };

        // Dashboard state
        this.state = useState({
            loading: true,
            error: null,
            filters: {
                dateFrom: this._getDefaultDateFrom(),
                dateTo: this._getDefaultDateTo(),
                farmIds: [],
                projectIds: []
            },
            data: {
                summary: {},
                charts: {},
                farms: [],
                projects: []
            },
            charts: {}
        });

        // Initialize dashboard
        onMounted(async () => {
            await this._initializeDashboard();
        });

        onWillUnmount(() => {
            this._destroyCharts();
        });
    }

    /**
     * Initialize the dashboard by loading data and creating charts
     */
    async _initializeDashboard() {
        try {
            this.state.loading = true;
            this.state.error = null;

            // Load Chart.js
            await this._loadChartJS();
            
            // Load dashboard data
            await Promise.all([
                this._loadFarms(),
                this._loadProjects(),
                this._loadDashboardData()
            ]);

            // Create charts
            await this._createCharts();

            this.state.loading = false;
        } catch (error) {
            console.error("Dashboard initialization failed:", error);
            this.state.error = error.message;
            this.state.loading = false;
            this.notification.add(_t("Failed to initialize dashboard: ") + error.message, {
                type: "danger"
            });
        }
    }

    /**
     * Load Chart.js library
     */
    async _loadChartJS() {
        if (window.Chart) {
            return window.Chart;
        }
        
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = '/farm_management/static/vendor/chart.min.js';
            script.onload = () => {
                if (window.Chart) {
                    resolve(window.Chart);
                } else {
                    reject(new Error("Chart.js failed to load"));
                }
            };
            script.onerror = () => reject(new Error("Failed to load Chart.js"));
            document.head.appendChild(script);
        });
    }

    /**
     * Load farms for filtering
     */
    async _loadFarms() {
        const farms = await this.orm.searchRead("farm.farm", [], ["id", "name", "total_area"]);
        this.state.data.farms = farms;
    }

    /**
     * Load projects for filtering
     */
    async _loadProjects() {
        const projects = await this.orm.searchRead("farm.cultivation.project", 
            [["state", "!=", "cancel"]], 
            ["id", "name", "state", "start_date", "end_date"]
        );
        this.state.data.projects = projects;
    }

    /**
     * Load dashboard data based on current filters
     */
    async _loadDashboardData() {
        const filters = this._buildFilters();
        
        // Load summary statistics
        const summary = await this.orm.call("farm.dashboard", "get_dashboard_summary", [], {
            date_from: this.state.filters.dateFrom,
            date_to: this.state.filters.dateTo,
            farm_ids: this.state.filters.farmIds,
            project_ids: this.state.filters.projectIds
        });

        // Load chart data
        const chartData = await this.orm.call("farm.dashboard", "get_chart_data", [], {
            date_from: this.state.filters.dateFrom,
            date_to: this.state.filters.dateTo,
            farm_ids: this.state.filters.farmIds,
            project_ids: this.state.filters.projectIds
        });

        this.state.data.summary = summary;
        this.state.data.charts = chartData;
    }

    /**
     * Create all dashboard charts
     */
    async _createCharts() {
        this._destroyCharts();

        const Chart = window.Chart;
        if (!Chart) {
            throw new Error("Chart.js not available");
        }

        // Configure Chart.js defaults
        Chart.defaults.plugins.legend.onClick = (evt, legendItem, legend) => {
            // Custom legend click handler for navigation
            const chart = legend.chart;
            const meta = chart.getDatasetMeta(legendItem.datasetIndex);
            
            // Toggle dataset visibility
            meta.hidden = meta.hidden === null ? !chart.data.datasets[legendItem.datasetIndex].hidden : null;
            chart.update();
        };

        // Create individual charts
        await Promise.all([
            this._createFarmStatsChart(),
            this._createCropDistributionChart(),
            this._createCostAnalysisChart(),
            this._createProjectStatusChart(),
            this._createRecentActivityChart()
        ]);
    }

    /**
     * Create farm statistics chart
     */
    async _createFarmStatsChart() {
        const canvas = this.chartRefs.farmStats.el;
        if (!canvas) return;

        const data = this.state.data.charts.farmStats || {};
        
        this.state.charts.farmStats = new window.Chart(canvas, {
            type: 'bar',
            data: {
                labels: data.labels || [],
                datasets: [{
                    label: _t('Total Area (hectares)'),
                    data: data.areas || [],
                    backgroundColor: 'rgba(54, 162, 235, 0.6)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }, {
                    label: _t('Active Projects'),
                    data: data.projects || [],
                    backgroundColor: 'rgba(255, 99, 132, 0.6)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: _t('Farm Statistics')
                    },
                    legend: {
                        display: true
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const farmIndex = elements[0].index;
                        const farmId = data.farm_ids?.[farmIndex];
                        if (farmId) {
                            this._navigateToFarm(farmId);
                        }
                    }
                }
            }
        });
    }

    /**
     * Create crop distribution chart
     */
    async _createCropDistributionChart() {
        const canvas = this.chartRefs.cropDistribution.el;
        if (!canvas) return;

        const data = this.state.data.charts.cropDistribution || {};
        
        this.state.charts.cropDistribution = new window.Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: data.labels || [],
                datasets: [{
                    data: data.values || [],
                    backgroundColor: [
                        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
                        '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: _t('Crop Distribution')
                    },
                    legend: {
                        position: 'bottom'
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const cropIndex = elements[0].index;
                        const cropId = data.crop_ids?.[cropIndex];
                        if (cropId) {
                            this._navigateToCrop(cropId);
                        }
                    }
                }
            }
        });
    }

    /**
     * Create cost analysis chart
     */
    async _createCostAnalysisChart() {
        const canvas = this.chartRefs.costAnalysis.el;
        if (!canvas) return;

        const data = this.state.data.charts.costAnalysis || {};
        
        this.state.charts.costAnalysis = new window.Chart(canvas, {
            type: 'line',
            data: {
                labels: data.labels || [],
                datasets: [{
                    label: _t('Actual Costs'),
                    data: data.actualCosts || [],
                    borderColor: 'rgba(255, 99, 132, 1)',
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    tension: 0.1
                }, {
                    label: _t('Budgeted Costs'),
                    data: data.budgetedCosts || [],
                    borderColor: 'rgba(54, 162, 235, 1)',
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return new Intl.NumberFormat('en-US', {
                                    style: 'currency',
                                    currency: 'USD'
                                }).format(value);
                            }
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: _t('Cost Analysis')
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        this._navigateToCostAnalysis();
                    }
                }
            }
        });
    }

    /**
     * Create project status chart
     */
    async _createProjectStatusChart() {
        const canvas = this.chartRefs.projectStatus.el;
        if (!canvas) return;

        const data = this.state.data.charts.projectStatus || {};
        
        this.state.charts.projectStatus = new window.Chart(canvas, {
            type: 'pie',
            data: {
                labels: data.labels || [],
                datasets: [{
                    data: data.values || [],
                    backgroundColor: ['#4CAF50', '#FF9800', '#2196F3', '#F44336', '#9C27B0']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: _t('Project Status')
                    },
                    legend: {
                        position: 'bottom'
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const statusIndex = elements[0].index;
                        const status = data.statuses?.[statusIndex];
                        if (status) {
                            this._navigateToProjects(status);
                        }
                    }
                }
            }
        });
    }

    /**
     * Create recent activity chart
     */
    async _createRecentActivityChart() {
        const canvas = this.chartRefs.recentActivity.el;
        if (!canvas) return;

        const data = this.state.data.charts.recentActivity || {};
        
        this.state.charts.recentActivity = new window.Chart(canvas, {
            type: 'bar',
            data: {
                labels: data.labels || [],
                datasets: [{
                    label: _t('Daily Reports'),
                    data: data.dailyReports || [],
                    backgroundColor: 'rgba(75, 192, 192, 0.6)'
                }, {
                    label: _t('Cost Entries'),
                    data: data.costEntries || [],
                    backgroundColor: 'rgba(255, 206, 86, 0.6)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: _t('Recent Activity (Last 7 Days)')
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        this._navigateToDailyReports();
                    }
                }
            }
        });
    }

    /**
     * Navigation methods
     */
    _navigateToFarm(farmId) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'farm.farm',
            res_id: farmId,
            views: [[false, 'form']],
            target: 'current'
        });
    }

    _navigateToCrop(cropId) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'farm.crop',
            res_id: cropId,
            views: [[false, 'form']],
            target: 'current'
        });
    }

    _navigateToCostAnalysis() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'farm.cost.analysis',
            views: [[false, 'list'], [false, 'form']],
            target: 'current'
        });
    }

    _navigateToProjects(status = null) {
        const domain = status ? [['state', '=', status]] : [];
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'farm.cultivation.project',
            domain: domain,
            views: [[false, 'list'], [false, 'form']],
            target: 'current'
        });
    }

    _navigateToDailyReports() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'farm.daily.report',
            views: [[false, 'list'], [false, 'form']],
            target: 'current'
        });
    }

    /**
     * Filter and event handlers
     */
    async onDateFilterChange(field, value) {
        this.state.filters[field] = value;
        await this._refreshDashboard();
    }

    async onFarmFilterChange(farmId) {
        const farmIds = [...this.state.filters.farmIds];
        const index = farmIds.indexOf(farmId);
        
        if (index > -1) {
            farmIds.splice(index, 1);
        } else {
            farmIds.push(farmId);
        }
        
        this.state.filters.farmIds = farmIds;
        await this._refreshDashboard();
    }

    async onRefresh() {
        await this._refreshDashboard();
    }

    /**
     * Utility methods
     */
    async _refreshDashboard() {
        this.state.loading = true;
        try {
            await this._loadDashboardData();
            await this._createCharts();
        } catch (error) {
            console.error("Dashboard refresh failed:", error);
            this.notification.add(_t("Failed to refresh dashboard"), { type: "danger" });
        }
        this.state.loading = false;
    }

    _destroyCharts() {
        Object.values(this.state.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        this.state.charts = {};
    }

    _buildFilters() {
        return {
            date_from: this.state.filters.dateFrom,
            date_to: this.state.filters.dateTo,
            farm_ids: this.state.filters.farmIds,
            project_ids: this.state.filters.projectIds
        };
    }

    _getDefaultDateFrom() {
        const date = new Date();
        date.setMonth(date.getMonth() - 1);
        return date.toISOString().split('T')[0];
    }

    _getDefaultDateTo() {
        return new Date().toISOString().split('T')[0];
    }

    /**
     * Summary card navigation handlers
     */
    onSummaryCardClick(cardType) {
        switch (cardType) {
            case 'farms':
                this.actionService.doAction({
                    type: 'ir.actions.act_window',
                    res_model: 'farm.farm',
                    views: [[false, 'list'], [false, 'form']],
                    target: 'current'
                });
                break;
            case 'projects':
                this._navigateToProjects();
                break;
            case 'reports':
                this._navigateToDailyReports();
                break;
            case 'costs':
                this._navigateToCostAnalysis();
                break;
        }
    }
}
