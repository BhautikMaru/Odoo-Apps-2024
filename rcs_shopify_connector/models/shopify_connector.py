# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import requests
import logging

_LOGGER = logging.getLogger(">>> Common Process Logs <<<")


class ShopifyConnector(models.Model):
    _name = 'shopify.connector'
    _description = "Shopify Connector"
    _rec_name = "name"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def _get_set_default_company(self):
        """
            Get default company based on current context or environment.
            :return: ID of the default company.
        """
        return self.env.company.id

    @api.model
    def _default_language(self):
        """
            Get default language based on the current user's language.
            :return: ID of the default language.
        """
        lang_code = self.env.user.lang
        language = self.env["res.lang"].search([('code', '=', lang_code)])
        return language.id if language else False

    @api.model
    def _get_set_default_warehouse(self):
        """
            Get default warehouse for the company.
            :return: ID of the default warehouse.
        """
        stock_warehouse_obj = self.env['stock.warehouse']
        warehouse_id = stock_warehouse_obj.search([('company_id', '=', self.company_id.id)], limit=1, order='id')
        return warehouse_id.id if warehouse_id else False

    @api.model
    def _get_set_default_location_id(self):
        """
            Retrieves the default location ID for the current company.

            Searches for a stock warehouse associated with the company. If found,
            returns the ID of the associated stock location. Otherwise, returns False.
            Returns:
                int or False: The ID of the default location or False if not found.
        """
        stock_warehouse_obj = self.env['stock.warehouse']
        warehouse_id = stock_warehouse_obj.search([('company_id', '=', self.company_id.id)], limit=1, order='id')
        return warehouse_id.lot_stock_id.id if warehouse_id else False

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=_get_set_default_company, required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', default=_get_set_default_warehouse)
    name = fields.Char(string="Connector Name", required=True, tracking=True)
    shopify_api_key = fields.Char(string="API Key", required=True)
    shopify_access_token = fields.Char(string="API Access Token", required=True)
    shopify_api_secret_key = fields.Char(string="API Secret Key", required=True)
    shopify_host = fields.Char(string="Shopify Host", required=True)
    shopify_store_time_zone = fields.Char(string="Store Time Zone", readonly=True)
    version_control = fields.Selection([
        ('2023-07', '2023-07'),
        ('2023-10', '2023-10'),
        ('2024-01', '2024-01'),
        ('2024-04', '2024-04')
    ], string="Shopify Version Control", default='2024-04', required=True)
    state = fields.Selection(
        [('draft', "Draft"), ('integrated', 'Integrated'),
         ('error', 'Error')], string="State", default='draft', tracking=True)
    currency_id = fields.Many2one('res.currency', 'Currency', required=True)
    lang_id = fields.Many2one('res.lang', 'Language', default=_default_language, required=True)
    shopify_webhook_ids = fields.One2many("shopify.webhook", "shopify_instance_id", string="Shopify Webhooks", tracking=True, required=True)
    shopify_sale_order_process_ids = fields.One2many('shopify.sale.order.process.configuration', 'multi_shopify_connector_id', string="Order Process Configuration", tracking=True)
    location_id = fields.Many2one('stock.location', string='Location', default=_get_set_default_location_id, required=True)

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """
            Onchange method to update warehouse based on selected company.
        """
        if self.company_id:
            self.warehouse_id = self._get_set_default_warehouse()
            self.location_id = self._get_set_default_location_id()

    def truncate_shopify_store_url(self, shopify_host):
        """
           Truncate Shopify store URL to format required for API calls.
           :param shopify_host: Full Shopify store URL.
           :return: Truncated and formatted Shopify API URL.
        """
        shop = shopify_host.split("//")
        if len(shop) == 2:
            shop_url = shop[0] + "//" + shop[1] + "/admin/api/" + self.version_control + "/shop.json"
        else:
            shop_url = "https://" + shop[0] + "/admin/api/" + self.version_control + "/shop.json"
        return shop_url

    def reset_to_draft_connection(self):
        """
           Reset the connection state to draft.
           :return: None
        """
        self.state = 'draft'

    def _create_notification(self, title, message, notification_type):
        """
            Create a notification message for displaying to the user.
            :param title: Title of the notification.
            :param message: Message content of the notification.
            :param notification_type: Type of notification (success, danger, etc.).
            :return: Dictionary with notification details for client action.
        """
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': notification_type,
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }

    def sync_shopify_currency(self, currency_code):
        """
            Synchronize Shopify currency with Odoo currency.
            :param currency_code: Currency code from Shopify.
            :return: None
        """
        currency_obj = self.env['res.currency']
        existing_currency = currency_obj.with_context(active_test=False).search([('name', '=', currency_code)], limit=1)
        if existing_currency:
            if not existing_currency.active:
                existing_currency.write({'active': True})
            self.currency_id = existing_currency.id

    def shopify_connection_action(self):
        """
           Perform action to establish connection with Shopify.
           :return: Notification message for UI indicating success or failure of connection.
        """
        connector_obj = self.env['shopify.operations.wizard']
        payment_gateway = self.env["shopify.payment.gateway"]
        self.ensure_one()
        url = self.truncate_shopify_store_url(self.shopify_host)
        headers = {
            "X-Shopify-Access-Token": self.shopify_access_token
        }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                # Connection successful
                self.state = 'integrated'
                shop_data = response.json().get('shop', [])
                location = shop_data.get('primary_location_id')
                # Update location's shopify_location_id field
                if self.location_id:
                    self.location_id.shopify_location_id = location

                self.write({'shopify_store_time_zone': shop_data.get('timezone')})
                self.sync_shopify_currency(shop_data.get('currency'))

                payment_status = connector_obj.truncate_shopify_store_url(self.shopify_host, self, 'orders')
                patment_urlstatus = f"{payment_status}?status=any&fields=payment_gateway_names&limit=250"
                payment_gateway.create_shopify_payment_gateway(patment_urlstatus, self)

                return self._create_notification('Success', 'Store %s is successfully connected to Shopify!' % self.name,
                                                 'success')
            else:
                # Connection failed
                self.state = 'error'
                return self._create_notification('Connection Failed',
                                                 f'Unable to connect to Shopify. HTTP Status Code: {response.status_code}',
                                                 'danger')
        except requests.RequestException as e:
            self.state = 'error'
            return self._create_notification('Connection Error',
                                             f'An error occurred while connecting to Shopify: {str(e)}', 'danger')

    @api.model
    def create(self, vals):
        """
           Override create method to set default values for new records.
           :param vals: Dictionary of field values for new record.
           :return: Newly created record.
        """
        if 'warehouse_id' not in vals:
            vals['warehouse_id'] = self._get_set_default_warehouse()
        if vals.get("shopify_host").endswith('/'):
            vals["shopify_host"] = vals.get("shopify_host").rstrip('/')
        return super(ShopifyConnector, self).create(vals)

    def _create_common_process_log(self, message, model=False, res_id=False, response=False):
        """
            Create a log entry for a sale order process.
            Args:
                message (str): The log message.
                res_id (int): The resource ID of the sale order.
                response (str): The response message.
            Returns:
                recordset: The created log entry.
        """
        log_model = self.env['common.process.log']
        log = log_model.sudo().create({
            'name': self.env['ir.sequence'].sudo().next_by_code('common.process.log') or _('New'),
            'message': message,
            'res_model': model,
            'res_id': res_id,
            'response': response,
            'resource_log': 'shopify_connector'
        })
        return log

    def _create_common_process_log_line(self, log_id, name, res_id, response, message, state='success'):
        """
           Create a log line entry associated with a log.
           Args:
               log_id (recordset): The log record to which the log line will be added.
               res_id (int or None): The resource ID associated with the log line.
               response (str): The response message.
               message (str): The log message.
           Returns:
               recordset: The created log line entry.
        """
        log_line = log_id.line_ids.create({
            'process_log_id': log_id.id,
            'name': name,
            'res_id': res_id.id if res_id is not None else None,
            'response': response,
            'message': message,
            'state': state
        })
        return log_line



