# -*- coding: utf-8 -*-


from odoo import models, fields, api


class ShopifySaleOrderProcessConfiguration(models.Model):
    _name = "shopify.sale.order.process.configuration"
    _description = 'Sale auto workflow configuration'
    _rec_name = "shopify_order_financial_status"

    @api.model
    def _get_default_account_payment_terms(self):
        """
            Get default account payment terms ID from Odoo's predefined data.
            :return: ID of the immediate payment term or False if not found.
        """
        immediate_payment_terms_id = self.env.ref("account.account_payment_term_immediate")
        return immediate_payment_terms_id and immediate_payment_terms_id.id or False

    def _get_set_default_company(self):
        """
            Get default company based on current context or environment.
            :return: ID of the default company.
        """
        return self.env.company.id
    active = fields.Boolean(string="Active", default=True)
    shopify_order_financial_status = fields.Selection(
        [('pending', 'The payments are pending'), ('authorized', 'The payments have been authorized'),
         ('partially_paid', 'The order has been partially paid'), ('paid', 'The payments have been paid'),
         ('partially_refunded', 'The payments have been partially refunded'),
         ('refunded', 'The payments have been refunded'),
         ('voided', 'The payments have been voided')], default="paid")

    account_payment_term_id = fields.Many2one('account.payment.term', string='Payment Term', default=_get_default_account_payment_terms)
    multi_shopify_connector_id = fields.Many2one('shopify.connector', string='Multi Shopify Connector')
    shopify_payment_gateway_id = fields.Many2one("shopify.payment.gateway", string="Shopify Payment Gateway", ondelete="restrict")
    rcs_sale_order_automation_id = fields.Many2one("sale.order.automation", string="WorkFlow Automation")
    company_id = fields.Many2one('res.company', string='Company', default=_get_set_default_company)


