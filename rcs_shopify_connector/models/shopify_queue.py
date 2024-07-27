# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ShopifyQueue(models.Model):
    """ This model is used to handle the customer data queue."""
    _name = "shopify.queue"
    _description = "Shopify Queue"
    _rec_name = "name"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def _get_set_default_company(self):
        """
            Get default company based on current context or environment.
            :return: ID of the default company.
        """
        return self.env.company.id

    name = fields.Char(size=120, readonly=True)
    shopify_instance_id = fields.Many2one('shopify.connector', string='Shopify Instance')
    state = fields.Selection([("draft", "Draft"), ("partially_completed", "Partially Completed"),
                              ("completed", "Completed"), ("failed", "Failed")], compute="_compute_queue_state",
                             default="draft", store=True, tracking=True)
    shopify_synced_queue_line_ids = fields.One2many("shopify.queue.line", "shopify_synced_queue_id", "Shopify Queue")
    model_selection = fields.Selection([("res_partner", "Res Partner"), ("sale_order", "Sale Order"), ("product", "Product")],
        default="res_partner", store=True, tracking=True)
    total_record_count = fields.Integer(string="Total Records Count", compute="_compute_total_record_count")
    draft_state_count = fields.Integer(compute="_compute_total_record_count")
    done_state_count = fields.Integer(compute="_compute_total_record_count")
    cancel_state_count = fields.Integer(compute="_compute_total_record_count")
    company_id = fields.Many2one('res.company', string='Company', default=_get_set_default_company)

    @api.depends("shopify_synced_queue_line_ids.state")
    def _compute_total_record_count(self):
        """ Compute total, draft, done, and cancel state counts of queue lines. """
        for record in self:
            queue_lines = record.shopify_synced_queue_line_ids
            record.total_record_count = len(queue_lines)
            record.draft_state_count = len(queue_lines.filtered(lambda x: x.state == "draft"))
            record.done_state_count = len(queue_lines.filtered(lambda x: x.state == "done"))
            record.cancel_state_count = len(queue_lines.filtered(lambda x: x.state == "cancel"))

    @api.depends("shopify_synced_queue_line_ids.state")
    def _compute_queue_state(self):
        """
           Compute the overall state of the queue based on line states.
        """
        for record in self:
            if record.total_record_count == record.done_state_count + record.cancel_state_count:
                record.state = "completed"
            elif record.draft_state_count == record.total_record_count:
                record.state = "draft"
            elif record.total_record_count == record.cancel_state_count:
                record.state = "cancel"
            else:
                record.state = "partially_completed"

    @api.model
    def create(self, vals):
        """
            Override create method to set name and handle model-specific sequences.
            Args:
                vals (dict): Values dictionary for creating the record.
            Returns:
                Created record.
        """
        model = vals.get('model_selection')
        if model == 'res_partner':
            seq = self.env["ir.sequence"].next_by_code("shopify.queue.customer") or "/"
            vals.update({"name": seq or ""})
        elif model == 'product':
            seq = self.env["ir.sequence"].next_by_code("shopify.queue.product") or "/"
            vals.update({"name": seq or ""})
        else:
            seq = self.env["ir.sequence"].next_by_code("shopify.queue.order") or "/"
            vals.update({"name": seq or ""})
        return super(ShopifyQueue, self).create(vals)

    @api.model
    def create_queue(self, instance, model_selection):
        """
           Create a new queue entry.
           Args:
               instance (shopify.connector): Shopify instance object.
               model_selection (str): Type of data model ('res_partner', 'sale_order', 'product').
           Returns:
               odoo.models.Model: Created queue entry.
        """
        queue_vals = {
            "shopify_instance_id": instance and instance.id or False,
            "model_selection": model_selection
        }
        return self.create(queue_vals)

    def process_queue_manually(self):
        """
           Process queue lines manually based on selected model type.

           This method iterates over queue line items and attempts to process them
           according to the selected model type ('res_partner', 'product', 'sale_order').
           It updates the state of each queue line based on success or failure.
        """
        shopify_connection = self.env['shopify.connector']
        sale_order_obj = self.env['sale.order']
        partner_obj = self.env['res.partner']
        product_tmpl_obj = self.env['product.template']
        if self.model_selection == "res_partner":
            for record in self.shopify_synced_queue_line_ids:
                try:
                    synced_data = eval(record.shopify_synced_data)
                    partner_obj._create_or_update_customer(synced_data, record.shopify_instance_id)
                    record.state = "done"
                except Exception as e:
                    log_id = shopify_connection._create_common_process_log('Error: Customer import failed.', "res.partner", record, str(e))
                    log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', record, str(e), 'An error occurred while fetching customers from Shopify', 'error')
                    record.state = "cancel"

        if self.model_selection == "product":
            for record in self.shopify_synced_queue_line_ids:
                try:
                    synced_data = eval(record.shopify_synced_data)
                    product_tmpl_obj._create_or_update_product(synced_data, record.shopify_instance_id)
                    record.state = "done"
                except Exception as e:
                    log_id = shopify_connection._create_common_process_log("An error occurred while fetching products.", "product.template", record, str(e))
                    log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', record, str(e),  f"Failed to fetch products.", 'error')
                    record.state = "cancel"

        if self.model_selection == "sale_order":
            for record in self.shopify_synced_queue_line_ids:
                try:
                    synced_data = eval(record.shopify_synced_data)
                    cancelled_at = synced_data.get('cancelled_at')
                    if cancelled_at is None:
                        sale_order_obj._create_or_update_orders(synced_data, record.shopify_instance_id)
                        record.state = "done"
                except Exception as e:
                    record.state = "cancel"
                    log_id = shopify_connection._create_common_process_log("An error occurred while fetching order.", "sale.order", record, str(e))
                    log_line_id = shopify_connection._create_common_process_log_line(log_id, 'Error', record, str(e), "An error occurred while fetching orders.", 'error')

    def open_record_queue_data(self):
        """
            Open queue line records associated with this queue.
            Returns:
                dict: Action dictionary to open the records in a window.
        """
        shopify_queue_line_ids = self.env['shopify.queue.line'].search([('shopify_synced_queue_id', '=', self.name)])
        if shopify_queue_line_ids:
            view_form_id = self.env.ref('rcs_shopify_connector.shopify_shopify_data_queue_line_rcs_form_view').id
            view_tree_id = self.env.ref('rcs_shopify_connector.view_data_queue_line_tree').id
            action = {
                'type': 'ir.actions.act_window',
                'domain': [('id', 'in', shopify_queue_line_ids.ids)],
                'view_mode': 'tree,form',
                'name': _('Shopify Synced Line'),
                'res_model': 'shopify.queue.line',
            }
            if len(shopify_queue_line_ids.ids) == 1:
                action.update({'views': [(view_form_id, 'form')], 'res_id': shopify_queue_line_ids.id})
            else:
                action['views'] = [(view_tree_id, 'tree'), (view_form_id, 'form')]
            return action

    def open_draft_queue_data(self):
        """
            Open draft queue line records associated with this queue.
            Returns:
                dict: Action dictionary to open the records in a window.
        """
        shopify_queue_line_ids = self.env['shopify.queue.line'].search([('shopify_synced_queue_id', '=', self.name), ('state', '=', 'draft')])
        if shopify_queue_line_ids:
            view_form_id = self.env.ref('rcs_shopify_connector.shopify_shopify_data_queue_line_rcs_form_view').id
            view_tree_id = self.env.ref('rcs_shopify_connector.view_data_queue_line_tree').id
            action = {
                'type': 'ir.actions.act_window',
                'domain': [('id', 'in', shopify_queue_line_ids.ids)],
                'view_mode': 'tree,form',
                'name': _('Shopify Synced Line'),
                'res_model': 'shopify.queue.line',
            }
            if len(shopify_queue_line_ids.ids) == 1:
                action.update({'views': [(view_form_id, 'form')], 'res_id': shopify_queue_line_ids.id})
            else:
                action['views'] = [(view_tree_id, 'tree'), (view_form_id, 'form')]
            return action

    def open_done_queue_data(self):
        """
            Open done queue line records associated with this queue.
            Returns:
                dict: Action dictionary to open the records in a window.
        """
        shopify_queue_line_ids = self.env['shopify.queue.line'].search(
            [('shopify_synced_queue_id', '=', self.name), ('state', '=', 'done')])
        if shopify_queue_line_ids:
            view_form_id = self.env.ref('rcs_shopify_connector.shopify_shopify_data_queue_line_rcs_form_view').id
            view_tree_id = self.env.ref('rcs_shopify_connector.view_data_queue_line_tree').id
            action = {
                'type': 'ir.actions.act_window',
                'domain': [('id', 'in', shopify_queue_line_ids.ids)],
                'view_mode': 'tree,form',
                'name': _('Shopify Synced Line'),
                'res_model': 'shopify.queue.line',
            }
            if len(shopify_queue_line_ids.ids) == 1:
                action.update({'views': [(view_form_id, 'form')], 'res_id': shopify_queue_line_ids.id})
            else:
                action['views'] = [(view_tree_id, 'tree'), (view_form_id, 'form')]
            return action

    def open_cancel_queue_data(self):
        """
            Open cancel queue line records associated with this queue.
            Returns:
                dict: Action dictionary to open the records in a window.
        """
        shopify_queue_line_ids = self.env['shopify.queue.line'].search(
            [('shopify_synced_queue_id', '=', self.name), ('state', '=', 'cancel')])
        if shopify_queue_line_ids:
            view_form_id = self.env.ref('rcs_shopify_connector.shopify_shopify_data_queue_line_rcs_form_view').id
            view_tree_id = self.env.ref('rcs_shopify_connector.view_data_queue_line_tree').id
            action = {
                'type': 'ir.actions.act_window',
                'domain': [('id', 'in', shopify_queue_line_ids.ids)],
                'view_mode': 'tree,form',
                'name': _('Shopify Synced Line'),
                'res_model': 'shopify.queue.line',
            }
            if len(shopify_queue_line_ids.ids) == 1:
                action.update({'views': [(view_form_id, 'form')], 'res_id': shopify_queue_line_ids.id})
            else:
                action['views'] = [(view_tree_id, 'tree'), (view_form_id, 'form')]
            return action

    def cron_all_record_completed(self):
        """
            Cron job method to process all Shopify queues that are in 'draft' or 'partially_completed' state.
            This method searches for all Shopify queue records that are either in 'draft' or 'partially_completed' state.
            For each queue record found, it invokes the 'process_queue_manually' method to process its queue lines
            manually and update their states based on the processing results.
        """
        queues = self.env['shopify.queue'].search([('state', 'in', ['draft', 'partially_completed'])])
        for rec in queues:
            rec.process_queue_manually()
