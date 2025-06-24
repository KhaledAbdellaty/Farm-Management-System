# Farm Management System for Odoo 18

A comprehensive Farm Management System that integrates with Odoo 18's Inventory, Accounting, and Project Management modules.

## Features

- **Farm & Field Management**: Track farm properties, fields, soil conditions, and field status
- **Crop Planning**: Manage crop information, growing conditions, and yield projections
- **Cultivation Projects**: Plan and execute cultivation projects with stage tracking
- **Input Management**: Define bills of materials for crop inputs and resources
- **Daily Operations**: Record and track daily farming activities
- **Cost Analysis**: Track and analyze farming costs by project, farm, field, or cost type
- **Integration**: Seamlessly works with Odoo Inventory, Accounting, and Project modules
- **Multilingual Support**: Full Arabic translation included

## Requirements

- Odoo 18
- Depends on: stock, account, analytic, project, hr_timesheet, web modules

## Installation

1. Clone this repository into your Odoo addons directory:
   ```bash
   git clone https://github.com/KhaledAbdellaty/farm_management /path/to/odoo/custom-addons/
   ```

2. Update your Odoo configuration file to include this path in the addons_path

3. Restart Odoo server and update the app list

4. Install the "Farm Management System" module from the Apps menu

## Usage

### Farm Management
- Create and manage farms with location details, area, and ownership information
- Organize farms into fields with details on soil type, field status, and crop history

### Crop Planning
- Define crops with growing requirements, seasons, and expected yields
- Create Bills of Materials (BOMs) for crop inputs with planned quantities and timing

### Cultivation Projects  
- Plan and track cultivation projects through stages from preparation to harvest
- Monitor project progress, costs, and yields

### Daily Operations
- Record daily farming activities with weather conditions and observations
- Track resource usage and costs for every operation

### Financial Management
- Analyze costs by project, crop, field, farm, or cost type
- Track budgeted vs. actual costs and calculate profitability

## License

LGPL-3

## Support

For support, contact your Odoo partner or open an issue on the GitHub repository.

## Credits

Developed by KhaledAbdellaty.
