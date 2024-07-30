# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import json


class ShopifyWebhook(models.Model):
    _name = "shopify.webhook"
    _description = 'Shopify Webhook'
    _rec_name = "name"

    name = fields.Char(string='Name', translate=True)
    webhook_id = fields.Char(string='Webhook ID')
    base_url = fields.Char(string="Base URL")

    state = fields.Selection([('active', 'Active'), ('disabled', 'Disabled'), ('paused', 'Paused')], default='disabled',
                             string="Hook State")
    operations = fields.Selection([('customers/create', 'Customer Create'),
                                   ('customers/update', 'Customer Update'),
                                   ('customers/delete', 'Customer Delete'),
                                   ('products/create', 'Product Create'),
                                   ('products/update', 'Product Update'),
                                   ('products/delete', 'Product Delete'),
                                   ('orders/create', 'Order Create'),
                                   ('orders/updated', 'Order Update')], default='orders/create', string="Operations")
    shopify_instance_id = fields.Many2one('shopify.connector', string='Shopify Instance', ondelete="cascade")

    @api.model_create_multi
    def create(self, vals_list):
        """
            Override create method to prevent duplicate webhooks and create Shopify webhook details.
            :param vals_list: List of dictionaries containing values for new records.
            :raises: ValidationError if a webhook with the same operations and instance exists.
            :return: Created record.
        """
        for vals in vals_list:
            existing_webhook_id = self.search(
                [('shopify_instance_id', '=', vals.get('shopify_instance_id')),
                 ('operations', '=', vals.get('operations'))], limit=1)
            if existing_webhook_id:
                raise ValidationError(_('Webhook is already created with the same operations.'))
        res = super(ShopifyWebhook, self).create(vals_list)
        res.create_webhook_details()
        return res

    def create_webhook_details(self):
        """
        Create Shopify webhook details by sending a POST request to Shopify.
        :return: True if successful.
        :raises: ValidationError if HTTP protocol is not HTTPS.
        """
        shopify_connection = self.env['shopify.connector']
        for record in self:
            try:
                shopify_instance_id = record.shopify_instance_id
                if shopify_instance_id.state != "integrated":
                    raise ValidationError("Shopify instance is not connected. Please connect Shopify instance first.")

                # base_url = 'https://64e8-150-129-104-231.ngrok-free.app'
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                operations = record.shopify_operation_url_hook()
                url = base_url + operations
                if url[:url.find(":")] == 'http':
                    raise ValidationError("Address protocol http:// is not supported for creating the webhooks. "
                                          "Only instances having SSL connection https:// are permitted.")
                headers = {
                    'X-Shopify-Access-Token': shopify_instance_id.shopify_access_token,
                    'Content-Type': 'application/json'
                }
                payload = json.dumps({
                    "webhook": {
                        "address": url,
                        "topic": record.operations,
                        "format": "json"
                    }
                })
                shopify_url = record.truncate_shopify_store_url_webhook(shopify_instance_id.shopify_host, shopify_instance_id)
                response = requests.post(shopify_url, headers=headers, data=payload)
                if response.status_code == 201:
                    response_data = response.json()
                    webhook_id = response_data["webhook"]['id']
                    record.write({"webhook_id": webhook_id, 'base_url': url, 'state': 'active'})
                    log_id = shopify_connection._create_common_process_log( f"Successfully created { record.operations} webhook from Shopify.", "shopify.webhook", record, response_data)
                    log_line_id = shopify_connection._create_common_process_log_line(log_id,  record.operations, record, response_data, f"Successfully created webhook from Shopify.", 'success')
                else:
                    error_message = f"Failed to create  { record.operations} Shopify Webhook. Status code: {response.status_code}."
                    log_id = shopify_connection._create_common_process_log(error_message, "shopify.webhook", record, response.text)
                    log_line_id = shopify_connection._create_common_process_log_line(log_id, record.operations, record, response.text, error_message, 'error')

            except ValidationError as ve:
                log_id = shopify_connection._create_common_process_log("Validation Error occurred.", "shopify.webhook", record, str(ve))
                log_line_id = shopify_connection._create_common_process_log_line(log_id, record.operations, record, str(ve), "Validation Error occurred.", 'error')


            except Exception as e:
                error_message = f"Error occurred: {str(e)}"
                log_id = shopify_connection._create_common_process_log(error_message, "shopify.webhook", record, str(e))
                log_line_id = shopify_connection._create_common_process_log_line(log_id, record.operations, record, str(e), error_message, 'error')


    def shopify_operation_url_hook(self):
        """
            Get the corresponding route for the Shopify webhook operations.
            :return: Route based on the selected operation.
        """
        operations = self.operations
        route = ""
        if operations == 'orders/create':
            route += "/rcs_shopify_order_create_hook"
        elif operations == 'orders/updated':
            route += "/rcs_shopify_order_update_hook"
        elif operations == 'customers/create':
            route += "/rcs_shopify_customer_create_hook"
        elif operations == 'customers/delete':
            route += "/rcs_shopify_customer_delete_hook"
        elif operations == 'customers/update':
            route += "/rcs_shopify_customer_update_hook"
        elif operations == 'products/create':
            route += "/rcs_shopify_product_create_hook"
        elif operations == 'products/update':
            route += "/rcs_shopify_product_update_hook"
        elif operations == 'products/delete':
            route += "/rcs_shopify_product_delete_hook"
        return route

    @api.model
    def unlink(self):
        """
            Override unlink method to delete Shopify webhook from Shopify store.
            :return: Super call to parent unlink method.
            :raises: ValidationError if something went wrong during webhook deletion.
        """
        shopify_connection = self.env['shopify.connector']
        connector_obj = self.env['shopify.operations.wizard']
        for record in self:
            if record.webhook_id:
                shopify_instance_id = record.shopify_instance_id
                url = record.delete_shopify_store_url_webhook(shopify_instance_id.shopify_host, shopify_instance_id)
                headers = {
                    'X-Shopify-Access-Token': shopify_instance_id.shopify_access_token
                }
                try:
                    response = requests.request("DELETE", url, headers=headers)
                    # Check response status for success
                    if response.status_code == 200:
                        response_data = response.json()
                        log_id = shopify_connection._create_common_process_log(f"Successfully deleted {record.operations} webhook from Shopify.", "shopify.webhook", record, response_data)
                        log_line_id = shopify_connection._create_common_process_log_line(log_id, record.operations, record, response_data, f"Successfully deleted webhook from Shopify.", 'success')
                        return super(ShopifyWebhook, self).unlink()
                    else:
                        raise ValidationError(
                            f'Failed to delete the webhook.{response.text} HTTP Status Code: {response.status_code}')

                except Exception as e:
                    log_id = shopify_connection._create_common_process_log(f'Something went wrong while deleting the webhook {record.operations}', "shopify.webhook", record, str(e))
                    log_line_id = shopify_connection._create_common_process_log_line(log_id, record.operations, record, response.text, 'Something went wrong while deleting the webhook', 'error')
                    self._cr.commit()
                    raise ValidationError(
                        f'Something went wrong while deleting the webhook: {e}')
            else:
                return super(ShopifyWebhook, self).unlink()

    def truncate_shopify_store_url_webhook(self, shopify_host, shopify_instance_id):
        """
            Generate Shopify webhook URL for creation.
            :param shopify_host: Shopify store host URL.
            :param shopify_instance_id: Shopify instance ID.
            :return: Constructed Shopify webhook URL.
        """
        shop = shopify_host.split("//")
        if len(shop) == 2:
            shop_url = shop[0] + "//" + shop[1] + "/admin/api/" + shopify_instance_id.version_control + "/webhooks.json"
        else:
            shop_url = "https://" + shop[0] + "/admin/api/" + shopify_instance_id.version_control + "/webhooks.json"
        return shop_url

    def delete_shopify_store_url_webhook(self, shopify_host, shopify_instance_id):
        """
            Generate Shopify webhook deletion URL.
            :param shopify_host: Shopify store host URL.
            :param shopify_instance_id: Shopify instance ID.
            :return: Constructed Shopify webhook deletion URL.
        """
        shop = shopify_host.split("//")
        if len(shop) == 2:
            shop_url = shop[0] + "//" + shop[1] + "/admin/api/" + shopify_instance_id.version_control + "/webhooks/" + self.webhook_id + ".json"
        else:
            shop_url = "https://" + shop[0] + "/admin/api/" + shopify_instance_id.version_control + "/webhooks/" + self.webhook_id + ".json"
        return shop_url
