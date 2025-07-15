/** @odoo-module alias=farm_management/components/farm_dashboard/farm_dashboard */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

// Import chart loader with the correct alias path
import * as ChartLoader from "@farm_management/js/chart_loader";

// Chart.js will be initialized during setup

/**
 * Farm Management Dashboard
 * A visual dashboard built with OWL and Chart.js for farm management analytics
 */
export class FarmDashboardComponent extends Component {
    static template = "farm_management.FarmDashboardComponent";
    static props = {
        // Define empty props or add specific props if needed
    };

    setup() {
        try {
            console.log("Setting up FarmDashboardComponent");
            
            // Services
            this.orm = useService("orm");
            this.action = useService("action");
            this.notification = useService("notification");
            
            // Initialize state before Chart.js loading
            this.state = useState({
                loading: true,
                filter: {
                    dateFrom: window.moment ? window.moment().subtract(30, 'days').format('YYYY-MM-DD') : new Date(Date.now() - 30*24*60*60*1000).toISOString().split('T')[0],
                    dateTo: window.moment ? window.moment().format('YYYY-MM-DD') : new Date().toISOString().split('T')[0],
                    farmIds: [],
                },
                farms: [],
                farmData: null,
                error: null
            });
            
            // Initialize Chart.js
            this.chartJsLoaded = false;
            this.Chart = null;
            
            console.log("About to load Chart.js using ChartLoader");
            console.log("ChartLoader check:", ChartLoader.isChartLoaderWorking());
            
            ChartLoader.getChartJS()
                .then(ChartJS => {
                    console.log("Chart.js loaded successfully in component");
                    this.Chart = ChartJS;
                    this.chartJsLoaded = true;
                    console.log("Chart.js loaded in dashboard component:", this.Chart.version);
                    
                    // If data is already loaded, render charts
                    if (this.state && !this.state.loading && this.state.farmData) {
                        this.renderCharts();
                    }
                })
                .catch(error => {
                    console.error("Failed to load Chart.js in component:", error);
                    this.state.error = "Failed to load Chart.js";
                    this.notification.add(_t("Failed to load Chart.js. Charts cannot be displayed."), {
                        type: "danger",
                    });
                });
        } catch (error) {
            console.error("Error in FarmDashboardComponent setup:", error);
            this.notification.add(_t("Dashboard initialization failed: ") + error.toString(), {
                type: "danger",
            });
        }
        
        // Dashboard refs - for charts
        this.stageChartRef = useRef("stageChart");
        this.cropChartRef = useRef("cropChart");
        this.costDistributionChartRef = useRef("costDistributionChart");
        this.budgetActualChartRef = useRef("budgetActualChart");
        this.yieldComparisonChartRef = useRef("yieldComparisonChart");
        this.resourceProductChartRef = useRef("resourceProductChart");
        
        // Chart instances
        this.charts = {};
        
        // Get current date and 30 days ago
        const today = new Date();
        const thirtyDaysAgo = new Date();
        thirtyDaysAgo.setDate(today.getDate() - 30);
        
        // Format dates for input fields
        const formatDate = (date) => {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        };
        
        // Dashboard state
        this.state = useState({
            loading: true,
            error: null,
            farmData: null,
            filter: {
                dateFrom: formatDate(thirtyDaysAgo),
                dateTo: formatDate(today),
                farmIds: [],
                cropIds: [],
                projectIds: []
            },
            farms: [],
            crops: [],
            projects: []
        });
        
        // Load data when component is mounted
        onMounted(() => this.loadData());
        
        // Clean up charts when component is unmounted
        onWillUnmount(() => this.destroyCharts());
    }
    
