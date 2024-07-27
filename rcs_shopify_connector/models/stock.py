# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _


class Location(models.Model):
    _inherit = 'stock.location'

    shopify_location_id = fields.Char("Shopify Location id")