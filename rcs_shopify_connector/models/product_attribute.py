# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    is_shopify_attribute = fields.Boolean(string="Is Shopify Attribute", default=False)

