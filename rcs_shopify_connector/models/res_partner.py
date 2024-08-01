# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.tools.misc import split_every
import requests
import logging

_logger = logging.getLogger(">>> Shopify Import Customer <<<")


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_shopify_customer = fields.Boolean(string="Is Shopify Customer", default=False)
    shopify_customer_id = fields.Char(string="Shopify Customer ID", tracking=True)
    shopify_instance_id = fields.Many2one('shopify.connector', string='Shopify Instance', tracking=True)
    log_count = fields.Integer(string='Customer Logs', compute='_get_customer_logs', store=True)

    @api.depends('shopify_customer_id')
    def _get_customer_logs(self):
        """
           @usage: For count the related customer log
                   Method will assign total number of logs to field log_count
        """
        process_log = self.env['common.process.log']
        for rec in self:
            log_count = process_log._get_log_count(rec.id, 'res.partner', rec.company_id.id, "shopify_connector")
            rec.log_count = len(log_count)

    def open_customer_logs(self):
        """
            @usage: For open the Customer logs
            :return: action
        """
        process_log = self.env['common.process.log']
        log_ids = process_log._get_log_count(self.id, 'res.partner', self.company_id.id, "shopify_connector")
        return process_log._open_logs_action(log_ids)

    def _get_country_or_state_id(self, state_name, country_code):
        """
            Get state and country IDs based on state name and country code.
            :param state_name: Name of the state.
            :param country_code: Code of the country.
            :return: Tuple (state_id, country_id)
        """
        country_id = False
        state_id = False
        if state_name or country_code:
            country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
            if country:
                country_id = country.id
                state = self.env['res.country.state'].search(
                    [('name', '=', state_name), ('country_id', '=', country.id)], limit=1)
                if state:
                    state_id = state.id
        return state_id, country_id

    @api.model
    def archive_customer_by_shopify_id(self, customer_data, instance_id):
        """
            Archive customer based on Shopify customer ID and Shopify instance ID.
            :param customer_data: Dictionary containing Shopify customer data.
            :param instance_id: Shopify instance ID (shopify.connector record).
            :return: True if customer is archived successfully, False otherwise.
        """
        shopify_connection = self.env['shopify.connector']
        customer_id = customer_data['id']
        _logger.info("Attempting to archive customer with Shopify ID: %s",customer_id)
        try:
            partner = self.search([('shopify_customer_id', '=', customer_id), ('shopify_instance_id', '=', instance_id.id)])
            if partner:
                _logger.info("Found %d Customer with Shopify Customer ID: %s", len(partner), customer_id)
                partner.write({'active': False})
                log_id = shopify_connection._create_common_process_log( f"Successfully archived Customer with Shopify Customer ID: {customer_id}", "res.partner", partner, customer_id)
                log_line_id = shopify_connection._create_common_process_log_line(log_id, partner.name, partner, customer_id, f"Customer with Shopify Customer ID: {customer_id} have been archived.", 'success')
                _logger.info("Successfully archived Customer with Shopify Customer ID: %s", customer_id)
                return True
            else:
                _logger.info("No Customer found to archive with Shopify Customer ID: %s", customer_id)
                return False
        except Exception as e:
            log_id = shopify_connection._create_common_process_log(f"Failed to archive Customer with Shopify Customer ID: {customer_id}", "res.partner", None, str(e))
            log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', None, str(e), f"An error occurred while archiving Customer with Shopify Customer ID: {customer_id}. Error: {str(e)}", 'error')
            _logger.error("An error occurred while attempting to archive Customer with Shopify Customer ID: %s. Error: %s", customer_id, str(e))
            return False

    def _create_or_update_customer(self, customer_data, instance_id):
        """
            Create or update a customer based on Shopify customer data.
            :param customer_data: Dictionary containing Shopify customer data.
            :param instance_id: Shopify instance ID (shopify.connector record).
            :return: Updated or newly created partner record.
        """
        partner_obj = self.env['res.partner']
        shopify_connection = self.env['shopify.connector']
        customer_id = None
        try:
            # Check if the customer already exists
            existing_partner = self.search([('shopify_customer_id', '=', customer_data['id']),
                                            ('shopify_instance_id', '=', instance_id.id)], limit=1)
            default_address = customer_data.get('default_address')
            state_id, country_id = self._get_country_or_state_id(default_address.get('province') if default_address else '', default_address.get('country_code') if default_address else '')
            first_name = customer_data.get('first_name', '')
            last_name = customer_data.get('last_name', '')
            name = f"{first_name} {last_name}".strip()
            vals = {
                'name': name,
                'email': customer_data.get('email'),
                'phone': customer_data.get('phone'),
                'street': default_address.get('address1') if default_address else False,
                'street2': default_address.get('address2') if default_address else False,
                'city': default_address.get('city') if default_address else False,
                'zip': default_address.get('zip') if default_address else False,
                'state_id': state_id,
                'country_id': country_id,
                'shopify_customer_id': customer_data.get('id'),
                'shopify_instance_id': instance_id.id,
                'company_type': 'person',
                'is_shopify_customer': True,
                'company_id': instance_id.company_id.id
            }
            if not existing_partner:
                existing_partner = self.create(vals)
                _logger.info("Successfully created customer '%s' from Shopify.", name)
                log_id = shopify_connection._create_common_process_log(f"Successfully created {name} customer from Shopify.", "res.partner", existing_partner, customer_data)
                log_line_id = shopify_connection._create_common_process_log_line(log_id, name, existing_partner, customer_data, f"Successfully imported {name} customer from Shopify.", 'success')
            else:
                existing_partner.write(vals)
                _logger.info("Successfully updated customer '%s' from Shopify.", name)
                log_id = shopify_connection._create_common_process_log(f"Successfully update {name} customer from Shopify.", "res.partner", existing_partner, customer_data)
                log_line_id = shopify_connection._create_common_process_log_line(log_id, name, existing_partner, customer_data, f"Successfully updated {name} customer from Shopify.", 'success')
            return existing_partner
        except Exception as e:
            _logger.error("An error occurred while creating or updating customer with Shopify ID '%s': %s", str(e), exc_info=True)
            log_id = shopify_connection._create_common_process_log('An error occurred while creating customers from Shopify', "res.partner", customer_id, str(e))
            log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', customer_id, str(e), 'Error: Customer created failed.', 'error')
            return partner_obj

    def import_customer(self, url, instance_id):
        """
           Import customers from Shopify using API.
           :param url: Shopify API URL for fetching customers.
           :param instance_id: Shopify instance ID (shopify.connector record).
           :return: Notification action to display success or error message.
        """
        shopify_connection = self.env['shopify.connector']
        partner_obj = self.env['res.partner']
        customer_id = None
        headers = {
            "X-Shopify-Access-Token": instance_id.shopify_access_token
        }
        try:
            _logger.info("Fetching customers from Shopify with URL: %s", url)
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                customers = response.json().get('customers', [])
                customer = response.json().get('customer', [])
                if customer:
                    try:
                        _logger.info("Processing single customer data: %s", customer)
                        customer_id = partner_obj._create_or_update_customer(customer, instance_id)
                        return customer_id
                    except Exception as e:
                        log_id = shopify_connection._create_common_process_log(f"Customer import Failed", "res.partner", customer_id, customer)
                        log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', customer_id, customer, str(e), 'error')
                        return partner_obj
                else:
                    if customers:
                        try:
                            customer_queue_ids = self.create_customer_data_queues(customers, instance_id)
                            return customer_queue_ids
                        except Exception as e:
                            log_id = shopify_connection._create_common_process_log(f"Customer import Failed", "res.partner", customer_id, customer)
                            log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', customer_id, customer, str(e), 'error')
                            return partner_obj
            else:
                log_id = shopify_connection._create_common_process_log(f"Failed to fetch customers from Shopify.", "res.partner", customer_id, response.text)
                log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', customer_id,  response.text, 'Failed to fetch customers from Shopify', 'error')
                return partner_obj
        except requests.RequestException as e:
            log_id = shopify_connection._create_common_process_log('An error occurred while fetching customers from Shopify', "res.partner", customer_id, str(e))
            log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', customer_id, str(e), 'Error: Customer import failed.', 'error')
            return partner_obj

    def create_customer_data_queues(self, customer_data, instance_id):
        """
            Create queues for customer data import.
            Args:
                customer_data (list): List of customer data to be queued.
                instance_id (int): ID of the Shopify instance.
            Returns:
                list: List of created customer queue IDs.
        """
        customer_queue_list = []
        customer_data_queue_obj = self.env["shopify.queue"]
        customer_data_queue_line_obj = self.env["shopify.queue.line"]

        if len(customer_data) > 0:
            for customer_id_chunk in split_every(125, customer_data):
                customer_queue = customer_data_queue_obj.create_queue(instance_id, "res_partner")
                customer_data_queue_line_obj.shopify_create_multi_queue(customer_queue, customer_id_chunk, instance_id, 'res_partner')
                customer_queue_list.append(customer_queue.id)
            self._cr.commit()
        return customer_data_queue_obj.search([('id', 'in', customer_queue_list)])