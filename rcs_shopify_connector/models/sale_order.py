# -*- coding: utf-8 -*-
import time
import requests
import logging
from pytz import utc
from odoo import models, fields, api, _
from dateutil import parser
from odoo.tools.misc import split_every

_LOGGER = logging.getLogger(">>> Shopify Import Orders <<<")


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_shopify_order = fields.Boolean(string='Is Shopify Order', default=False)
    shopify_instance_id = fields.Many2one('shopify.connector', string='Shopify Instance', tracking=True)
    shopify_order_id = fields.Char(string='Shopify Order ID', tracking=True)
    log_count = fields.Integer(string='Sale Order Logs', compute='_get_sale_order_logs', store=True)
    shopify_payment_gateway_id = fields.Many2one("shopify.payment.gateway", string="Shopify Payment Gateway", ondelete="restrict")


    @api.depends('shopify_order_id')
    def _get_sale_order_logs(self):
        """
           @usage: For count the related Sale order log
                   Method will assign total number of logs to field log_count
        """
        process_log = self.env['common.process.log']
        for rec in self:
            log_count = process_log._get_log_count(rec.id, 'sale.order', rec.company_id.id, "shopify_connector")
            rec.log_count = len(log_count)

    def open_sale_order_logs(self):
        """
            @usage: For open the Sale order logs
            :return: action
        """
        process_log = self.env['common.process.log']
        log_ids = process_log._get_log_count(self.id, 'sale.order', self.company_id.id,  "shopify_connector")
        return process_log._open_logs_action(log_ids)

    def convert_order_date(self, order):
        """
            Convert Shopify order date to Odoo-compatible format.
            :param order: Dictionary containing Shopify order data.
            :return: Converted date string.
        """
        if order.get("created_at", False):
            order_date = order.get("created_at", False)
            date_order = parser.parse(order_date).astimezone(utc).strftime("%Y-%m-%d %H:%M:%S")
        else:
            date_order = time.strftime("%Y-%m-%d %H:%M:%S")
            date_order = str(date_order)
        return date_order

    def _get_partner_id(self, shopify_customer_id, instance_id):
        """
            Retrieve partner ID based on Shopify customer ID and instance.
            :param shopify_customer_id: Shopify customer ID.
            :param instance_id: Shopify instance ID (shopify.connector record).
            :return: res.partner record.
        """
        connector_obj = self.env['shopify.operations.wizard']
        partner_obj = self.env['res.partner']

        partner_id = partner_obj.search([('shopify_customer_id', '=', shopify_customer_id),
                                         ('shopify_instance_id', '=', instance_id.id)])
        if partner_id:
            return partner_id
        else:
            host = connector_obj.add_https_to_url(instance_id.shopify_host)
            url = f"{host}/admin/api/{instance_id.version_control}/customers/{shopify_customer_id}.json"
            partner_id = partner_obj.import_customer(url, instance_id)
            return partner_id

    def _create_or_update_orders(self, order, instance_id):
        """
            Create or update a sale order based on Shopify order data.
            :param order: Dictionary containing Shopify order data.
            :param instance_id: Shopify instance ID (shopify.connector record).
            :return: Created or updated sale.order record.
        """
        shopify_connection = self.env['shopify.connector']
        financial_status = order.get('financial_status')
        fulfillment_status = order.get('fulfillment_status')
        payment_gateway_name = order.get('payment_gateway_names') or 'no_payment_gateway'
        # Fetch automation settings based on financial status and instance
        automation_settings = self._get_automation_settings(instance_id, financial_status, payment_gateway_name)
        payment_term_id = automation_settings.account_payment_term_id.id if automation_settings else False
        payment_gateway_id = automation_settings.shopify_payment_gateway_id.id if automation_settings else False
        shopify_order_id = order.get('id')
        name = order.get('name')
        shopify_customer_id = order.get('customer').get('id') if order.get('customer') else ''
        date_order = self.convert_order_date(order)
        partner_id = self._get_partner_id(shopify_customer_id, instance_id)
        taxes_included = order.get("taxes_included") or False

        sale_order_vals = {
            'partner_id': partner_id.id,
            'is_shopify_order': True,
            'shopify_order_id': shopify_order_id,
            'shopify_instance_id': instance_id.id,
            'date_order': date_order,
            'company_id': instance_id.company_id.id,
            'payment_term_id': payment_term_id,
            'shopify_payment_gateway_id': payment_gateway_id

        }
        existing_order = self.search(
            [('shopify_order_id', '=', shopify_order_id), ('shopify_instance_id', '=', instance_id.id)], limit=1)

        if existing_order:
            if existing_order.state in ['sale', 'cancel']:
                log_id = shopify_connection._create_common_process_log(f"Successfully update {name} order from Shopify.", "sale.order", existing_order, order)
                log_line_id = shopify_connection._create_common_process_log_line(log_id, name, existing_order, order, f"Successfully updated {name} order from Shopify.", 'success')
            else:
                existing_order.write(sale_order_vals)
                log_id = shopify_connection._create_common_process_log(f"Successfully update {name} order from Shopify.", "sale.order", existing_order, order)
                log_line_id = shopify_connection._create_common_process_log_line(log_id, name, existing_order, order, f"Successfully updated {name} order from Shopify.", 'success')
        else:
            existing_order = self.create(sale_order_vals)
            log_id = shopify_connection._create_common_process_log(f"Successfully created {name} order from Shopify.", "sale.order", existing_order, order)
            log_line_id = shopify_connection._create_common_process_log_line(log_id, name, existing_order, order, f"Successfully created {name} order from Shopify.", 'success')

        line_items = order.get('line_items')
        if existing_order.state not in ["sale", "cancel"]:
            order_line = self._create_sale_order_line(existing_order, line_items, order.get('tax_lines', []), taxes_included,
                                                      instance_id, log_id)

        if automation_settings:
            self._process_automation_settings(existing_order, automation_settings.rcs_sale_order_automation_id, fulfillment_status)
        return existing_order

    def _get_automation_settings(self, instance_id, financial_status, payment_gateway_name):
        """
            Retrieve automation settings based on Shopify instance and financial status.
            :param instance_id: Shopify instance ID (shopify.connector record).
            :param financial_status: Financial status of the Shopify order.
            :return: Automation settings record (sale.order.automation) or False.
        """
        if financial_status and payment_gateway_name:
            # Filter the configurations based on financial status and payment gateway
            configuration = instance_id.shopify_sale_order_process_ids.filtered(
                lambda config: (
                        config.shopify_order_financial_status == financial_status and
                        config.shopify_payment_gateway_id.name == payment_gateway_name
                )
            )
            if configuration:
                return configuration[0]
        return False

    def _process_automation_settings(self, sale_order, automation_settings, fulfillment_status):
        """
        Process automation settings for a sale order.
        :param sale_order: Sale order record.
        :param automation_settings: Automation settings record (sale.order.automation).
        :param fulfillment_status: Status of the fulfillment ('fulfilled' or other).
        """
        invoice = None

        if sale_order.state == "draft" and automation_settings.is_confirm_order:
            sale_order.action_confirm()

        if fulfillment_status == "fulfilled" and not sale_order.picking_ids.filtered(lambda p: p.state == 'done'):
            self.validate_delivery(sale_order, automation_settings)

        if automation_settings.is_create_invoice and sale_order.state in ['sale', 'cancel']:
            if sale_order.invoice_status != 'invoiced':
                invoice = sale_order.with_context(default_journal_id=automation_settings.sale_journal_id.id)._create_invoices()
            else:
                invoice = sale_order.invoice_ids.filtered(lambda inv: inv.state != 'cancel')[0] if sale_order.invoice_ids else None

        if invoice and automation_settings.is_validate_invoice and invoice.state == 'draft':
            invoice.action_post()

        if invoice and invoice.payment_state in ["not_paid", "partial"] and invoice.amount_residual != 0 and automation_settings.is_register_payment:
            self._register_payment(invoice, automation_settings)

        if automation_settings.is_order_date_same_as_invoice_date:
            sale_order.invoice_ids.filtered(lambda inv: inv.state != 'cancel').write({'invoice_date': sale_order.date_order})

        if sale_order.state == 'sale' and sale_order.locked != True and automation_settings.is_lock_order:
            sale_order.action_lock()

    def validate_delivery(self, sale_order, automation_settings):
        """
            Validate the delivery process based on the automation settings.
            Args:
                sale_order (recordset): The sale order record containing delivery information.
                automation_settings (recordset): Settings that determine the picking policy.
            Returns:
                bool: True if the delivery process is validated.
        """
        if automation_settings.picking_policy == "direct":
            delivery = sale_order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
            for picking in delivery:
                if picking.state in ('waiting', 'confirmed'):
                    picking.action_assign()
                if picking.move_line_ids_without_package:
                    picking_policy = picking.picking_type_id.create_backorder = "always"
                    picking.with_context(skip_sms=True).button_validate()
        elif automation_settings.picking_policy == "never":
            delivery = sale_order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
            for picking in delivery:
                if picking.state in ('waiting', 'confirmed'):
                    picking.action_assign()
                if picking.move_line_ids_without_package:
                    picking_policy = picking.picking_type_id.create_backorder = "never"
                    picking.with_context(skip_sms=True).button_validate()
        else:
            delivery = sale_order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
            for picking in delivery:
                if picking.state in ('waiting', 'confirmed'):
                    picking.action_assign()
                for move in picking.move_ids:
                    move.quantity = move.product_uom_qty
            picking.with_context(skip_backorder=True, skip_sms=True).button_validate()
        return True

    def _register_payment(self, invoice, automation_settings):
        """
           Register payment for an invoice.
           :param invoice: Invoice record.
        """
        for invoice in invoice:
            self.env['account.payment.register']\
                .with_context(active_model='account.move', active_ids=invoice.ids)\
                .create({
                'journal_id': automation_settings.journal_id.id,
                'payment_method_line_id': automation_settings.inbound_payment_method_line_id.id,
                'amount': invoice.amount_residual,
            })._create_payments()

    def _get_product_id(self, shopify_product_id, shopify_variant_id, instance_id):
        """
            Retrieve product ID based on Shopify product ID and variant ID.
            :param shopify_product_id: Shopify product ID.
            :param shopify_variant_id: Shopify product variant ID.
            :param instance_id: Shopify instance ID (.shopify.connector record).
            :return: Product variant record (product.product).
        """
        product_obj = self.env['product.template']
        connector_obj = self.env['shopify.operations.wizard']
        product_id = product_obj.search([('shopify_product_id', '=', shopify_product_id)])
        # return product_id
        if product_id:
            variant_ids = product_id.product_variant_ids
            for variant in variant_ids:
                if variant.shopify_variant_id == str(shopify_variant_id):
                    return variant
        else:
            host = connector_obj.add_https_to_url(instance_id.shopify_host)
            url = f"{host}/admin/api/{instance_id.version_control}/products/{shopify_product_id}.json"
            product_id = product_obj.import_product(url, instance_id)
            if product_id:
                variant_ids = product_id.product_variant_ids
                for variant in variant_ids:
                    if variant.shopify_variant_id == str(shopify_variant_id):
                        return variant

    def _create_sale_order_line(self, existing_order_id, line_items, tax_lines, taxes_included, instance_id, log_id):
        """
            Create sale order lines based on Shopify order line items.
            :param existing_order_id: Sale order record.
            :param line_items: List of line items from Shopify order.
            :param tax_lines: Tax lines from Shopify order.
            :param taxes_included: Boolean indicating if taxes are included.
            :param instance_id: Shopify instance ID (shopify.connector record).
            :return: Created sale order line record (sale.order.line).
        """
        shopify_connection = self.env['shopify.connector']
        sale_order_line_obj = self.env["sale.order.line"]
        existing_order_line = None
        for line in line_items:
            name = None
            try:
                line_id = line.get('id')
                order_qty = line.get('current_quantity')
                name = line.get('name')
                price = line.get('price')
                company = instance_id.company_id
                product_id = self._get_product_id(line.get('product_id'), line.get('variant_id'), instance_id)
                taxes = self._get_or_create_taxes(tax_lines, taxes_included, company)

                order_line_vals = {
                    "order_id": existing_order_id.id,
                    "shopify_order_line_id": line_id,
                    "shopify_instance_id": instance_id.id,
                    "product_id": product_id.id,
                    "name": name,
                    "company_id": company.id,
                    "product_uom": product_id.uom_id.id,
                    "price_unit": price,
                    "product_uom_qty": order_qty,
                    "tax_id": [(6, 0, taxes.ids)],
                }

                existing_order_line = sale_order_line_obj.search([('shopify_order_line_id', '=', line_id), ('shopify_instance_id', '=', instance_id.id)])
                if existing_order_line:
                    existing_order_line.write(order_line_vals)
                else:
                    existing_order_line = sale_order_line_obj.create(order_line_vals)
                    log_line_id = shopify_connection._create_common_process_log_line(log_id, name, existing_order_line, line, f"Successfully created {name} order line from Shopify.", 'success')

            except Exception as e:
                log_line_id = shopify_connection._create_common_process_log_line(log_id, name, existing_order_line, str(e), f"Failed to created {name} order line from Shopify.", 'error')

    def _get_or_create_taxes(self, tax_lines, tax_included, company):
        """
            Retrieve or create taxes based on Shopify tax lines.
            :param tax_lines: Tax lines from Shopify order.
            :param tax_included: Boolean indicating if taxes are included.
            :param company: Company record.
            :return: Tax records (account.tax).
        """
        tax_obj = self.env['account.tax']
        tax_ids = []
        for tax_line in tax_lines:
            rate = float(tax_line.get("rate", 0.0))
            rate = rate * 100
            price = float(tax_line.get('price', 0.0))
            title = tax_line.get("title")
            if rate != 0.0 and price != 0.0:
                if tax_included:
                    name = "%s_(%s %s included)" % (title, str(rate), "%")
                else:
                    name = "%s_(%s %s excluded)" % (title, str(rate), "%")
                tax = self.env["account.tax"].search([("price_include", "=", tax_included),
                                                      ("type_tax_use", "=", "sale"), ("amount", "=", rate),
                                                      ("name", "=", name), ("company_id", "=", company.id)], limit=1)
                if not tax:
                    tax = tax_obj.create({
                        'name': name,
                        'amount': rate,
                        'type_tax_use': 'sale',
                        'amount_type': 'percent',
                    })
                tax_ids.append(tax.id)
        return tax_obj.browse(tax_ids)

    def import_shopify_orders(self, url_status, instance_id):
        """
            Import Shopify orders within a specified date range.
            :param url_status: URL to fetch Shopify orders.
            :param instance_id: Shopify instance ID (shopify.connector record).
            :param start_date: Start date for filtering orders.
            :param end_date: End date for filtering orders.
            :return: Notification of success or failure.
        """
        shopify_connection = self.env['shopify.connector']
        sale_order_obj = self.env['sale.order']
        connector_obj = self.env['shopify.operations.wizard']
        order_id = None
        headers = {
            "X-Shopify-Access-Token": instance_id.shopify_access_token
        }
        try:
            response = requests.get(url_status, headers=headers)
            if response.status_code == 200:
                orders = response.json().get('orders', [])
                order = response.json().get('order', [])
                if order:
                    try:
                        order_id = sale_order_obj._create_or_update_orders(order, instance_id)
                        return order_id
                    except Exception as e:
                        log_id = shopify_connection._create_common_process_log("Failed to import", "sale.order", order_id, response.json())
                        log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', order_id, response.json(), str(e), 'error')
                        return sale_order_obj
                else:
                    if orders:
                        try:
                            order_queue_ids = self.create_sale_order_data_queues(orders, instance_id)
                            return order_queue_ids
                        except Exception as e:
                            log_id = shopify_connection._create_common_process_log("Failed to import", "sale.order", order_queue_ids, str(e))
                            log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', order_queue_ids, response.json(), str(e), 'error')

                            return sale_order_obj
            else:
                log_id = shopify_connection._create_common_process_log("Failed to fetch orders from Shopify", "sale.order", order_id, response.json())
                log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', order_id, response.json(),  f"Failed to fetch sale order from Shopify. HTTP Error: {response.status_code}", 'error')

                return sale_order_obj
        except requests.RequestException as e:
            log_id = shopify_connection._create_common_process_log("An error occurred while fetching order from Shopify", "sale.order", order_id, str(e))
            log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', order_id, str(e), "An error occurred while fetching orders from Shopify", 'error')
            return sale_order_obj

    def create_sale_order_data_queues(self, order_data, instance_id):
        """
           Create queues for sale order data import.
           Args:
               order_data (list): List of sale order data to be queued.
               instance_id (int): ID of the Shopify instance.
           Returns:
               list: List of created order queue IDs.
        """
        order_queue_list = []
        order_data_queue_obj = self.env["shopify.queue"]
        order_data_queue_line_obj = self.env["shopify.queue.line"]

        if len(order_data) > 0:
            for order_id_chunk in split_every(125, order_data):
                order_queue = order_data_queue_obj.create_queue(instance_id, "sale_order")
                order_data_queue_line_obj.shopify_create_multi_queue(order_queue, order_id_chunk, instance_id, "sale_order")
                order_queue_list.append(order_queue.id)
            self._cr.commit()
        return order_data_queue_obj.search([('id', 'in', order_queue_list)])


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    shopify_order_line_id = fields.Char(string='Shopify Order Line ID')
    shopify_instance_id = fields.Many2one('shopify.connector', string='Shopify Instance', tracking=True)

