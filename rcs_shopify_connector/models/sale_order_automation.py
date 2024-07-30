# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SaleOrderAutomation(models.Model):
    _name = "sale.order.automation"
    _description = "Sale WorkFlow Automation"
    _rec_name = "name"

    # Default method to get the default sales journal for the company
    @api.model
    def _get_set_default_journal(self):
        """
            Fetches the default sales journal for the company.
            :return: Default account.journal record for sales, or None.
        """
        company_id = self._context.get('company_id', self.env.company.id)
        return self.env['account.journal'].search([('type', '=', "sale"), ('company_id', '=', company_id)], limit=1)

    def _get_set_default_company(self):
        """
            Get default company based on current context or environment.
            :return: ID of the default company.
        """
        return self.env.company.id

    is_confirm_order = fields.Boolean(string="Confirm Order", default=False)
    is_create_invoice = fields.Boolean(string='Create Invoice', default=False)
    is_validate_invoice = fields.Boolean(string='Validate Invoice', default=False)
    is_register_payment = fields.Boolean(string='Register Payment', default=False)
    is_lock_order = fields.Boolean(string="Lock Confirmed Order", default=False)
    is_order_date_same_as_invoice_date = fields.Boolean(string='Invoice Date Same As Order')
    name = fields.Char(string="Name", translate=True)
    picking_policy = fields.Selection(
        [('direct', 'Deliver each product when available'), ('one', 'Deliver all products at once'), ('never', 'Deliver each product when available but not create backorder')],
        string='Shipping Policy', default="one")
    journal_id = fields.Many2one('account.journal', string='Payment Journal', domain=[('type', 'in', ['cash', 'bank'])])
    sale_journal_id = fields.Many2one('account.journal', string='Sales Journal', default=_get_set_default_journal, domain=[('type', '=', 'sale')])
    inbound_payment_method_line_id = fields.Many2one('account.payment.method.line', string="Debit Method", domain=[('payment_type', '=', 'inbound')])
    company_id = fields.Many2one('res.company', string='Company', default=_get_set_default_company)
    multi_shopify_connector_id = fields.Many2one('shopify.connector', string='Multi Shopify Connector', copy=False, required=True)

    @api.onchange("is_confirm_order")
    def onchange_confirm_order(self):
        for record_id in self:
            if not record_id.is_confirm_order:
                record_id.is_create_invoice = False

    @api.onchange("is_create_invoice")
    def onchange_create_invoice(self):
        for record_id in self:
            if not record_id.is_create_invoice:
                record_id.is_register_payment = False

