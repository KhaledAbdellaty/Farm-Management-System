/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

/**
 * Extremely minimal Farm Dashboard Widget
 * For debugging purposes
 */
class FarmDashboardWidget extends Component {
    setup() {
        // Do nothing - keep it extremely minimal
    }
}

// Define template and props
FarmDashboardWidget.template = "farm_management.FarmDashboardWidget";
FarmDashboardWidget.props = standardFieldProps;

// Register the field widget
registry.category("fields").add("farm_dashboard_widget", FarmDashboardWidget);

export default FarmDashboardWidget;
