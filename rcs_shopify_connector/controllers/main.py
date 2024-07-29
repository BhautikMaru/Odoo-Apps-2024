# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class Main(http.Controller):

    def check_hook_details(self, route):
        res = {'id': 7683885039821, 'email': None, 'created_at': '2024-06-25T07:30:29-04:00',
         'updated_at': '2024-06-25T07:30:29-04:00', 'first_name': 'DEMO', 'last_name': '3',
         'orders_count': 0,
         'state': 'disabled', 'total_spent': '0.00', 'last_order_id': None, 'note': '',
         'verified_email': True,
         'multipass_identifier': None, 'tax_exempt': False, 'tags': '', 'last_order_name': None,
         'currency': 'INR', 'phone': None, 'addresses': [
            {'id': 10296598528205, 'customer_id': 7683885039821, 'first_name': 'DEMO', 'last_name': '3',
             'company': '', 'address1': '', 'address2': '', 'city': '', 'province': '', 'country': 'India',
             'zip': '', 'phone': '', 'name': 'DEMO 3', 'province_code': None, 'country_code': 'IN',
             'country_name': 'India', 'default': True}], 'tax_exemptions': [], 'email_marketing_consent': None,
         'sms_marketing_consent': None, 'admin_graphql_api_id': 'gid://shopify/Customer/7683885039821',
         'default_address': {'id': 10296598528205, 'customer_id': 7683885039821, 'first_name': 'DEMO',
                             'last_name': '3', 'company': '', 'address1': '', 'address2': '', 'city': '',
                             'province': '', 'country': 'India', 'zip': '', 'phone': '', 'name': 'DEMO 3',
                             'province_code': None, 'country_code': 'IN', 'country_name': 'India',
                             'default': True}}
        # res = request.dispatcher.jsonrequest
        host = request.httprequest.headers.get("X-Shopify-Shop-Domain")
        shopify_instance_id = request.env["shopify.connector"].sudo().with_context(active_test=False).search(
            [("shopify_host", "ilike", host)], limit=1)
        webhook_id = request.env["shopify.webhook"].sudo().search(
            [("base_url", "ilike", route), ("shopify_instance_id", "=", shopify_instance_id.id)], limit=1)
        if not shopify_instance_id.state == 'integrated' or not shopify_instance_id.active or not webhook_id.state == "active":
            res = False
        return res, shopify_instance_id

    # Webhook for creating or updating customers in Shopify
    @http.route(['/rcs_shopify_customer_create_hook', '/rcs_shopify_customer_update_hook'], type='http', auth="public", )
    def customer_create_or_update_webhook(self):
        """
            Handle webhook for creating or updating customers in Shopify.
            This method processes incoming webhook data to create or update customer records in Odoo based on Shopify data.
            Returns:
                str: Confirmation message indicating the webhook was received or processing failed.
        """
        partner_obj = request.env['res.partner'].sudo()
        hook_route = request.httprequest.path.split('/')[1]
        res, shopify_instance_id = self.check_hook_details(hook_route)
        if not res:
            return
        try:
            data = res
            # data = {'id': 7683885039821, 'email': None, 'created_at': '2024-06-25T07:30:29-04:00',
            #         'updated_at': '2024-06-25T07:30:29-04:00', 'first_name': 'DEMO', 'last_name': '3',
            #         'orders_count': 0,
            #         'state': 'disabled', 'total_spent': '0.00', 'last_order_id': None, 'note': '',
            #         'verified_email': True,
            #         'multipass_identifier': None, 'tax_exempt': False, 'tags': '', 'last_order_name': None,
            #         'currency': 'INR', 'phone': None, 'addresses': [
            #         {'id': 10296598528205, 'customer_id': 7683885039821, 'first_name': 'DEMO', 'last_name': '3',
            #          'company': '', 'address1': '', 'address2': '', 'city': '', 'province': '', 'country': 'India',
            #          'zip': '', 'phone': '', 'name': 'DEMO 3', 'province_code': None, 'country_code': 'IN',
            #          'country_name': 'India', 'default': True}], 'tax_exemptions': [], 'email_marketing_consent': None,
            #         'sms_marketing_consent': None, 'admin_graphql_api_id': 'gid://shopify/Customer/7683885039821',
            #         'default_address': {'id': 10296598528205, 'customer_id': 7683885039821, 'first_name': 'DEMO',
            #                             'last_name': '3', 'company': '', 'address1': '', 'address2': '', 'city': '',
            #                             'province': '', 'country': 'India', 'zip': '', 'phone': '', 'name': 'DEMO 3',
            #                             'province_code': None, 'country_code': 'IN', 'country_name': 'India',
            #                             'default': True}}

            # connector_obj = request.env['shopify.connector'].sudo()
            # con = connector_obj.browse(17)
            if data:
                partner_obj._create_or_update_customer(data, shopify_instance_id)
                # partner_obj._create_or_update_customer(data, con)
            return 'Webhook received'
        except Exception as e:
            return 'Webhook processing failed'

    @http.route(['/rcs_shopify_customer_delete_hook'], csrf=False, auth="public", type="json", methods=['POST'])
    def customer_delete_webhook(self):
        """
            Handle webhook for deleting customers in Shopify.
            This method processes incoming webhook data to delete customer records in Odoo based on Shopify data.
            Returns:
                str: Confirmation message indicating the webhook was received or processing failed.
        """
        res, shopify_instance_id = self.check_hook_details('/rcs_shopify_customer_delete_hook')
        if not res:
            return
        try:
            data = res
            # data = {'id': 7683884155085, 'phone': None, 'addresses': [], 'tax_exemptions': [],
            #         'email_marketing_consent': None, 'sms_marketing_consent': None,
            #         'admin_graphql_api_id': 'gid://shopify/Customer/7683885039821'}

            partner_obj = request.env['res.partner'].sudo()
            # connector_obj = request.env['shopify.connector'].sudo()
            # con = connector_obj.browse(17)
            if data:
                partner_obj.archive_customer_by_shopify_id(data, shopify_instance_id)
                # partner_obj.archive_customer_by_shopify_id(data, con)
            return 'Webhook received'
        except Exception as e:
            return 'Webhook processing failed'

    @http.route(['/rcs_shopify_product_create_hook', '/rcs_shopify_product_update_hook'], csrf=False, auth="public", type="json", methods=['POST'])
    def product_create_webhook(self):
        """
            Handle webhook for creating or updating products in Shopify.
            This method processes incoming webhook data to create or update product records in Odoo based on Shopify data.
            Returns:
                str: Confirmation message indicating the webhook was received or processing failed.
        """
        hook_route = request.httprequest.path.split('/')[1]
        res, shopify_instance_id = self.check_hook_details(hook_route)
        if not res:
            return
        try:
            data = res
            # data = {
            #     'admin_graphql_api_id': 'gid://shopify/Product/8884439711949',
            #     'body_html': '',
            #     'created_at': '2024-06-19T03:21:36-04:00',
            #     'handle': 't-shirt',
            #     'id': 8884439711949,
            #     'product_type': 'clothes',
            #     'published_at': '2024-06-19T03:21:36-04:00',
            #     'template_suffix': '',
            #     'title': 'T-Shirt',
            #     'updated_at': '2024-06-25T07:47:55-04:00',
            #     'vendor': 'relodoo',
            #     'status': 'active',
            #     'published_scope': 'global',
            #     'tags': '',
            #     'variants': [
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47752301445325',
            #             'barcode': '',
            #             'compare_at_price': None,
            #             'created_at': '2024-06-19T03:27:28-04:00',
            #             'fulfillment_service': 'manual',
            #             'id': 47752301445325,
            #             'inventory_management': 'shopify',
            #             'inventory_policy': 'deny',
            #             'position': 1,
            #             'price': '100.00',
            #             'product_id': 8884439711949,
            #             'sku': '',
            #             'taxable': True,
            #             'title': 'Long / Black / 1-2 years',
            #             'updated_at': '2024-06-25T07:47:54-04:00',
            #             'option1': 'Long',
            #             'option2': 'Black',
            #             'option3': '1-2 years',
            #             'grams': 10000,
            #             'image_id': 52515724951757,
            #             'weight': 10.0,
            #             'weight_unit': 'kg',
            #             'inventory_item_id': 49830254739661,
            #             'inventory_quantity': 2,
            #             'old_inventory_quantity': 2,
            #             'requires_shipping': True
            #         },
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47752406466765',
            #             'barcode': '',
            #             'compare_at_price': None,
            #             'created_at': '2024-06-19T03:32:36-04:00',
            #             'fulfillment_service': 'manual',
            #             'id': 47752406466765,
            #             'inventory_management': 'shopify',
            #             'inventory_policy': 'deny',
            #             'position': 2,
            #             'price': '100.00',
            #             'product_id': 8884439711949,
            #             'sku': '',
            #             'taxable': True,
            #             'title': 'Long / White / 1-2 years',
            #             'updated_at': '2024-06-25T07:47:54-04:00',
            #             'option1': 'Long',
            #             'option2': 'White',
            #             'option3': '1-2 years',
            #             'grams': 0,
            #             'image_id': None,
            #             'weight': 0.0,
            #             'weight_unit': 'kg',
            #             'inventory_item_id': 49830276858061,
            #             'inventory_quantity': 10,
            #             'old_inventory_quantity': 10,
            #             'requires_shipping': True
            #         },
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47752301478093',
            #             'barcode': '',
            #             'compare_at_price': None,
            #             'created_at': '2024-06-19T03:27:28-04:00',
            #             'fulfillment_service': 'manual',
            #             'id': 47752301478093,
            #             'inventory_management': 'shopify',
            #             'inventory_policy': 'deny',
            #             'position': 3,
            #             'price': '100.00',
            #             'product_id': 8884439711949,
            #             'sku': '',
            #             'taxable': True,
            #             'title': 'Short / Black / 1-2 years',
            #             'updated_at': '2024-06-25T07:47:54-04:00',
            #             'option1': 'Short',
            #             'option2': 'Black',
            #             'option3': '1-2 years',
            #             'grams': 0,
            #             'image_id': None,
            #             'weight': 0.0,
            #             'weight_unit': 'kg',
            #             'inventory_item_id': 49830254772429,
            #             'inventory_quantity': 5,
            #             'old_inventory_quantity': 5,
            #             'requires_shipping': True
            #         },
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47752406499533',
            #             'barcode': '',
            #             'compare_at_price': None,
            #             'created_at': '2024-06-19T03:32:36-04:00',
            #             'fulfillment_service': 'manual',
            #             'id': 47752406499533,
            #             'inventory_management': 'shopify',
            #             'inventory_policy': 'deny',
            #             'position': 4,
            #             'price': '100.00',
            #             'product_id': 8884439711949,
            #             'sku': '',
            #             'taxable': True,
            #             'title': 'Short / White / 1-2 years',
            #             'updated_at': '2024-06-25T07:47:54-04:00',
            #             'option1': 'Short',
            #             'option2': 'White',
            #             'option3': '1-2 years',
            #             'grams': 0,
            #             'image_id': None,
            #             'weight': 0.0,
            #             'weight_unit': 'kg',
            #             'inventory_item_id': 49830276890829,
            #             'inventory_quantity': 29,
            #             'old_inventory_quantity': 29,
            #             'requires_shipping': True
            #         },
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47776457130189',
            #             'barcode': '',
            #             'compare_at_price': None,
            #             'created_at': '2024-06-25T07:47:55-04:00',
            #             'fulfillment_service': 'manual',
            #             'id': 47776457130189,
            #             'inventory_management': 'shopify',
            #             'inventory_policy': 'deny',
            #             'position': 5,
            #             'price': '100.00',
            #             'product_id': 8884439711949,
            #             'sku': '',
            #             'taxable': True,
            #             'title': 'Long / Black / 6-12 months',
            #             'updated_at': '2024-06-25T07:47:55-04:00',
            #             'option1': 'Long',
            #             'option2': 'Black',
            #             'option3': '6-12 months',
            #             'grams': 10000,
            #             'image_id': None,
            #             'weight': 10.0,
            #             'weight_unit': 'kg',
            #             'inventory_item_id': 49841752408269,
            #             'inventory_quantity': 0,
            #             'old_inventory_quantity': 0,
            #             'requires_shipping': True
            #         },
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47776457162957',
            #             'barcode': '',
            #             'compare_at_price': None,
            #             'created_at': '2024-06-25T07:47:55-04:00',
            #             'fulfillment_service': 'manual',
            #             'id': 47776457162957,
            #             'inventory_management': 'shopify',
            #             'inventory_policy': 'deny',
            #             'position': 6,
            #             'price': '100.00',
            #             'product_id': 8884439711949,
            #             'sku': '',
            #             'taxable': True,
            #             'title': 'Long / White / 6-12 months',
            #             'updated_at': '2024-06-25T07:47:55-04:00',
            #             'option1': 'Long',
            #             'option2': 'White',
            #             'option3': '6-12 months',
            #             'grams': 10000,
            #             'image_id': None,
            #             'weight': 10.0,
            #             'weight_unit': 'kg',
            #             'inventory_item_id': 49841752441037,
            #             'inventory_quantity': 0,
            #             'old_inventory_quantity': 0,
            #             'requires_shipping': True
            #         },
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47776457195725',
            #             'barcode': '',
            #             'compare_at_price': None,
            #             'created_at': '2024-06-25T07:47:55-04:00',
            #             'fulfillment_service': 'manual',
            #             'id': 47776457195725,
            #             'inventory_management': 'shopify',
            #             'inventory_policy': 'deny',
            #             'position': 7,
            #             'price': '100.00',
            #             'product_id': 8884439711949,
            #             'sku': '',
            #             'taxable': True,
            #             'title': 'Short / Black / 6-12 months',
            #             'updated_at': '2024-06-25T07:47:55-04:00',
            #             'option1': 'Short',
            #             'option2': 'Black',
            #             'option3': '6-12 months',
            #             'grams': 10000,
            #             'image_id': None,
            #             'weight': 10.0,
            #             'weight_unit': 'kg',
            #             'inventory_item_id': 49841752473805,
            #             'inventory_quantity': 0,
            #             'old_inventory_quantity': 0,
            #             'requires_shipping': True
            #         },
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47776457228493',
            #             'barcode': '',
            #             'compare_at_price': None,
            #             'created_at': '2024-06-25T07:47:55-04:00',
            #             'fulfillment_service': 'manual',
            #             'id': 47776457228493,
            #             'inventory_management': 'shopify',
            #             'inventory_policy': 'deny',
            #             'position': 8,
            #             'price': '100.00',
            #             'product_id': 8884439711949,
            #             'sku': '',
            #             'taxable': True,
            #             'title': 'Short / White / 6-12 months',
            #             'updated_at': '2024-06-25T07:47:55-04:00',
            #             'option1': 'Short',
            #             'option2': 'White',
            #             'option3': '6-12 months',
            #             'grams': 10000,
            #             'image_id': None,
            #             'weight': 10.0,
            #             'weight_unit': 'kg',
            #             'inventory_item_id': 49841752506573,
            #             'inventory_quantity': 0,
            #             'old_inventory_quantity': 0,
            #             'requires_shipping': True
            #         }
            #     ],
            #     'options': [
            #         {
            #             'name': 'Sleeve length type',
            #             'id': 11355674837197,
            #             'product_id': 8884439711949,
            #             'position': 1,
            #             'values': [
            #                 'Long',
            #                 'Short'
            #             ]
            #         },
            #         {
            #             'name': 'Color',
            #             'id': 11355677032653,
            #             'product_id': 8884439711949,
            #             'position': 2,
            #             'values': [
            #                 'Black',
            #                 'White'
            #             ]
            #         },
            #         {
            #             'name': 'Age group',
            #             'id': 11364566139085,
            #             'product_id': 8884439711949,
            #             'position': 3,
            #             'values': [
            #                 '1-2 years',
            #                 '6-12 months'
            #             ]
            #         }
            #     ],
            #     'images': [
            #         {
            #             'id': 52515724951757,
            #             'product_id': 8884439711949,
            #             'position': 1,
            #             'created_at': '2024-06-19T06:07:58-04:00',
            #             'updated_at': '2024-06-19T06:09:06-04:00',
            #             'alt': None,
            #             'width': 430,
            #             'height': 399,
            #             'src': 'https://cdn.shopify.com/s/files/1/0638/6712/5965/files/istockphoto-483960103-170667a.webp?v=1718791679',
            #             'variant_ids': [
            #                 47752301445325
            #             ],
            #             'admin_graphql_api_id': 'gid://shopify/ProductImage/52515724951757'
            #         }
            #     ],
            #     'image': {
            #         'id': 52515724951757,
            #         'product_id': 8884439711949,
            #         'position': 1,
            #         'created_at': '2024-06-19T06:07:58-04:00',
            #         'updated_at': '2024-06-19T06:09:06-04:00',
            #         'alt': None,
            #         'width': 430,
            #         'height': 399,
            #         'src': 'https://cdn.shopify.com/s/files/1/0638/6712/5965/files/istockphoto-483960103-170667a.webp?v=1718791679',
            #         'variant_ids': [
            #             47752301445325
            #         ],
            #         'admin_graphql_api_id': 'gid://shopify/ProductImage/52515724951757'
            #     },
            #     'variant_gids': [
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47776457130189',
            #             'updated_at': '2024-06-25T11:47:55.000Z'
            #         },
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47776457162957',
            #             'updated_at': '2024-06-25T11:47:55.000Z'
            #         },
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47776457195725',
            #             'updated_at': '2024-06-25T11:47:55.000Z'
            #         },
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47776457228493',
            #             'updated_at': '2024-06-25T11:47:55.000Z'
            #         },
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47752301445325',
            #             'updated_at': '2024-06-25T11:47:54.000Z'
            #         },
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47752406466765',
            #             'updated_at': '2024-06-25T11:47:54.000Z'
            #         },
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47752301478093',
            #             'updated_at': '2024-06-25T11:47:54.000Z'
            #         },
            #         {
            #             'admin_graphql_api_id': 'gid://shopify/ProductVariant/47752406499533',
            #             'updated_at': '2024-06-25T11:47:54.000Z'
            #         }
            #     ]
            # }

            product_tem_obj = request.env['product.template'].sudo()
            # connector_obj = request.env['shopify.connector'].sudo()
            # con = connector_obj.browse(17)
            if data:
                product_tem_obj._create_or_update_product(data, shopify_instance_id)
                # product_tem_obj._create_or_update_product(data, con)
            return 'Webhook received'
        except Exception as e:
            return 'Webhook processing failed'

    @http.route(['/rcs_shopify_product_delete_hook'], csrf=False, auth="public", type="json", methods=['POST'])
    def product_delete_webhook(self):
        """
            Handle webhook for deleting products in Shopify.
            This method processes incoming webhook data to delete product records in Odoo based on Shopify data.
            Returns:
                str: Confirmation message indicating the webhook was received or processing failed.
        """
        res, shopify_instance_id = self.check_hook_details('/rcs_shopify_product_delete_hook')
        if not res:
            return
        try:
            data = res
            # data = {'id': 8891545977037}

            product_tem_obj = request.env['product.template'].sudo()
            # connector_obj = request.env['shopify.connector'].sudo()
            # con = connector_obj.browse(17)
            if data:
                product_tem_obj.archive_by_shopify_product_id(data, shopify_instance_id)
                # product_tem_obj.archive_by_shopify_product_id(data, con)
            return 'Webhook received'
        except Exception as e:
            return 'Webhook processing failed'

    @http.route(['/rcs_shopify_order_create_hook', '/rcs_shopify_order_update_hook'], csrf=False, auth="public", type="json", methods=['POST'])
    def order_create_webhook(self):
        """
            Handle webhook for creating or updating orders in Shopify.
            This method processes incoming webhook data to create or update order records in Odoo based on Shopify data.
            Returns:
                str: Confirmation message indicating the webhook was received or processing failed.
        """
        hook_route = request.httprequest.path.split('/')[1]
        res, shopify_instance_id = self.check_hook_details(hook_route)
        if not res:
            return
        try:
            data = res
            sale_obj = request.env['sale.order'].sudo()
            # connector_obj = request.env['shopify.connector'].sudo()
            # con = connector_obj.browse(17)
            if data:
                # partner_obj.archive_by_shopify_product_id(data, shopify_instance_id)
                sale_obj._create_or_update_orders(data, shopify_instance_id)
            return 'Webhook received'
        except Exception as e:
            return 'Webhook processing failed'
