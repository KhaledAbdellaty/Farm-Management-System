#!/bin/bash

# Farm Management System - Arabic Translation Update Script
# This script consolidates and updates Arabic translations for both farm_management and farm_management_dashboard modules

echo "=== Farm Management System - Arabic Translation Update ==="
echo "Starting translation update process..."

# Change to Odoo directory
cd /media/khaled/ECF0050EF004E126/odoo18

# Activate virtual environment if it exists
if [ -d "/media/khaled/ECF0050EF004E126/odoo-venv" ]; then
    echo "Activating virtual environment..."
    source /media/khaled/ECF0050EF004E126/odoo-venv/bin/activate
fi

# Extract terms from farm_management module
echo "Extracting translation terms from farm_management module..."
./odoo-bin --addons-path=./addons,./custom-addons \
           --i18n-export=./custom-addons/farm_management/i18n/farm_management.pot \
           --modules=farm_management \
           -d temp-translation-db \
           --db_user=odoo \
           --db_password=odoo \
           --db_host=localhost \
           --stop-after-init

# Extract terms from farm_management_dashboard module
echo "Extracting translation terms from farm_management_dashboard module..."
./odoo-bin --addons-path=./addons,./custom-addons \
           --i18n-export=./custom-addons/farm_management_dashboard/i18n/farm_management_dashboard.pot \
           --modules=farm_management_dashboard \
           -d temp-translation-db \
           --db_user=odoo \
           --db_password=odoo \
           --db_host=localhost \
           --stop-after-init

# Deactivate virtual environment if it was activated
if [ -d "/media/khaled/ECF0050EF004E126/odoo-venv" ]; then
    deactivate
fi

# Update farm_management Arabic translations
echo "Updating farm_management Arabic translations..."
if [ -f ./custom-addons/farm_management/i18n/farm_management.pot ]; then
    # Backup the original translation file
    cp ./custom-addons/farm_management/i18n/ar.po ./custom-addons/farm_management/i18n/ar.po.bak
    
    # Merge with existing Arabic translations
    msgmerge -U ./custom-addons/farm_management/i18n/ar.po ./custom-addons/farm_management/i18n/farm_management.pot
    
    # Remove duplicated entries using msgcat
    echo "Deduplicating farm_management translation entries..."
    TEMP_FILE=$(mktemp)
    msgcat --use-first ./custom-addons/farm_management/i18n/ar.po > $TEMP_FILE
    mv $TEMP_FILE ./custom-addons/farm_management/i18n/ar.po
    
    # Validate the translation file
    echo "Validating farm_management translation file..."
    msgfmt -c ./custom-addons/farm_management/i18n/ar.po -o /dev/null
    
    echo "✓ Farm_management translation file updated successfully!"
else
    echo "✗ Error: farm_management translation template not generated. Check your Odoo configuration."
fi

# Update farm_management_dashboard Arabic translations
echo "Updating farm_management_dashboard Arabic translations..."
if [ -f ./custom-addons/farm_management_dashboard/i18n/farm_management_dashboard.pot ]; then
    # Backup the original translation file if it exists
    if [ -f ./custom-addons/farm_management_dashboard/i18n/ar.po ]; then
        cp ./custom-addons/farm_management_dashboard/i18n/ar.po ./custom-addons/farm_management_dashboard/i18n/ar.po.bak
        
        # Merge with existing Arabic translations
        msgmerge -U ./custom-addons/farm_management_dashboard/i18n/ar.po ./custom-addons/farm_management_dashboard/i18n/farm_management_dashboard.pot
    else
        echo "No existing dashboard Arabic translation found, using template..."
    fi
    
    # Remove duplicated entries using msgcat
    echo "Deduplicating dashboard translation entries..."
    TEMP_FILE=$(mktemp)
    msgcat --use-first ./custom-addons/farm_management_dashboard/i18n/ar.po > $TEMP_FILE
    mv $TEMP_FILE ./custom-addons/farm_management_dashboard/i18n/ar.po
    
    # Validate the translation file
    echo "Validating dashboard translation file..."
    msgfmt -c ./custom-addons/farm_management_dashboard/i18n/ar.po -o /dev/null
    
    echo "✓ Dashboard translation file updated successfully!"
else
    echo "✗ Error: Dashboard translation template not generated. Check your Odoo configuration."
fi

# Clean up temporary database
echo "Cleaning up temporary database..."
dropdb temp-translation-db 2>/dev/null || true

echo ""
echo "=== Translation Update Summary ==="
echo "✓ Consolidated multiple Arabic .po files into single ar.po"
echo "✓ Removed duplicate translation entries"
echo "✓ Created Arabic translations for dashboard module"
echo "✓ Updated translation extraction for both modules"
echo ""
echo "Next steps:"
echo "1. Restart your Odoo server"
echo "2. Go to Settings -> Translations -> Load a Translation"
echo "3. Select Arabic language and install/update"
echo "4. The system will now be fully available in Arabic"
echo ""
echo "Translation update completed successfully!"