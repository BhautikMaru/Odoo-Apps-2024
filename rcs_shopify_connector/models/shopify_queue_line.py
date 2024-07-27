# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import models, fields, api, _


class ShopifyQueueLine(models.Model):
    """This model is used to handel the customer data queue line"""
    _name = "shopify.queue.line"
    _description = "Shopify Synced Line"
    _rec_name = "name"

    shopify_data_id = fields.Text(string="Shopify ID")
    shopify_synced_data = fields.Char(string="Shopify Synced Data")
    shopify_synced_queue_id = fields.Many2one("shopify.queue", string="Shopify Customer", ondelete="cascade")
    last_process_date = fields.Datetime("Last Updated Date")
    shopify_instance_id = fields.Many2one('shopify.connector', string='Shopify Instance')
    name = fields.Char(string="Name", help="Shopify Name")
    state = fields.Selection([("draft", "Draft"), ("done", "Done"), ("cancel", "Cancelled")], default="draft")

    def shopify_create_multi_queue(self, shopify_queue_id, data_ids, instance_id, model_selection):
        """
           Create multiple queue lines based on the provided data IDs.
           Args:
               shopify_queue_id (shopify.queue): Parent queue ID to link the lines.
               data_ids (list): List of data IDs to create queue lines for.
               instance_id (shopify.connector): Shopify instance associated with the data.
               model_selection (str): Model type ('product', 'res_partner', etc.) determining line naming.
           Returns:
               bool: True if creation is successful.

        """
        if shopify_queue_id:
            for result in data_ids:
                self.shopify_data_queue_line_create(result, shopify_queue_id, instance_id, model_selection)
        return True

    def shopify_data_queue_line_create(self, result, shopify_queue_id, instance_id, model_selection):
        """
            Create a single queue line with the provided data.
            Args:
                result (dict): Data dictionary to create the queue line with.
                shopify_queue_id (shopify.queue): Parent queue ID to link the line.
                instance_id (shopify.connector): Shopify instance associated with the data.
                model_selection (str): Model type ('product', 'res_partner', etc.) determining line naming.
            Returns: shopify.queue.line: Created queue line object.
        """
        synced_shopify_customers_line_obj = self.env["shopify.queue.line"]
        name = ""
        if model_selection == 'product':
            name = result.get("title")
        elif model_selection == 'res_partner':
            name = "%s %s" % (result.get("first_name") or "", result.get("last_name") or "")
        else:
            name = result.get("name")
        shopify_id = result.get("id")
        data = result
        line_vals = {
            "shopify_synced_queue_id": shopify_queue_id.id,
            "shopify_data_id": shopify_id or "",
            "name": name.strip() if isinstance(name, str) else "",
            "shopify_synced_data": data,
            "shopify_instance_id": instance_id.id,
            "last_process_date": datetime.now(),
        }
        return synced_shopify_customers_line_obj.create(line_vals)
