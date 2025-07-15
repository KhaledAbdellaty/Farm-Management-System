/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { FormRenderer } from "@web/views/form/form_renderer";
import { formView } from "@web/views/form/form_view";
import { _t } from "@web/core/l10n/translation";
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";

/**
 * Farm Dashboard Component
 * Extends the standard FormRenderer to add chart visualization capabilities
 */
class FarmDashboardRenderer extends FormRenderer {
    setup() {
        super.setup();
        
        this.state = useState({
            chartsInitialized: false,
        });
        
        // Initialize charts when component is mounted
        onMounted(() => {
            if (this.props.record.resModel === 'farm.dashboard') {
                // Wait a bit to ensure DOM is fully rendered
                setTimeout(() => this.initCharts(), 300);
            }
        });
        
        // Clean up any chart instances when component is unmounted
        onWillUnmount(() => {
            // If you need to clean up chart instances
        });
    }
    
    /**
     * Initialize all dashboard charts
     */
    initCharts() {
        if (this.state.chartsInitialized) return;
        
        // Initialize all charts
        this.initProjectStageChart();
        this.initProjectCropChart();
        this.initCostDistributionChart();
        this.initBudgetActualChart();
        this.initYieldComparisonChart();
        this.initIrrigationChart();
        this.initResourceCategoryChart();
        this.initResourceProductChart();
        
        this.state.chartsInitialized = true;
    }
    
    /**
     * Initialize Project Stage Chart
     */
    initProjectStageChart() {
        const chartElement = this.el.querySelector('#projectStageChart');
        if (!chartElement) return;

        let stagesData;
        try {
            stagesData = JSON.parse(chartElement.dataset.stages || '{}');
        } catch (e) {
            console.error('Failed to parse stages data', e);
            return;
        }

        const labels = [];
        const data = [];
        const backgroundColor = [
            'rgba(255, 99, 132, 0.7)',
            'rgba(54, 162, 235, 0.7)',
            'rgba(255, 206, 86, 0.7)',
            'rgba(75, 192, 192, 0.7)',
            'rgba(153, 102, 255, 0.7)',
            'rgba(255, 159, 64, 0.7)',
            'rgba(201, 203, 207, 0.7)',
            'rgba(255, 99, 132, 0.7)'
        ];

        // Prepare data for chart
        for (const stage in stagesData) {
            labels.push(stagesData[stage].name);
            data.push(stagesData[stage].count);
        }

        // Create chart
        new Chart(chartElement, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: backgroundColor,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    /**
     * Initialize Project Crop Chart
     */
    initProjectCropChart() {
        const chartElement = this.el.querySelector('#projectCropChart');
        if (!chartElement) return;

        let cropsData;
        try {
            cropsData = JSON.parse(chartElement.dataset.crops || '{}');
        } catch (e) {
            console.error('Failed to parse crops data', e);
            return;
        }

        const labels = [];
        const data = [];
        const backgroundColor = [
            'rgba(75, 192, 192, 0.7)',
            'rgba(54, 162, 235, 0.7)',
            'rgba(255, 206, 86, 0.7)',
            'rgba(255, 99, 132, 0.7)',
            'rgba(153, 102, 255, 0.7)',
            'rgba(255, 159, 64, 0.7)',
            'rgba(201, 203, 207, 0.7)',
            'rgba(255, 99, 132, 0.7)'
        ];

        // Prepare data for chart
        for (const crop in cropsData) {
            labels.push(crop);
            data.push(cropsData[crop]);
        }

        // Create chart
        new Chart(chartElement, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: backgroundColor,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    /**
     * Initialize Cost Distribution Chart
     */
    initCostDistributionChart() {
        const chartElement = this.el.querySelector('#costDistributionChart');
        if (!chartElement) return;

        let costData;
        try {
            costData = JSON.parse(chartElement.dataset.costs || '{}');
        } catch (e) {
            console.error('Failed to parse cost data', e);
            return;
        }

        const labels = [];
        const data = [];
        const backgroundColor = [
            'rgba(255, 99, 132, 0.7)',
            'rgba(54, 162, 235, 0.7)',
            'rgba(255, 206, 86, 0.7)',
            'rgba(75, 192, 192, 0.7)',
            'rgba(153, 102, 255, 0.7)',
            'rgba(255, 159, 64, 0.7)',
            'rgba(201, 203, 207, 0.7)',
            'rgba(255, 99, 132, 0.7)'
        ];

        // Prepare data for chart
        for (const costType in costData) {
            // Use translation mapping
            const label = this.getCostTypeLabel(costType);
            labels.push(label);
            data.push(costData[costType]);
        }

        // Create chart
        new Chart(chartElement, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: backgroundColor,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'right'
                    }
                }
            }
        });
    }