    /**
     * Load dashboard data from the server
     */
    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        
        try {
            // Load filter options
            const [farms, crops, projects] = await Promise.all([
                this.orm.searchRead("farm.farm", [], ["id", "name"]),
                this.orm.searchRead("farm.crop", [], ["id", "name"]),
                this.orm.searchRead("farm.cultivation.project", [], ["id", "name", "farm_id", "crop_id"])
            ]);
            
            this.state.farms = farms;
            this.state.crops = crops;
            this.state.projects = projects;
            
            // Load dashboard data
            await this.refreshDashboard();
        } catch (error) {
            console.error("Failed to load dashboard data", error);
            this.state.error = "Could not load data. Please check your connection and try again.";
            this.notification.add(_t("Failed to load dashboard data"), {
                type: "danger",
            });
            this.state.loading = false;
        }
    }
    
    /**
     * Refresh dashboard data based on current filters
     */
    async refreshDashboard() {
        this.state.loading = true;
        this.state.error = null;
        
        try {
            if (!this.state.farms || !this.state.farms.length) {
                // If we don't have farms loaded yet, skip the rest of the processing
                this.state.loading = false;
                return;
            }
            
            // Prepare domain based on filters
            const domain = [];
            if (this.state.filter.dateFrom) {
                domain.push(['start_date', '>=', this.state.filter.dateFrom]);
            }
            if (this.state.filter.dateTo) {
                domain.push(['start_date', '<=', this.state.filter.dateTo]);
            }
            if (this.state.filter.farmIds.length) {
                domain.push(['farm_id', 'in', this.state.filter.farmIds]);
            }
            if (this.state.filter.cropIds.length) {
                domain.push(['crop_id', 'in', this.state.filter.cropIds]);
            }
            
            // Load projects based on filters
            const projects = await this.orm.searchRead(
                "farm.cultivation.project", 
                domain,
                [
                    "name", "field_area", "budget", "actual_cost", 
                    "revenue", "profit", "state", "crop_id",
                    "planned_yield", "actual_yield", "yield_quality"
                ]
            );
            
            // Skip rest of processing if no projects found
            if (!projects.length) {
                this.state.farmData = {
                    farmOverview: { totalProjects: 0 },
                    costAnalysis: {},
                    yieldComparison: { yieldData: [] },
                    resourceUsage: {},
                    irrigationStats: {}
                };
                this.state.loading = false;
                return;
            }
            
            // Get cost analysis data for these projects
            const costAnalysis = await this.orm.searchRead(
                "farm.cost.analysis",
                [['project_id', 'in', projects.map(p => p.id)]],
                ["project_id", "cost_type", "cost_amount", "date"]
            );
            
            // Get irrigation data for these projects
            const irrigationData = await this.orm.searchRead(
                "farm.daily.report",
                [
                    ['project_id', 'in', projects.map(p => p.id)],
                    ['operation_type', '=', 'irrigation']
                ],
                ["project_id", "date", "irrigation_duration"]
            );
            
            // Get resource usage data
            const dailyReports = await this.orm.searchRead(
                "farm.daily.report",
                [['project_id', 'in', projects.map(p => p.id)]],
                ["id"]
            );
            
            let productLines = [];
            if (dailyReports.length > 0) {
                productLines = await this.orm.searchRead(
                    "farm.daily.report.line",
                    [['report_id', 'in', dailyReports.map(r => r.id)]],
                    ["product_id", "quantity"]
                );
            }
            
            // Process all the data
            const dashboardData = {
                farmOverview: this.processFarmOverviewData(projects),
                costAnalysis: this.processCostAnalysisData(costAnalysis, projects),
                yieldComparison: this.processYieldComparisonData(projects),
                resourceUsage: this.processResourceUsageData(productLines),
                irrigationStats: this.processIrrigationData(irrigationData, projects)
            };
            
            this.state.farmData = dashboardData;
            
            // Render charts after data is processed
            this.destroyCharts();
            
            // Wait longer for the DOM to be fully updated
            setTimeout(() => {
                this.renderCharts();
            }, 500);
        } catch (error) {
            console.error("Failed to refresh dashboard data", error);
            this.state.error = `Error loading dashboard data: ${error.message || "Unknown error"}`;
            this.notification.add(_t("Failed to refresh dashboard data"), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }
    
    /**
     * Process farm overview data
     */
    processFarmOverviewData(projects) {
        // Calculate totals
        const totalArea = projects.reduce((sum, p) => sum + (p.field_area || 0), 0);
        const totalBudget = projects.reduce((sum, p) => sum + (p.budget || 0), 0);
        const totalCost = projects.reduce((sum, p) => sum + (p.actual_cost || 0), 0);
        const totalRevenue = projects.reduce((sum, p) => sum + (p.revenue || 0), 0);
        const totalProfit = projects.reduce((sum, p) => sum + (p.profit || 0), 0);
        
        // Count projects by stage
        const stageCounts = {};
        const stages = {
            'draft': _t('Draft'),
            'planned': _t('Planned'),
            'in_progress': _t('In Progress'),
            'completed': _t('Completed'),
            'cancelled': _t('Cancelled')
        };
        
        Object.keys(stages).forEach(stage => {
            stageCounts[stage] = {
                name: stages[stage],
                count: projects.filter(p => p.state === stage).length
            };
        });
        
        // Count projects by crop
        const cropCounts = {};
        projects.forEach(project => {
            if (project.crop_id) {
                const cropId = project.crop_id[0];
                const cropName = project.crop_id[1];
                if (!cropCounts[cropName]) {
                    cropCounts[cropName] = 0;
                }
                cropCounts[cropName]++;
            }
        });
        
        return {
            totalProjects: projects.length,
            totalArea: totalArea,
            totalBudget: totalBudget,
            totalCost: totalCost,
            totalRevenue: totalRevenue,
            totalProfit: totalProfit,
            budgetUsagePercentage: totalBudget ? (totalCost / totalBudget * 100) : 0,
            profitMargin: totalRevenue ? (totalProfit / totalRevenue * 100) : 0,
            stageCounts: stageCounts,
            cropCounts: cropCounts
        };
    }
    
    /**
     * Process cost analysis data
     */
    processCostAnalysisData(costRecords, projects) {
        // Group costs by type
        const costByType = {};
        costRecords.forEach(record => {
            if (!costByType[record.cost_type]) {
                costByType[record.cost_type] = 0;
            }
            costByType[record.cost_type] += record.cost_amount;
        });
        
        // Calculate budget vs actual by project
        const budgetVsActual = projects.map(project => ({
            projectName: project.name,
            budget: project.budget || 0,
            actual: project.actual_cost || 0,
            variance: (project.budget || 0) - (project.actual_cost || 0),
            variancePercentage: project.budget ? ((project.budget - (project.actual_cost || 0)) / project.budget * 100) : 0
        }));
        
        return {
            costByType: costByType,
            budgetVsActual: budgetVsActual,
            totalBudget: projects.reduce((sum, p) => sum + (p.budget || 0), 0),
            totalActual: projects.reduce((sum, p) => sum + (p.actual_cost || 0), 0),
            totalVariance: projects.reduce((sum, p) => sum + ((p.budget || 0) - (p.actual_cost || 0)), 0)
        };
    }
    
    /**
     * Process yield comparison data
     */
    processYieldComparisonData(projects) {
        const yieldData = projects
            .filter(p => p.planned_yield > 0 || p.actual_yield > 0)
            .map(project => ({
                projectName: project.name,
                cropName: project.crop_id ? project.crop_id[1] : '',
                plannedYield: project.planned_yield || 0,
                actualYield: project.actual_yield || 0,
                yieldVariance: (project.actual_yield || 0) - (project.planned_yield || 0),
                yieldVariancePercentage: project.planned_yield ? 
                    ((project.actual_yield || 0) - project.planned_yield) / project.planned_yield * 100 : 0,
                yieldQuality: project.yield_quality || ''
            }));
        
        return {
            yieldData: yieldData,
            totalPlannedYield: projects.reduce((sum, p) => sum + (p.planned_yield || 0), 0),
            totalActualYield: projects.reduce((sum, p) => sum + (p.actual_yield || 0), 0),
            totalYieldVariance: projects.reduce((sum, p) => sum + ((p.actual_yield || 0) - (p.planned_yield || 0)), 0)
        };
    }
    
    /**
     * Process irrigation data
     */
    processIrrigationData(irrigationReports, projects) {
        // Group irrigation by project
        const irrigationByProject = {};
        irrigationReports.forEach(report => {
            const projectId = report.project_id[0];
            if (!irrigationByProject[projectId]) {
                irrigationByProject[projectId] = [];
            }
            irrigationByProject[projectId].push({
                date: report.date,
                duration: report.irrigation_duration || 0
            });
        });
        
        // Calculate total irrigation time by project
        const totalByProject = [];
        Object.keys(irrigationByProject).forEach(projectId => {
            const irrigations = irrigationByProject[projectId];
            const project = projects.find(p => p.id === parseInt(projectId));
            if (project) {
                totalByProject.push({
                    projectName: project.name,
                    cropName: project.crop_id ? project.crop_id[1] : '',
                    totalIrrigationHours: irrigations.reduce((sum, item) => sum + item.duration, 0),
                    irrigationCount: irrigations.length
                });
            }
        });
        
        return {
            totalIrrigationHours: irrigationReports.reduce((sum, report) => sum + (report.irrigation_duration || 0), 0),
            totalIrrigationCount: irrigationReports.length,
            irrigationByProject: totalByProject
        };
    }
    
    /**
     * Process resource usage data
     */
    processResourceUsageData(productLines) {
        // Fetch product details first
        const productIds = productLines.map(line => line.product_id[0]);
        
        // Group by product category
        const usageByCategory = {};
        const usageByProduct = {};
        
        productLines.forEach(line => {
            if (line.product_id) {
                const productId = line.product_id[0];
                const productName = line.product_id[1];
                
                if (!usageByProduct[productName]) {
                    usageByProduct[productName] = 0;
                }
                usageByProduct[productName] += line.quantity;
            }
        });
        
        return {
            usageByCategory: usageByCategory,
            usageByProduct: usageByProduct
        };
    }
    
    /**
     * Render all charts
     */
    renderCharts() {
        console.log("Initializing charts...");
        
        if (!this.chartJsLoaded || !this.Chart) {
            console.error("Chart.js is not loaded yet or failed to load!");
            this.notification.add(_t("Chart.js is not loaded. Charts cannot be displayed."), {
                type: "warning",
            });
            return;
        }
        
        // Wait longer for the DOM to be fully updated and Chart.js to be ready
        setTimeout(() => {
            try {
                console.log("DOM ready, rendering charts");
                this.renderFarmOverviewCharts();
                this.renderCostAnalysisCharts();
                this.renderYieldComparisonCharts();
                this.renderResourceUsageCharts();
                console.log("Charts initialization complete");
            } catch (error) {
                console.error("Error rendering charts:", error);
                this.notification.add(_t("Error rendering charts: ") + error.message, {
                    type: "danger",
                });
            }
        }, 500);  // Increased timeout to 500ms for better chart rendering
    }
    
    /**
     * Render farm overview charts
     */
    renderFarmOverviewCharts() {
        if (!this.state.farmData || !this.state.farmData.farmOverview) {
            console.warn("No farm overview data available");
            return;
        }
        
        if (!this.stageChartRef.el || !this.cropChartRef.el) {
            console.error("Farm overview chart elements not found");
            return;
        }
        
        const overview = this.state.farmData.farmOverview;
        
        // Project Stage Chart
        try {
            const stageLabels = [];
            const stageData = [];
            const stageColors = [
                'rgba(255, 99, 132, 0.7)',
                'rgba(54, 162, 235, 0.7)',
                'rgba(255, 206, 86, 0.7)',
                'rgba(75, 192, 192, 0.7)',
                'rgba(153, 102, 255, 0.7)'
            ];
            
            for (const stage in overview.stageCounts) {
                stageLabels.push(overview.stageCounts[stage].name);
                stageData.push(overview.stageCounts[stage].count);
            }
            
            console.log("Creating project stage chart", stageLabels, stageData);
            
            this.charts.stageChart = new this.Chart(this.stageChartRef.el, {
                type: 'doughnut',
                data: {
                    labels: stageLabels,
                    datasets: [{
                        data: stageData,
                        backgroundColor: stageColors,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                        },
                        title: {
                            display: true,
                            text: _t('Projects by Stage')
                        }
                    }
                }
            });
            console.log("Project stage chart created successfully");
        } catch (e) {
            console.error("Error creating project stage chart:", e);
        }
    
        // Project Crop Chart
        try {
            const cropLabels = [];
            const cropData = [];
            const cropColors = [
                'rgba(255, 99, 132, 0.7)',
                'rgba(54, 162, 235, 0.7)',
                'rgba(255, 206, 86, 0.7)',
                'rgba(75, 192, 192, 0.7)',
                'rgba(153, 102, 255, 0.7)',
                'rgba(255, 159, 64, 0.7)',
                'rgba(201, 203, 207, 0.7)',
                'rgba(255, 99, 132, 0.7)'
            ];
            
            for (const crop in overview.cropCounts) {
                cropLabels.push(crop);
                cropData.push(overview.cropCounts[crop]);
            }
            
            console.log("Creating crop chart", cropLabels, cropData);
            
            this.charts.cropChart = new this.Chart(this.cropChartRef.el, {
                type: 'pie',
                data: {
                    labels: cropLabels,
                    datasets: [{
                        data: cropData,
                        backgroundColor: cropColors,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                        },
                        title: {
                            display: true,
                            text: _t('Projects by Crop')
                        }
                    }
                }
            });
            console.log("Crop chart created successfully");
        } catch (e) {
            console.error("Error creating crop chart:", e);
        }
    }
    
    /**
     * Render cost analysis charts
     */
    renderCostAnalysisCharts() {
        if (!this.state.farmData || !this.state.farmData.costAnalysis) {
            console.warn("No cost analysis data available");
            return;
        }
        
        if (!this.costDistributionChartRef.el || !this.budgetActualChartRef.el) {
            console.error("Cost analysis chart elements not found");
            return;
        }
        
        const costData = this.state.farmData.costAnalysis;
        
        // Cost Distribution Chart
        try {
            const costLabels = Object.keys(costData.costByType);
            const costValues = Object.values(costData.costByType);
            const costColors = [
                'rgba(255, 99, 132, 0.7)',
                'rgba(54, 162, 235, 0.7)',
                'rgba(255, 206, 86, 0.7)',
                'rgba(75, 192, 192, 0.7)',
                'rgba(153, 102, 255, 0.7)'
            ];
            
            console.log("Creating cost distribution chart", costLabels, costValues);
            
            this.charts.costDistribution = new this.Chart(this.costDistributionChartRef.el, {
                type: 'doughnut',
                data: {
                    labels: costLabels,
                    datasets: [{
                        data: costValues,
                        backgroundColor: costColors,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                        },
                        title: {
                            display: true,
                            text: _t('Cost Distribution by Type')
                        }
                    }
                }
            });
            console.log("Cost distribution chart created successfully");
        } catch (e) {
            console.error("Error creating cost distribution chart:", e);
        }
        
        // Budget vs Actual Chart
        try {
            if (costData.budgetVsActual && costData.budgetVsActual.length > 0) {
                const budgetLabels = costData.budgetVsActual.map(item => item.projectName);
                const budgetData = costData.budgetVsActual.map(item => item.budget);
                const actualData = costData.budgetVsActual.map(item => item.actual);
                
                console.log("Creating budget vs actual chart", budgetLabels, budgetData, actualData);
                
                this.charts.budgetActual = new this.Chart(this.budgetActualChartRef.el, {
                    type: 'bar',
                    data: {
                        labels: budgetLabels,
                        datasets: [
                            {
                                label: _t('Budget'),
                                data: budgetData,
                                backgroundColor: 'rgba(54, 162, 235, 0.7)',
                                borderColor: 'rgba(54, 162, 235, 1)',
                                borderWidth: 1
                            },
                            {
                                label: _t('Actual'),
                                data: actualData,
                                backgroundColor: 'rgba(255, 99, 132, 0.7)',
                                borderColor: 'rgba(255, 99, 132, 1)',
                                borderWidth: 1
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            x: {
                                stacked: false,
                            },
                            y: {
                                beginAtZero: true
                            }
                        },
                        plugins: {
                            title: {
                                display: true,
                                text: _t('Budget vs Actual Cost by Project')
                            }
                        }
                    }
                });
                console.log("Budget vs actual chart created successfully");
            }
        } catch (e) {
            console.error("Error creating budget vs actual chart:", e);
        }
    }
    
    /**
     * Render yield comparison charts
     */
    renderYieldComparisonCharts() {
        if (!this.state.farmData || !this.state.farmData.yieldComparison) {
            console.warn("No yield comparison data available");
            return;
        }
        
        if (!this.yieldComparisonChartRef.el) {
            console.error("Yield comparison chart element not found");
            return;
        }
        
        const yieldData = this.state.farmData.yieldComparison;
        
        try {
            if (yieldData.yieldData && yieldData.yieldData.length > 0) {
                const yieldLabels = yieldData.yieldData.map(item => item.projectName);
                const plannedYieldData = yieldData.yieldData.map(item => item.plannedYield);
                const actualYieldData = yieldData.yieldData.map(item => item.actualYield);
                
                console.log("Creating yield comparison chart", yieldLabels, plannedYieldData, actualYieldData);
                
                this.charts.yieldComparison = new this.Chart(this.yieldComparisonChartRef.el, {
                    type: 'bar',
                    data: {
                        labels: yieldLabels,
                        datasets: [
                            {
                                label: _t('Planned Yield'),
                                data: plannedYieldData,
                                backgroundColor: 'rgba(54, 162, 235, 0.7)',
                                borderColor: 'rgba(54, 162, 235, 1)',
                                borderWidth: 1
                            },
                            {
                                label: _t('Actual Yield'),
                                data: actualYieldData,
                                backgroundColor: 'rgba(75, 192, 192, 0.7)',
                                borderColor: 'rgba(75, 192, 192, 1)',
                                borderWidth: 1
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            x: {
                                stacked: false,
                            },
                            y: {
                                beginAtZero: true
                            }
                        },
                        plugins: {
                            title: {
                                display: true,
                                text: _t('Planned vs Actual Yield')
                            }
                        }
                    }
                });
                console.log("Yield comparison chart created successfully");
            }
        } catch (e) {
            console.error("Error creating yield comparison chart:", e);
        }
    }
    
    /**
     * Render resource usage charts
     */
    renderResourceUsageCharts() {
        if (!this.state.farmData || !this.state.farmData.resourceUsage) {
            console.warn("No resource usage data available");
            return;
        }
        
        if (!this.resourceProductChartRef.el) {
            console.error("Resource usage chart element not found");
            return;
        }
        
        const resourceData = this.state.farmData.resourceUsage;
        
        // Top Products Usage Chart
        try {
            const productLabels = Object.keys(resourceData.usageByProduct).slice(0, 10);
            const productValues = productLabels.map(label => resourceData.usageByProduct[label]);
            
            console.log("Creating resource product chart", productLabels, productValues);
            
            this.charts.resourceProduct = new this.Chart(this.resourceProductChartRef.el, {
                type: 'bar',
                data: {
                    labels: productLabels,
                    datasets: [{
                        label: _t('Usage Quantity'),
                        data: productValues,
                        backgroundColor: 'rgba(153, 102, 255, 0.7)',
                        borderColor: 'rgba(153, 102, 255, 1)',
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
                            text: _t('Top Products Usage')
                        }
                    }
                }
            });
            console.log("Resource product chart created successfully");
        } catch (e) {
            console.error("Error creating resource product chart:", e);
        }
    }
    
    /**
     * Destroy all chart instances to prevent memory leaks
     */
    destroyCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        this.charts = {};
    }
    
    /**
     * Update date filter
     */
    updateDateFilter(field, value) {
        this.state.filter[field] = value;
    }
    
    /**
     * Toggle farm filter
     */
    toggleFarmFilter(farmId) {
        const index = this.state.filter.farmIds.indexOf(farmId);
        if (index === -1) {
            this.state.filter.farmIds.push(farmId);
        } else {
            this.state.filter.farmIds.splice(index, 1);
        }
    }
    
    /**
     * Toggle crop filter
     */
    toggleCropFilter(cropId) {
        const index = this.state.filter.cropIds.indexOf(cropId);
        if (index === -1) {
            this.state.filter.cropIds.push(cropId);
        } else {
            this.state.filter.cropIds.splice(index, 1);
        }
    }
    
    /**
     * Apply filters and refresh dashboard
     */
    async applyFilters() {
        await this.refreshDashboard();
    }
}

// The component is registered in dashboard_loader.js
