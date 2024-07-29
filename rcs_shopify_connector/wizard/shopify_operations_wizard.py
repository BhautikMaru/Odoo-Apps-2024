# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError
from datetime import datetime


class ShopifyOperationsWizard(models.TransientModel):
    _name = 'shopify.operations.wizard'
    _description = "Shopify operations perform"

    shopify_connector_id = fields.Many2one('shopify.connector')
    shopify_operations = fields.Selection(selection=[('import_customer', 'Import Customers'),
                                                     ('import_specific_customer', 'Import Specific Customer'),
                                                     ('import_product', 'Import Products'),
                                                     ("import_specific_product", "Import Specific Product-IDS"),
                                                     ('import_orders', 'Import Order'),
                                                     ('import_unshipped_orders', 'Import Unshipped Order'),
                                                     ("import_shipped_orders", "Import Shipped Orders"),
                                                     ("import_specific_order", "Import Specific Order-IDS"),
                                                     ("export_stock", "Export Stock"),
                                                     ("import_payment_gateway", "Import Payment Gateway Type")],
                                          string="Shopify Operation")
    start_date = fields.Datetime('From Date')
    end_date = fields.Datetime('To Date', default=fields.Datetime.now)
    import_specific_id = fields.Text(string="Specific Order ID", translate=True)

    @api.constrains('start_date', 'end_date', 'shopify_operations')
    def _check_to_date(self):
        for record in self:
            if record.shopify_operations in (
                    'import_unshipped_orders', 'import_shipped_orders'):
                if not record.start_date or not record.end_date:
                    raise ValidationError("Start Date or End Date is missing. Please select appropriate dates.")
                if record.start_date > record.end_date:
                    raise ValidationError("End Date must be greater than or equal to the Start Date.")

    def add_https_to_url(self, url):
        if not url.startswith('https://'):
            url = 'https://' + url
        return url

    def truncate_shopify_store_url(self, shopify_host, instance_id, resource_path):
        shop = shopify_host.split("//")
        if len(shop) == 2:
            shop_url = shop[0] + "//" + shop[
                1] + "/admin/api/" + instance_id.version_control + "/" + resource_path + ".json"
        else:
            shop_url = "https://" + shop[
                0] + "/admin/api/" + instance_id.version_control + "/" + resource_path + ".json"
        return shop_url

    def _create_notification(self, title, message, notification_type):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': notification_type,
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def shopify_perform_operations_action(self):
        self.ensure_one()
        product_tmpl_obj = self.env['product.template']
        product_obj = self.env['product.product']
        partner_obj = self.env['res.partner']
        sale_order_obj = self.env['sale.order']
        payment_gateway = self.env['shopify.payment.gateway']
        instance_id = self.shopify_connector_id
        queue_ids = []
        action_name = ""
        form_view_name = ""

        if self.shopify_operations == 'import_customer':
            url = self.truncate_shopify_store_url(self.shopify_connector_id.shopify_host, instance_id, 'customers')
            url_status = url + "?limit=250"
            customer_queue_ids = partner_obj.import_customer(url_status, instance_id)
            if customer_queue_ids:
                queue_ids = customer_queue_ids
                action_name = "rcs_shopify_connector.action_shopify_synced_customer_data"
                form_view_name = "rcs_shopify_connector.shopify_synced_data_form_view_rcs"

        elif self.shopify_operations == 'import_specific_customer':
            url = self.truncate_shopify_store_url(self.shopify_connector_id.shopify_host, instance_id, 'customers')
            url_status = f"{url}?ids={self.import_specific_id}"
            customer_queue_ids = partner_obj.import_customer(url_status, instance_id)
            if customer_queue_ids:
                queue_ids = customer_queue_ids
                action_name = "rcs_shopify_connector.action_shopify_synced_customer_data"
                form_view_name = "rcs_shopify_connector.shopify_synced_data_form_view_rcs"

        elif self.shopify_operations == 'import_product':
            url = self.truncate_shopify_store_url(self.shopify_connector_id.shopify_host, instance_id, 'products')
            url_status = url + "?limit=250"
            product_queue_ids = product_tmpl_obj.import_product(url_status, instance_id)
            if product_queue_ids:
                queue_ids = product_queue_ids
                action_name = "rcs_shopify_connector.action_shopify_synced_Product_data"
                form_view_name = "rcs_shopify_connector.shopify_synced_data_form_view_rcs"

        elif self.shopify_operations == 'import_specific_product':
            url = self.truncate_shopify_store_url(self.shopify_connector_id.shopify_host, instance_id, 'products')
            url_status = f"{url}?ids={self.import_specific_id}"
            product_queue_ids = product_tmpl_obj.import_product(url_status, instance_id)
            if product_queue_ids:
                queue_ids = product_queue_ids
                action_name = "rcs_shopify_connector.action_shopify_synced_Product_data"
                form_view_name = "rcs_shopify_connector.shopify_synced_data_form_view_rcs"

        elif self.shopify_operations == 'import_unshipped_orders':
            url = self.truncate_shopify_store_url(self.shopify_connector_id.shopify_host, instance_id, 'orders')
            start_date_iso = self.start_date.isoformat()
            end_date_iso = self.end_date.isoformat()
            url_status = f"{url}?fulfillment_status=unshipped&created_at_min={start_date_iso}&created_at_max={end_date_iso}"
            order_queue_ide = sale_order_obj.import_shopify_orders(url_status, instance_id)
            if order_queue_ide:
                queue_ids = order_queue_ide
                action_name = "rcs_shopify_connector.action_shopify_synced_sale_order_data"
                form_view_name = "rcs_shopify_connector.shopify_synced_data_form_view_rcs"

        elif self.shopify_operations == 'import_shipped_orders':
            url = self.truncate_shopify_store_url(self.shopify_connector_id.shopify_host, instance_id, 'orders')
            start_date_iso = self.start_date.isoformat()
            end_date_iso = self.end_date.isoformat()
            url_status = f"{url}?fulfillment_status=shipped&created_at_min={start_date_iso}&created_at_max={end_date_iso}"
            order_queue_shipped_ids = sale_order_obj.import_shopify_orders(url_status, instance_id)
            if order_queue_shipped_ids:
                queue_ids = order_queue_shipped_ids
                action_name = "rcs_shopify_connector.action_shopify_synced_sale_order_data"
                form_view_name = "rcs_shopify_connector.shopify_synced_data_form_view_rcs"

        elif self.shopify_operations == 'import_orders':
            url = self.truncate_shopify_store_url(self.shopify_connector_id.shopify_host, instance_id, 'orders')
            start_date_iso = self.start_date.isoformat()
            end_date_iso = self.end_date.isoformat()
            url_status = f"{url}?status=any&created_at_min={start_date_iso}&created_at_max={end_date_iso}"
            all_order_queue_ids = sale_order_obj.import_shopify_orders(url_status, instance_id)
            if all_order_queue_ids:
                queue_ids = all_order_queue_ids
                action_name = "rcs_shopify_connector.action_shopify_synced_sale_order_data"
                form_view_name = "rcs_shopify_connector.shopify_synced_data_form_view_rcs"

        elif self.shopify_operations == 'import_specific_order':
            url = self.truncate_shopify_store_url(self.shopify_connector_id.shopify_host, instance_id, 'orders')
            url_status = f"{url}?ids={self.import_specific_id}"
            specific_order = sale_order_obj.import_shopify_orders(url_status, instance_id)
            if specific_order:
                queue_ids = specific_order
                action_name = "rcs_shopify_connector.action_shopify_synced_sale_order_data"
                form_view_name = "rcs_shopify_connector.shopify_synced_data_form_view_rcs"

        elif self.shopify_operations == 'export_stock':
            url = self.truncate_shopify_store_url(self.shopify_connector_id.shopify_host, instance_id, 'inventory_levels/set')
            product_export = product_obj.export_shopify_product(url, instance_id)
            return product_export

        elif self.shopify_operations == 'import_payment_gateway':
            url = self.truncate_shopify_store_url(self.shopify_connector_id.shopify_host, instance_id, 'orders')
            start_date_iso = self.start_date.isoformat()
            end_date_iso = self.end_date.isoformat()
            url_status = f"{url}?status=any&created_at_min={start_date_iso}&created_at_max={end_date_iso}&fields=payment_gateway_names&limit=250"
            import_payment_gateway_ids = payment_gateway.create_shopify_payment_gateway(url_status, instance_id)
            if import_payment_gateway_ids:
                queue_ids = import_payment_gateway_ids
                action_name = "rcs_shopify_connector.rcs_shopify_payment_gateway_action"
                form_view_name = "rcs_shopify_connector.rcs_shopify_payment_gateway_form_view"

        if queue_ids and action_name and form_view_name:
            action = self.env.ref(action_name).sudo().read()[0]
            form_view = self.sudo().env.ref(form_view_name)

            if len(queue_ids) == 1:
                action.update({"view_id": (form_view.id, form_view.name), "res_id": queue_ids.ids[0],
                               "views": [(form_view.id, "form")]})
            else:
                action["domain"] = [("id", "in", queue_ids.ids)]
            return action

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