    /**
     * Initialize Budget vs Actual Chart
     */
    initBudgetActualChart() {
        const chartElement = this.el.querySelector('#budgetActualChart');
        if (!chartElement) return;

        let budgetData;
        try {
            budgetData = JSON.parse(chartElement.dataset.budget || '[]');
        } catch (e) {
            console.error('Failed to parse budget data', e);
            return;
        }

        const labels = [];
        const budgetValues = [];
        const actualValues = [];

        // Prepare data for chart (limit to top 8 for readability)
        const limitedData = budgetData.slice(0, 8);
        for (let i = 0; i < limitedData.length; i++) {
            labels.push(limitedData[i].project_name);
            budgetValues.push(limitedData[i].budget);
            actualValues.push(limitedData[i].actual);
        }

        // Create chart
        new Chart(chartElement, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: _t('Budget'),
                        data: budgetValues,
                        backgroundColor: 'rgba(54, 162, 235, 0.7)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    },
                    {
                        label: _t('Actual'),
                        data: actualValues,
                        backgroundColor: 'rgba(255, 99, 132, 0.7)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    /**
     * Initialize Yield Comparison Chart
     */
    initYieldComparisonChart() {
        const chartElement = this.el.querySelector('#yieldComparisonChart');
        if (!chartElement) return;

        let yieldData;
        try {
            yieldData = JSON.parse(chartElement.dataset.yield || '[]');
        } catch (e) {
            console.error('Failed to parse yield data', e);
            return;
        }

        const labels = [];
        const plannedValues = [];
        const actualValues = [];

        // Prepare data for chart (limit to top 8 for readability)
        const limitedData = yieldData.slice(0, 8);
        for (let i = 0; i < limitedData.length; i++) {
            labels.push(limitedData[i].project_name);
            plannedValues.push(limitedData[i].planned_yield);
            actualValues.push(limitedData[i].actual_yield);
        }

        // Create chart
        new Chart(chartElement, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: _t('Planned Yield'),
                        data: plannedValues,
                        backgroundColor: 'rgba(75, 192, 192, 0.7)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 1
                    },
                    {
                        label: _t('Actual Yield'),
                        data: actualValues,
                        backgroundColor: 'rgba(255, 206, 86, 0.7)',
                        borderColor: 'rgba(255, 206, 86, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    /**
     * Initialize Irrigation Chart
     */
    initIrrigationChart() {
        const chartElement = this.el.querySelector('#irrigationChart');
        if (!chartElement) return;

        let irrigationData;
        try {
            irrigationData = JSON.parse(chartElement.dataset.irrigation || '[]');
        } catch (e) {
            console.error('Failed to parse irrigation data', e);
            return;
        }

        const labels = [];
        const durationValues = [];
        const countValues = [];

        // Prepare data for chart
        for (let i = 0; i < irrigationData.length; i++) {
            labels.push(irrigationData[i].project_name);
            durationValues.push(irrigationData[i].total_irrigation_hours);
            countValues.push(irrigationData[i].irrigation_count);
        }

        // Create chart
        new Chart(chartElement, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: _t('Total Hours'),
                        data: durationValues,
                        backgroundColor: 'rgba(54, 162, 235, 0.7)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1,
                        yAxisID: 'y'
                    },
                    {
                        label: _t('Number of Irrigations'),
                        data: countValues,
                        backgroundColor: 'rgba(153, 102, 255, 0.7)',
                        borderColor: 'rgba(153, 102, 255, 1)',
                        borderWidth: 1,
                        yAxisID: 'y1',
                        type: 'line'
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: _t('Hours')
                        }
                    },
                    y1: {
                        beginAtZero: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: _t('Count')
                        },
                        grid: {
                            drawOnChartArea: false
                        }
                    }
                }
            }
        });
    }

    /**
     * Initialize Resource Category Chart
     */
    initResourceCategoryChart() {
        const chartElement = this.el.querySelector('#resourceCategoryChart');
        if (!chartElement) return;

        let resourceData;
        try {
            resourceData = JSON.parse(chartElement.dataset.resources || '{}');
        } catch (e) {
            console.error('Failed to parse resource data', e);
            return;
        }

        const labels = [];
        const data = [];
        const backgroundColor = [
            'rgba(75, 192, 192, 0.7)',
            'rgba(255, 159, 64, 0.7)',
            'rgba(255, 99, 132, 0.7)',
            'rgba(54, 162, 235, 0.7)',
            'rgba(255, 206, 86, 0.7)',
            'rgba(153, 102, 255, 0.7)',
            'rgba(201, 203, 207, 0.7)'
        ];

        // Prepare data for chart
        for (const category in resourceData) {
            labels.push(category);
            data.push(resourceData[category]);
        }

        // Create chart
        new Chart(chartElement, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: backgroundColor,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'right'
                    }
                }
            }
        });
    }

    /**
     * Initialize Resource Product Chart
     */
    initResourceProductChart() {
        const chartElement = this.el.querySelector('#resourceProductChart');
        if (!chartElement) return;

        let productData;
        try {
            productData = JSON.parse(chartElement.dataset.products || '{}');
        } catch (e) {
            console.error('Failed to parse product data', e);
            return;
        }

        // Sort products by quantity and get top 10
        const sortedProducts = Object.keys(productData)
            .map(function(key) {
                return { name: key, quantity: productData[key] };
            })
            .sort(function(a, b) {
                return b.quantity - a.quantity;
            })
            .slice(0, 10);

        const labels = [];
        const data = [];
        const backgroundColor = 'rgba(54, 162, 235, 0.7)';
        const borderColor = 'rgba(54, 162, 235, 1)';

        // Prepare data for chart
        for (let i = 0; i < sortedProducts.length; i++) {
            labels.push(sortedProducts[i].name);
            data.push(sortedProducts[i].quantity);
        }

        // Create chart
        new Chart(chartElement, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: _t('Quantity Used'),
                    data: data,
                    backgroundColor: backgroundColor,
                    borderColor: borderColor,
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: {
                    legend: {
                        position: 'top'
                    }
                }
            }
        });
    }

    /**
     * Helper to get translated cost type labels
     */
    getCostTypeLabel(costType) {
        const labels = {
            'seeds': _t('Seeds/Seedlings'),
            'fertilizer': _t('Fertilizers'),
            'pesticide': _t('Pesticides'),
            'herbicide': _t('Herbicides'),
            'water': _t('Irrigation Water'),
            'labor': _t('Labor/Workforce'),
            'machinery': _t('Machinery/Equipment'),
            'rent': _t('Land Rent'),
            'fuel': _t('Fuel'),
            'maintenance': _t('Maintenance'),
            'services': _t('Services'),
            'transportation': _t('Transportation'),
            'storage': _t('Storage'),
            'certification': _t('Certification'),
            'testing': _t('Laboratory Testing'),
            'other': _t('Other')
        };
        return labels[costType] || costType;
    }
}

// Register our custom renderer for farm.dashboard form views
registry.category("views").add("farm_dashboard_form", {
    ...formView,
    Renderer: FarmDashboardRenderer,
});
