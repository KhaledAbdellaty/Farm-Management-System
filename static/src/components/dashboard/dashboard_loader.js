/** @odoo-module */

import { registry } from "@web/core/registry";
import { FarmDashboard } from "./farm_dashboard";

// Register the farm dashboard as a client action
registry.category("actions").add("farm_management.dashboard", FarmDashboard);
