/** @odoo-module alias=farm_management/js/dashboard_loader */

/**
 * This file serves as the main entry point for the farm dashboard component.
 * It ensures all dependencies are properly loaded and registered.
 */

import { registry } from "@web/core/registry";
import { FarmDashboardComponent } from "@farm_management/components/farm_dashboard";

// Register the dashboard component as a client action
registry.category("actions").add("farm_management.dashboard", FarmDashboardComponent);
