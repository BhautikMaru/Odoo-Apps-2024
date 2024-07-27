# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SetuShopifyPaymentGateway(models.Model):
    _name = "rcs.shopify.payment.gateway"
    _description = "Shopify Payment Gateway"

    active = fields.Boolean(string="Active GateWay", default=True)
    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string="Code", required=True)
    multi_shopify_connector_id = fields.Many2one('shopify.connector', string='Multi e-Commerce Connector', copy=False, required=True)

