# -*- coding: utf-8 -*-
import requests
import json
import logging
from odoo import models, fields, api, _

_LOGGER = logging.getLogger(">>> Shopify Import Product <<<")


class ProductProduct(models.Model):
    _inherit = "product.product"
    _description = "Product Variant"

    shopify_variant_id = fields.Char(string='Shopify Variant ID')
    is_shopify_product = fields.Boolean(string="Is Shopify Product", default=False)
    shopify_instance_id = fields.Many2one('shopify.connector', string='Shopify Instance', tracking=True)
    inventory_item_id = fields.Char(String="Inventory item ID")

    def export_shopify_product(self, url, instance_id):
        """
            Export product stock information to Shopify.

            :param url: Shopify API endpoint URL for stock update.
            :param instance_id: Shopify Instance record containing Shopify access details.
            :return: Notification message indicating the success or failure of the export process.
        """
        shopify_connection = self.env['shopify.connector']
        # Assuming `self` is a recordset of `ProductProduct` instances
        connector_obj = self.env['shopify.operations.wizard']
        headers = {
            'X-Shopify-Access-Token': instance_id.shopify_access_token,
            'Content-Type': 'application/json'
        }
        # Filter products by shopify_instance_id
        products_to_export = self.search([('shopify_instance_id', '=', instance_id.id)])
        export_stock = []
        log_id = shopify_connection._create_common_process_log("Successfully exported stock to Shopify.", "product.product")
        _LOGGER.info("Starting stock export to Shopify for %d products.", len(products_to_export))
        for product in products_to_export:
            try:
                # Query stock.quant to get the available quantity for the product
                quants = self.env['stock.quant'].sudo().search([
                    ('product_id', '=', product.id),
                    ('location_id', '=', instance_id.location_id.id)  # Adjust location filter as per your setup
                ])
                # Calculate total available quantity from all quants
                total_available_qty = sum(quant.quantity for quant in quants)

                # Fetch location ID from Shopify instance (assuming you have the correct setup)
                location_id = product.shopify_instance_id.location_id.shopify_location_id

                # Prepare payload with inventory item ID and updated stock quantity
                payload = {
                    "location_id": location_id,
                    "inventory_item_id": product.inventory_item_id,
                    "available": int(total_available_qty)  # Convert to integer if needed
                }
                payload_json = json.dumps(payload)
                response = requests.post(url, headers=headers, data=payload_json)
                if response.status_code == 200:
                    response_data = response.json()
                    export_stock.append(response_data)
                    _LOGGER.info("Successfully exported stock for product '%s' to Shopify.", product.name)
                    log_line_id = shopify_connection._create_common_process_log_line(log_id, product.name, product,payload_json, f"Successfully imported {product.name} customer from Shopify.", 'success')
                else:
                    _LOGGER.error("Failed to export stock for product '%s'. HTTP Error: %d", product.name, response.status_code)
                    log_line_id = shopify_connection._create_common_process_log_line(log_id, product.name, product, payload_json, f"Failed to export stock. HTTP Error: {response.status_code}", 'error')

            except Exception as e:
                _LOGGER.error("Exception occurred while exporting stock for product '%s': %s", product.name, str(e), exc_info=True)
                log_line_id = shopify_connection._create_common_process_log_line(log_id, product.name, product, str(e), "Failed to export stock.", 'error')

        notification = connector_obj._create_notification('Success', 'Export stock Process Completed', 'success')
        _LOGGER.info("Stock export process completed with %d products processed.", len(products_to_export))
        return notification
