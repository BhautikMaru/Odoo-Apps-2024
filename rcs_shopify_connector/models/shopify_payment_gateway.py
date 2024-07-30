# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import requests
import json


class ShopifyPaymentGateway(models.Model):
    _name = "shopify.payment.gateway"
    _description = "Shopify Payment Gateway"
    _rec_name = "name"

    active = fields.Boolean(string="Active GateWay", default=True)
    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string="Code", required=True)
    multi_shopify_connector_id = fields.Many2one('shopify.connector', string='Multi Shopify Connector', copy=False,
                                                 required=True)


    def create_shopify_payment_gateway(self, url_status, shopify_instance_id):
        """
          Fetches payment gateways from Shopify and creates or updates them in the Odoo system.

          :param url_status: The URL endpoint to fetch payment gateway information from Shopify.
          :param shopify_instance_id: The Shopify instance record that contains authentication details
                                      for the request.
          :return: A recordset of `shopify.payment.gateway` instances that were created or updated.
          :rtype: recordset of `shopify.payment.gateway`
        """
        shopify_connection = self.env['shopify.connector']
        payment_gateway = []
        shopify_payment = None
        headers = {
            'X-Shopify-Access-Token': shopify_instance_id.shopify_access_token,
            'Content-Type': 'application/json'
        }
        try:
            response = requests.request("GET", url_status, headers=headers)
            if response.status_code == 200:
                response_data = response.json()
                for rec in response_data.get('orders'):
                    gateway = rec.get('payment_gateway_names') or ['no_payment_gateway']
                    payment_gateway.append(self.search_or_create_payment_gateway(shopify_instance_id, gateway[0], rec).id)

                return self.search([('id', 'in', payment_gateway)])
            else:
                log_id = shopify_connection._create_common_process_log(f"Failed to fetch payment gateway from Shopify.", "shopify.payment.gateway", shopify_payment, response.text)
                log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', shopify_payment, response.text, 'Failed to fetch payment gateway from Shopify', 'error')
                return shopify_payment

        except Exception as error:
            log_id = shopify_connection._create_common_process_log( f"Failed to fetch payment gateway from Shopify.", "shopify.payment.gateway", shopify_payment, error)
            log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', shopify_payment, error, 'Failed to fetch payment gateway from Shopify', 'error')
            return shopify_payment

    def search_or_create_payment_gateway(self, instance, gateway_name, rec):
        """
           Searches for an existing payment gateway record in Odoo or creates a new one if it does not exist.

           :param instance: The Shopify connector instance to associate with the payment gateway.
           :param gateway_name: The name of the payment gateway to search for or create.
           :param rec: The Shopify order record containing the payment gateway information. This is used for logging purposes.
           :return: The `shopify.payment.gateway` record that was found or created.
           :rtype: record of `shopify.payment.gateway`
        """
        shopify_connection = self.env['shopify.connector']

        shopify_payment_gateway = self.search([('code', '=', gateway_name),
                                               ('multi_shopify_connector_id', '=', instance.id)], limit=1)
        if not shopify_payment_gateway:
            shopify_payment_gateway = self.create({'name': gateway_name,
                                                   'code': gateway_name,
                                                   'multi_shopify_connector_id': instance.id})
            log_id = shopify_connection._create_common_process_log(
                f"Successfully created {shopify_payment_gateway.name} Payment Gateway from Shopify.", "shopify.payment.gateway", shopify_payment_gateway, rec)
            log_line_id = shopify_connection._create_common_process_log_line(log_id, shopify_payment_gateway.name, shopify_payment_gateway, rec,   f"Successfully created Payment Gateway from Shopify.", 'success')

        return shopify_payment_gateway