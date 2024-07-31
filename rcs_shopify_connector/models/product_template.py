# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools.misc import split_every
import requests
import base64
import logging

_logger = logging.getLogger(">>> Shopify Import Products <<<")


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Fields related to Shopify integration
    shopify_product_id = fields.Char(string='Shopify Product ID', tracking=True)
    is_shopify_product = fields.Boolean(string="Is Shopify Product", default=False)
    shopify_instance_id = fields.Many2one('shopify.connector', string='Shopify Instance', tracking=True)
    inventory_item_id = fields.Char(String="Inventory item ID", compute='_compute_inventory', inverse='_set_inventory')
    log_count = fields.Integer(string='Product Logs', compute='_get_product_logs')

    @api.depends('product_variant_ids.inventory_item_id')
    def _compute_inventory(self):
        """Compute method for inventory_item_id field."""
        self._compute_template_field_from_variant_field('inventory_item_id')

    def _set_inventory(self):
        """Inverse method for inventory_item_id field."""
        self._set_product_variant_field('inventory_item_id')

    @api.depends('shopify_product_id')
    def _get_product_logs(self):
        """
            Update the log_count field based on the number of related logs for each record.
        """
        process_log = self.env['common.process.log']
        for rec in self:
            log_count = process_log._get_log_count(rec.id, 'product.template', rec.company_id.id, "shopify_connector")
            rec.log_count = len(log_count)

    def open_product_logs(self):
        """
            Opens product logs related to the current product template.
            :return: Action dictionary to open product logs.
        """
        process_log = self.env['common.process.log']
        log_ids = process_log._get_log_count(self.id, 'product.template', self.company_id.id, "shopify_connector")
        return process_log._open_logs_action(log_ids)

    @api.model
    def archive_by_shopify_product_id(self, shopify_product_id, instance_id):
        """
            Archive products based on Shopify Product ID.
            :param shopify_product_id: Dictionary containing 'id' key with Shopify Product ID.
            :param instance_id: Shopify instance ID to filter products.
            :return: True if archived successfully, False otherwise.
        """
        product_id = shopify_product_id.get('id')
        _logger.info("Attempting to archive product with Shopify Product ID: %s", product_id)
        products = self.search(
            [('shopify_product_id', '=', product_id), ('shopify_instance_id', '=', instance_id.id)])
        if products:
            products.write({'active': False})
            _logger.info("Successfully archived product(s) with Shopify Product ID: %s", product_id)
            return True
        _logger.info("No products found to archive with Shopify Product ID: %s", product_id)
        return False

    def _get_image_from_url(self, url):
        """
            Fetches image from given URL and returns base64 encoded image data.
            :param url: URL of the image.
            :return: Base64 encoded image data if successful, False otherwise.
        """
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return base64.b64encode(response.content)
            else:
                return False
        except requests.RequestException:
            return False

    def _get_or_create_attribute(self, attribute_name):
        """
            Retrieves or creates a product attribute based on Shopify attribute ID.
            :param attribute_name: Name of the attribute.
            :param shopify_attribute_id: Shopify attribute ID.
            :return: Existing or newly created product.attribute record.
        """
        attribute_obj = self.env['product.attribute']
        attribute = attribute_obj.search([('name', '=', attribute_name), ('is_shopify_attribute', '=', True)], limit=1)
        if not attribute:
            attribute = attribute_obj.create({'name': attribute_name,
                                              'is_shopify_attribute': True})
        return attribute

    def _get_or_create_attribute_value(self, attribute, value_name):
        """
            Retrieves or creates a product attribute value.
            :param attribute: product.attribute record.
            :param value_name: Name of the attribute value.
            :return: Existing or newly created product.attribute.value record.
        """
        attribute_value_obj = self.env['product.attribute.value']
        attribute_value = attribute_value_obj.search([('name', '=', value_name), ('attribute_id', '=', attribute.id)], limit=1)
        if not attribute_value:
            attribute_value = attribute_value_obj.create({'name': value_name, 'attribute_id': attribute.id})
        return attribute_value

    def _get_or_create_category(self, product_type):
        """
           Retrieves or creates a product category based on Shopify product type.
           :param product_type: Shopify product type (category name).
           :return: Existing or newly created product.category record.
        """
        category_obj = self.env['product.category']
        category_value = category_obj.search([('name', '=', product_type), ('is_shopify_category', '=', True)], limit=1)
        if not category_value:
            category_value = category_obj.create({'name': product_type, 'is_shopify_category': True})
        return category_value

    def _create_or_update_product(self, product_data, instance_id):
        """
            Creates or updates a product template and its variants based on Shopify product data.
            :param product_data: Dictionary containing Shopify product information.
            :param instance_id: Shopify instance ID.
            :return: Created or updated product.template record.
        """
        shopify_connection = self.env['shopify.connector']
        image_data = None
        try:
            if product_data.get('image') and product_data.get('image').get('src'):
                _logger.info("Fetching image from URL: %s", product_data['image']['src'])
                image_data = self._get_image_from_url(product_data['image']['src'])

            product_category = False
            if product_data.get('product_type'):
                _logger.info("Getting or creating category: %s", product_data.get('product_type'))
                product_category = self._get_or_create_category(product_data.get('product_type')).id

            variation_attributes_lst = []
            # Collect option names from product data
            option_name_lst = [options.get("name") for options in product_data.get("options", []) if options.get("name")]

            # Collect attribute lines
            attribute_lines = {}
            for variant in product_data.get('variants', []):
                variant_id = variant.get("id")
                variant_barcode = variant.get("barcode")
                variant_weight = variant.get("weight")
                weight_unit = variant.get('weight_unit')
                inventory_item_id = variant.get('inventory_item_id')
                variant_dict = {"variant_id": variant_id,
                                "barcode": variant_barcode,
                                "weight": variant_weight,
                                "weight_unit": weight_unit,
                                "inventory_item_id": inventory_item_id}
                # Map options to their corresponding names
                if len(option_name_lst) > 0 and variant.get("option1"):
                    variant_dict[option_name_lst[0]] = variant.get("option1")
                if len(option_name_lst) > 1 and variant.get("option2"):
                    variant_dict[option_name_lst[1]] = variant.get("option2")
                if len(option_name_lst) > 2 and variant.get("option3"):
                    variant_dict[option_name_lst[2]] = variant.get("option3")
                variation_attributes_lst.append(variant_dict)

                for option in ['option1', 'option2', 'option3']:
                    attribute_value_name = variant.get(option)
                    if attribute_value_name:
                        attribute_index = int(option[-1]) - 1
                        if attribute_index < len(product_data['options']):
                            attribute_name = product_data['options'][attribute_index]['name']
                            shopify_attribute_id = product_data['options'][attribute_index]['id']
                            attribute = self._get_or_create_attribute(attribute_name)
                            attribute_value = self._get_or_create_attribute_value(attribute, attribute_value_name)

                            if attribute.id not in attribute_lines:
                                attribute_lines[attribute.id] = {
                                    'attribute_id': attribute.id,
                                    'value_ids': []
                                }
                            if attribute_value.id not in attribute_lines[attribute.id]['value_ids']:
                                attribute_lines[attribute.id]['value_ids'].append(attribute_value.id)

            # Searching for existing product template
            _logger.info("Searching for existing product template.")
            product_tmpl = self.search(
                [('shopify_instance_id', '=', instance_id.id),
                 ('shopify_product_id', '=', product_data['id'])],
                limit=1)

            # Attribute line values to be updated or created
            existing_attribute_lines = {}
            if product_tmpl:
                _logger.info("Found existing product template: %s", product_tmpl.name)
                for line in product_tmpl.attribute_line_ids:
                    existing_attribute_lines[line.attribute_id.id] = line.value_ids.ids

            new_attribute_lines = []
            for attr_id, line_data in attribute_lines.items():
                if attr_id in existing_attribute_lines:
                    existing_value_ids = set(existing_attribute_lines[attr_id])
                    new_value_ids = set(line_data['value_ids'])
                    if not new_value_ids.issubset(existing_value_ids):
                        combined_value_ids = list(existing_value_ids.union(new_value_ids))
                        new_attribute_lines.append(
                            (1, product_tmpl.attribute_line_ids.filtered(lambda l: l.attribute_id.id == attr_id).id, {
                                'value_ids': [(6, 0, combined_value_ids)]}))
                else:
                    new_attribute_lines.append((0, 0, {
                        'attribute_id': attr_id,
                        'value_ids': [(6, 0, line_data['value_ids'])]
                    }))

            product_vals = {
                'name': product_data['title'],
                'image_1920': image_data,
                'shopify_product_id': product_data['id'],
                'shopify_instance_id': instance_id.id,
                'attribute_line_ids': new_attribute_lines,
                'categ_id': product_category,
                'type': 'product',
                'is_shopify_product': True
            }

            if product_tmpl:
                _logger.info("Updating existing product template: %s", product_tmpl.name)
                product_tmpl.write(product_vals)
            else:
                _logger.info("Creating new product template: %s", product_data['title'])
                product_tmpl = self.create(product_vals)

            log_id = shopify_connection._create_common_process_log(f"Successfully imported {product_data['title']} Product from Shopify.",
                                                                   "product.template", product_tmpl, product_data)
            product_variants = product_tmpl.product_variant_ids
            for variant in product_variants:
                attribute_values = variant.product_template_attribute_value_ids
                for attribute in variation_attributes_lst:
                    match = True
                    for idx, option in enumerate(option_name_lst):
                        if attribute.get(option) != variant.product_template_attribute_value_ids.filtered(lambda v: v.attribute_id.name == option).name:
                            match = False
                            break
                    if match:
                        vals = {
                            'shopify_variant_id': attribute['variant_id'],
                            'barcode': attribute['barcode'],
                            'weight': attribute['weight'],
                            'company_id': instance_id.company_id.id,
                            'is_shopify_product': True,
                            'shopify_instance_id': instance_id.id,
                            'inventory_item_id': attribute['inventory_item_id']
                        }
                        _logger.info("Updating variant '%s' with values: %s", variant.display_name, vals)
                        variant.update(vals)
                        break
                _logger.info("Successfully imported variant '%s' from Shopify.", variant.display_name)
                log_line_id = shopify_connection._create_common_process_log_line(log_id, variant.display_name, variant, product_data, f"Successfully imported {variant.display_name} customer from Shopify.", 'success')
            return product_tmpl
        except Exception as e:
            _logger.error("An error occurred while creating or updating product '%s': %s", product_data.get('title', 'Unknown'), str(e))
            log_id = shopify_connection._create_common_process_log('An error occurred while creating or updating product from Shopify', "product.template", None, str(e))
            log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', None, str(e), 'Error: Product creation or update failed.', 'error')

    def import_product(self, url, instance_id):
        """
            Imports products from Shopify API using given URL.
            :param url: Shopify API URL to fetch products.
            :param instance_id: Shopify instance ID.
            :return: Notification message.
        """
        shopify_connection = self.env['shopify.connector']
        product_tmpl_obj = self.env['product.template']
        product_id = None
        headers = {
            "X-Shopify-Access-Token": instance_id.shopify_access_token
        }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                product = response.json().get('product', [])
                products = response.json().get('products', [])
                if product:
                    try:
                        product_id = product_tmpl_obj._create_or_update_product(product, instance_id)
                        return product_id
                    except Exception as e:
                        message = 'Failed to import %s product from Shopify.' % product.get('title')
                        log_id = shopify_connection._create_common_process_log(message, "product.template", product_id, product)
                        log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', product_id, product, str(e), 'error')
                        return product_tmpl_obj
                else:
                    if products:
                        try:
                            product_queue_ids = self.create_product_data_queues(products, instance_id)
                            return product_queue_ids
                        except Exception as e:
                            message = 'Failed to import %s product from Shopify.' % product.get('title')
                            log_id = shopify_connection._create_common_process_log(message, "product.template", product_id, product)
                            log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', product_id, product, str(e), 'error')
                            return product_tmpl_obj
            else:
                log_id = shopify_connection._create_common_process_log("Failed to fetch products from Shopify", "product.template", product_id, response.text)
                log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', product_id, response.text, f"Failed to fetch products from Shopify. HTTP Error: {response.status_code}", 'error')
                return product_tmpl_obj

        except requests.RequestException as e:
            log_id = shopify_connection._create_common_process_log("An error occurred while fetching products from Shopify",
                                                                   "product.template", product_id,  str(e))
            log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', product_id,  str(e),
                                                                             f"Failed to fetch products from Shopify.", 'error')
            return product_tmpl_obj

    def create_product_data_queues(self, product_data, instance_id):
        """
            Creates product data queues for batch processing.

            :param product_data: List of Shopify product data dictionaries.
            :param instance_id: Shopify instance ID.
            :return: List of created product queue IDs.
        """
        product_queue_list = []
        product_data_queue_obj = self.env["shopify.queue"]
        product_data_queue_line_obj = self.env["shopify.queue.line"]

        if len(product_data) > 0:
            for product_id_chunk in split_every(125, product_data):
                product_queue = product_data_queue_obj.create_queue(instance_id, "product")
                product_data_queue_line_obj.shopify_create_multi_queue(product_queue, product_id_chunk, instance_id, 'product')

                product_queue_list.append(product_queue.id)
            self._cr.commit()
        return product_data_queue_obj.search([('id', 'in', product_queue_list)])