#!/bin/bash

# Change to Odoo directory
cd /media/khaled/ECF0050EF004E126/odoo18

# Extract terms from source code and templates
echo "Extracting translation terms..."
source /media/khaled/ECF0050EF004E126/odoo-venv/bin/activate
./odoo-bin --addons-path=./addons,./custom-addons \
           --i18n-export=./custom-addons/farm_management/i18n/farm_management.pot \
           --modules=farm_management \
           -d new-db \
           --db_user=odoo \
           --db_password=odoo \
           --db_host=localhost

deactivate

# Merge with existing Arabic translations
echo "Updating Arabic translations..."
if [ -f ./custom-addons/farm_management/i18n/farm_management.pot ]; then
    # Backup the original translation file
    cp ./custom-addons/farm_management/i18n/ar.po ./custom-addons/farm_management/i18n/ar.po.bak
    
    # Create a merged translation file
    msgmerge -U ./custom-addons/farm_management/i18n/ar.po ./custom-addons/farm_management/i18n/farm_management.pot
    
    # Create a temporary file to store deduplicated translations
    TEMP_FILE=$(mktemp)
    
    # Remove duplicated entries using msgcat
    echo "Deduplicating translation entries..."
    msgcat --use-first ./custom-addons/farm_management/i18n/ar.po > $TEMP_FILE
    
    # Replace the original file with the deduplicated version
    mv $TEMP_FILE ./custom-addons/farm_management/i18n/ar.po
    
    # Validate the translation file
    echo "Validating translation file..."
    msgfmt -c ./custom-addons/farm_management/i18n/ar.po -o /dev/null
    
    echo "Translation file updated and deduplicated successfully!"
else
    echo "Error: Translation template not generated. Check your Odoo configuration."
fi

echo "Done! Now restart your Odoo server and use Settings -> Translations -> Load a Translation to apply the Arabic language."
