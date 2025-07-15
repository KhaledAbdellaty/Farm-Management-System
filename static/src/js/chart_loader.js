/** @odoo-module alias=farm_management/js/chart_loader */

/**
 * This file initializes Chart.js and ensures it's available to the application.
 * It must be loaded before any component that uses Chart.js.
 */

// Import required modules
import { loadJS } from "@web/core/assets";

// Define promises outside any function to make them available throughout the module
const chartJsPromise = (function() {
    // Try to use the global instance or load it
    if (window.Chart) {
        console.log("Chart.js already loaded in window object");
        return Promise.resolve(window.Chart);
    } else {
        console.warn("Chart.js not found in window object, attempting to load it");
        return loadJS("/farm_management/static/vendor/chart.min.js").then(() => {
            if (!window.Chart) {
                throw new Error("Chart.js loaded but not available in window.Chart");
            }
            return window.Chart;
        });
    }
})();

// Do the same for moment.js
const momentJsPromise = (function() {
    if (window.moment) {
        console.log("moment.js already loaded in window object");
        return Promise.resolve(window.moment);
    } else {
        console.warn("moment.js not found in window object, attempting to load it");
        return loadJS("/farm_management/static/vendor/moment.min.js").then(() => {
            if (!window.moment) {
                throw new Error("moment.js loaded but not available in window.moment");
            }
            return window.moment;
        });
    }
})();

/**
 * Get the Chart.js library
 * @returns {Promise<any>} Resolves when Chart.js is loaded
 */
export async function getChartJS() {
    try {
        await Promise.all([chartJsPromise, momentJsPromise]);
        
        if (!window.Chart) {
            console.error("Chart.js failed to load properly!");
            throw new Error("Chart.js not available");
        }
        
        console.log("Chart.js successfully loaded and ready to use:", window.Chart.version);
        return window.Chart;
    } catch (error) {
        console.error("Error in getChartJS:", error);
        throw error;
    }
}

// Log when Chart.js is ready (outside the exported function)
chartJsPromise
    .then(() => {
        if (window.Chart) {
            console.log("Chart.js loaded successfully:", window.Chart.version);
        } else {
            console.error("Chart.js failed to load!");
        }
    })
    .catch(error => {
        console.error("Error loading Chart.js:", error);
    });

// Export a simple check function to see if the module loaded correctly
export function isChartLoaderWorking() {
    return "Chart loader module loaded successfully";
}
