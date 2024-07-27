# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProductCategory(models.Model):
    _inherit = "product.category"

    is_shopify_category = fields.Boolean(string="Is Shopify Category", default=False)
