# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

import logging
import mysql.connector
from mysql.connector import Error
import json
import requests
import traceback
import mimetypes
import datetime
import pytz
_logger = logging.getLogger(__name__)

from odoo.exceptions import UserError, ValidationError


def get_create_by(created_by_result):
    if not created_by_result or len(created_by_result) == 0:
        raise UserError("Your account does not exist in beta")
    else:
        return created_by_result[0]

def get_beta_customer_master_id(customer_master_result):
    if not customer_master_result or len(customer_master_result) ==0:
        raise UserError("Master customer for this branch does not exist in beta")
    else:
        return customer_master_result[0][0], customer_master_result[0][1]

def get_beta_customer_id_and_status(customer_id_result):
    if not customer_id_result or len(customer_id_result) == 0:
        raise UserError("This branch has not been created in beta")
    else:
        return customer_id_result[0][0], customer_id_result[0][1]


def get_beta_godown_id(godown_result):
    if not godown_result or len(godown_result) == 0:
        raise UserError("Either of billing or parent godown is not present in beta")
    else:
        return godown_result[0]


def get_quotation_insert_query():
    return "INSERT INTO quotations (created_by, customer_id, contact_name, phone_number, site_name, price_type, total, freight, gstn, billing_address_line, billing_address_city, billing_address_pincode, delivery_address_line, delivery_address_city, delivery_address_pincode, delivery_date, pickup_date, security_amt, freight_payment, godown_id, crm_account_id,computed_freight_amount,overidden_freight,computed_vehicle_type, created_at, updated_at) VALUES (%(created_by)s, %(customer_id)s, %(contact_name)s, %(phone_number)s, %(site_name)s, %(price_type)s, %(total)s, %(freight)s, %(gstn)s, %(billing_address_line)s, %(billing_address_city)s, %(billing_address_pincode)s, %(delivery_address_line)s, %(delivery_address_city)s, %(delivery_address_pincode)s, %(delivery_date)s, %(pickup_date)s, %(security_amt)s, %(freight_payment)s, %(godown_id)s, %(crm_account_id)s,%(computed_freight_amount)s,%(overidden_freight)s,%(computed_vehicle_type)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"


def get_quotation_items_insert_query():
    return "INSERT INTO quotation_items (quotation_id, item_code, unit_price, quantity, created_at, updated_at) " \
           "VALUES (%(quotation_id)s, %(item_code)s, %(unit_price)s, %(quantity)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) " \
           "ON DUPLICATE KEY UPDATE " \
           "item_code = VALUES(item_code), unit_price = VALUES(unit_price), " \
           "quantity = VALUES(quantity), updated_at = CURRENT_TIMESTAMP"

def get_quotation_items_log_insert_query():
    return "INSERT INTO quotation_items_log (quotation_id, item_code, unit_price, quantity, created_at, updated_at) VALUES (%(quotation_id)s, %(item_code)s, %(unit_price)s, %(quantity)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"




def get_beta_user_id_from_email_query():
    return "select id from users where LOWER(email) = %s"

def get_customer_master_id_from_pan():
    return "select id, status from customer_masters where UPPER(pan) = %s"

def get_beta_customer_id_from_gstn():
    return "select id, status from customers where UPPER(gstn) = %s"


def get_beta_customer_id_for_non_gst_customer():
    return "select customers.id as id, customers.status as status from customers, customer_masters where customer_masters.id = customers.customer_master_id and customer_masters.pan = %s limit 1"

def get_beta_branch_form_gstn_query():
    return "select id from customers where UPPER(gstn) = %s"


def get_location_insert_query():
    return "INSERT INTO locations (location_name, type, state_code) VALUES (%s, 'job_order', %s)"


def get_state_code_from_state_alpha_query(state_code):
    return "SELECT state_code FROM states WHERE state_alpha = '{}'".format(state_code)


def get_order_insert_query():
    return ("INSERT INTO orders (quotation_id, customer_id, job_order, po_no, place_of_supply, gstn, security_cheque, "
            "rental_advance, rental_order, godown_id, billing_godown, created_by, total, is_authorized, created_at, "
            "updated_at, crm_account_id, po_status, po_stage) "
            "VALUES (%(quotation_id)s, %(customer_id)s, %(job_order)s, %(po_no)s, %(place_of_supply)s, %(gstn)s, "
            "%(security_cheque)s, %(rental_advance)s, %(rental_order)s, %(godown_id)s, %(billing_godown)s, "
            "%(created_by)s, %(total)s, %(is_authorized)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %(crm_account_id)s, "
            "%(po_status)s, %(po_stage)s)")

def _get_cheque_details_insert_query():
    return "INSERT INTO customer_security_cheque (customer_id, order_id, cheque_no, cheque_amount, cheque_date,bank, lapsed, verified, cheque_ownership, security_cheque) VALUES(%(customer_id)s, %(order_id)s, %(cheque_no)s, %(cheque_amount)s, %(cheque_date)s, %(bank)s, %(lapsed)s, %(verified)s, %(cheque_ownership)s, %(security_cheque)s)"

def _get_contact_notification_insert_query():
    return """
    INSERT INTO order_contact_notification (order_id, contact_crm_id)
    SELECT %(order_id)s, %(contact_crm_id)s
    WHERE NOT EXISTS (
        SELECT 1 FROM order_contact_notification 
        WHERE order_id = %(order_id)s AND contact_crm_id = %(contact_crm_id)s
    )
    """

def get_beta_godown_id_by_name_query(godown_name):
    return "SELECT id from locations where type='godown' and location_name = '{}'".format(godown_name)


def get_update_quotation_with_order_query():
    return "UPDATE quotations set order_id = %s, converted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP where id = %s"


def get_challan_remarks_history():
    return "INSERT INTO challan_remark_history (order_id, challan_id, user_id, remark, remarks_date) VALUES (%s, 'Initial Order', %s, %s, CURRENT_TIMESTAMP)"

def get_order_po_insert_query():
    return "INSERT INTO order_po(order_id, po_no, po_amt, balance) VALUES (%s, %s, %s, %s)"

def get_order_po_details_insert_query():
    return "INSERT INTO order_po_details(order_id, po_no, po_date , item_code , quantity) VALUES (%(order_id)s,%(po_no)s,%(po_date)s,%(item_code)s,%(quantity)s)"


def get_order_item_feed_insert_query():
    return "INSERT INTO order_item_feed(job_order, item_code, quantity) VALUES (%(job_order)s, %(item_code)s, %(quantity)s)" \
           "ON DUPLICATE KEY UPDATE " \
           "quantity = VALUES(quantity)"



def get_billing_process_insert_query():
    return "insert into billing_process (order_id, odoo_site_contact, odoo_office_contact, bill_submission_location, site_address, site_pincode, office_address, office_pincode, process) " \
           "VALUES (%(order_id)s, %(odoo_site_contact)s,%(odoo_office_contact)s,%(bill_submission_location)s,%(site_address)s,%(site_pincode)s,%(office_address)s,%(office_pincode)s,%(process)s)"


def _concatenate_address_string(address_strings):
    arr = [x for x in address_strings if x]
    return ', '.join(map(str, arr))


def _get_order_item_feed_details_amend_order(job_order, odoo_quotation_items, existing_quantity_at_beta, existing_order_item_feed):
    item_feed_details = []

    for oddo_item in odoo_quotation_items:
        found_existing_item = False
        for existing_item_quantity_at_quotation in existing_quantity_at_beta:
            for existing_item_quantity_at_order_item_feed in existing_order_item_feed:
                if (oddo_item['item_code'] == existing_item_quantity_at_quotation[0]) and (existing_item_quantity_at_order_item_feed[0] == oddo_item['item_code']):
                    quantity = oddo_item['quantity'] - existing_item_quantity_at_quotation[1] + existing_item_quantity_at_order_item_feed[1]

                    if quantity < 0:
                        raise Exception('Cannot Amend Less Than Material To Be Sent')

                    item_feed_details.append({
                        'job_order': job_order,
                        'item_code': oddo_item['item_code'],
                        'quantity': quantity,
                    })
                    found_existing_item = True
                    break

            if found_existing_item:
                break

        if not found_existing_item:
            item_feed_details.append({
                'job_order': job_order,
                'item_code': oddo_item['item_code'],
                'quantity': oddo_item['quantity'],
            })

    return item_feed_details


def _get_order_item_feed_details(job_order, quotation_items):
    item_feed_details = []
    for item in quotation_items:
        item_feed_details.append({
            'job_order': job_order,
            'item_code': item['item_code'],
            'quantity': item['quantity'],
        })
    return item_feed_details

def _get_beta_compatible_freight_type(freight_type):
    frieght_map = {
        'freight_type1': 'It has been agreed 1st Dispatch and final Pickup will be done by Youngman',
        'freight_type2': 'It has been agreed 1st Dispatch and final Pickup will be done by Customer'
    }

    return frieght_map.get(freight_type)

class SaleAdvancePaymentInvInheit(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def create_invoices(self):
        try:
            sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
            for order in sale_orders:
                _logger.info("evt=CREATE_INVOICE msg=Job Order" + order.job_order)

                payment_reciept = self.env['ir.attachment'].sudo().search(
                    [('res_model', '=', 'sale.order'), ('res_field', '=', 'payment_reciept'), ('res_id', '=', order.id),
                     ('type', '=', 'url')])

                if not payment_reciept['url']:
                    raise UserError("Payment Reciept is required for creating invoice.")

                payload = json.dumps({
                    "invoice": [
                        {
                            "job_order": order.job_order,
                            "invoice_type": order.order_type,
                            "payment_reciept_url": payment_reciept.url if payment_reciept.url else ""
                        }
                    ]
                })
                invoice_save_endpoint = "https://youngmanbeta.com/createSaleInvoice"
                response = requests.request("POST", invoice_save_endpoint, headers={'Content-Type': 'application/json'},
                                            data=payload, verify=False)
                response.raise_for_status()

            return super(SaleAdvancePaymentInvInheit, self).create_invoices()
        except requests.HTTPError as e:
            error_msg = _(
                "Remote server returned status " + e.response.status_code + "with message " + e.response.reason)
            raise self.env['res.config.settings'].get_config_warning(error_msg)
        except Exception as e:
            error_msg = _(str(e))
            raise self.env['res.config.settings'].get_config_warning(error_msg)
        finally:
            _logger.error(traceback.format_exc())

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    beta_order_id = fields.Integer(string = "Beta Order Id")
    
    def action_amend(self, vals,po_details= None):
        try:

            connection = self._get_connection()
            connection.autocommit = False
            cursor = connection.cursor()

            self._validate_if_amendment_allowed(vals)
            quotation_id = (self.job_order.split('/')[-1])
            amendment_details = self._get_amendment_details(vals)
            cursor.execute("INSERT INTO amend_order_log (order_id, freight, amendment_doc, po_no, is_amended) VALUES (%(order_id)s, %(freight)s, %(amendment_doc)s, %(po_no)s, %(is_amended)s)", amendment_details)
            cursor.execute("SELECT LAST_INSERT_ID()")
            last_amend_order_log_id = cursor.fetchone()[0]
            existing_quotation_items_at_beta = cursor.execute("SELECT item_code , quantity FROM quotation_items WHERE quotation_id = %s",(quotation_id,))
            existing_quotation_items_at_beta = cursor.fetchall()
            existing_order_item_feed = cursor.execute("SELECT item_code , quantity FROM order_item_feed WHERE job_order = %s",(self.job_order,))
            existing_order_item_feed = cursor.fetchall()

            quotation_items = []
            for order_line in vals.get('amend_order_line_ids', []):
                data_dict = order_line[2]
                action_to_perform = order_line[0]

                if action_to_perform in [0,1]:

                    if action_to_perform == 0:
                        # Create new
                        item_code = self.env['product.product'].search([('id', '=', data_dict.get('product_id'))]).default_code
                        unit_price = data_dict.get('price_unit')
                        quantity = data_dict.get('product_uom_qty')
                    else:
                        # update existing
                        existing_order_line = self.env['sale.order.line'].search([('id', '=', order_line[1])])
                        item_code = existing_order_line.product_id.code
                        unit_price = data_dict.get('price_unit', existing_order_line.price_unit)
                        quantity = data_dict.get('product_uom_qty', existing_order_line.product_uom_qty)



                    cursor.execute(
                        "INSERT INTO amend_order_log_details (amend_order_log_id, order_id, item_code, unit_price, quantity) "
                        "VALUES (%(amend_order_log_id)s, %(order_id)s, %(item_code)s, %(unit_price)s, %(quantity)s)", {
                                'amend_order_log_id': last_amend_order_log_id,
                                'order_id': self.beta_order_id,
                                'item_code': item_code,
                                'unit_price': unit_price,
                                'quantity': quantity
                            })

                    _logger.info("evt=AMMEND_ORDER_TO_BETA msg=Trying to save quoataion items")

                    quotation_items.append({
                        'quotation_id': self.job_order.split("/")[-1],
                        'item_code': item_code,
                        'unit_price': unit_price,
                        'quantity': quantity
                    })



            cursor.executemany(get_quotation_items_insert_query(), quotation_items)
            _logger.info("evt=AMMEND_ORDER_TO_BETA msg=Quotation items saved")

            _logger.info("evt=AMMEND_ORDER_TO_BETA msg=Insert into order item feed")
            item_feed_details = _get_order_item_feed_details_amend_order(self.job_order, quotation_items, existing_quotation_items_at_beta, existing_order_item_feed)
            for item_detail in item_feed_details:
                cursor.execute(get_order_item_feed_insert_query(), item_detail)
            _logger.info("evt=AMMEND_ORDER_TO_BETA msg=Order item feed saved")


            _logger.info("evt=AMMEND_ORDER_TO_BETA msg=Trying to save quoataion items log")
            quotation_items_log = self._get_quotation_items_details_for_amend(quotation_id,quotation_items,existing_quotation_items_at_beta)
            cursor.executemany(get_quotation_items_log_insert_query(), quotation_items_log)
            _logger.info("evt=AMMEND_ORDER_TO_BETA msg = Quotation items log saved")


            get_order_realese_status = cursor.execute("SELECT released_at FROM orders WHERE quotation_id = %s",(quotation_id,))
            get_order_realese_status = cursor.fetchall()
            if get_order_realese_status[0][0] is not None:
                cursor.execute("UPDATE orders SET released_at = NULL WHERE quotation_id = %s", (quotation_id,))


            self.freight_amount += vals['additional_freight'] if 'additional_freight' in vals else 0
            vals['additional_freight'] = 0

            if self.po_available and po_details and po_details.po_details_po_status == 'approved':
                self.env['sale.po.details']._send_po_details_to_beta(po_details,'AMEND')
            elif self.po_available and po_details and po_details.po_details_po_status != 'approved':
                 po_details.po_details_po_status = 'pending'
                 self.env['sale.po.details']._send_po_status(po_details)

            connection.commit()
        except Error as err:
            _logger.error("evt=ORDER_CANNOT_BE_AMENDED msg=", exc_info=1)
            connection.rollback()
            raise UserError(_(err))
        except Exception as e:
            connection.rollback()
            raise UserError(_(e))

    def _validate_if_amendment_allowed(self, vals):
        not_allowed_actions = [2, 5, 6, 3]
        for order_line in vals.get('order_line', []):
            if order_line[0] in not_allowed_actions:
                raise UserError(_('You Cannot Delete an existing item'))

    def _get_amendment_details(self, vals):
        amendment_details = {
            'order_id': self.beta_order_id,
            'freight': vals['additional_freight'] if 'additional_freight' in vals else 0,
            'amendment_doc': self._get_document_if_exists('rental_order'),
            'po_no': vals['po_number'] if 'po_number' in vals else False,
            'is_amended': 1
        }
        return amendment_details

    # data_dict.get('price_unit', order_line.price_unit)

    def action_extend(self):
        try:
            connection = self._get_connection()
            connection.autocommit = False
            cursor = connection.cursor()

            _logger.info("evt=EXTEND_ORDER msg=Saving PO data")

            cursor.execute("INSERT INTO extensions (order_id, old_rental_order) SELECT id as order_id, rental_order as old_rental_order FROM orders WHERE id = %s",(self.beta_order_id,))
            cursor.execute("UPDATE quotations SET pickup_date=%s WHERE order_id=%s",(self.pickup_date, self.beta_order_id))
            cursor.execute("UPDATE orders SET rental_order = %s WHERE id = %s",[self._get_document_if_exists('rental_order'), self.beta_order_id])
            cursor.execute("UPDATE challans SET deleted_at = current_timestamp WHERE deleted_at IS NULL AND challan_type = 'Pickup' AND challans.recieving IS NULL AND order_id = %s",(self.beta_order_id,))
            connection.commit()

        except Error as err:
            _logger.error("evt=SEND_ORDER_TO_BETA msg=", exc_info=1)
            connection.rollback()
            raise UserError(_(err))
        except Exception as e:
            connection.rollback()
            raise UserError(_(e))

    def action_confirm(self):
        if self.is_sale_order_approval_required:
           result = super(SaleOrderInherit, self).action_confirm()
           return result
        self._validate_order_before_confirming()

        self.env['customer.to.beta']._create_customer_in_beta_if_not_exists(self.partner_id)
        self._create_branch_in_beta_if_not_exists() #For branches that were added post initial customer creation

        try:
            connection = self._get_connection()
            connection.autocommit = False
            cursor = connection.cursor()
            email = self.partner_id.user_id.email.lower()

            if self.partner_id.team_id.name == 'INSIDE SALES':
                created_by = 568
            else:
                _logger.info("evt=SEND_ORDER_TO_BETA msg=Get created by from beta")
                cursor.execute(get_beta_user_id_from_email_query(), [email])
                created_by = get_create_by(cursor.fetchone())

            cheque_ownership = created_by

            _logger.info("evt=SEND_ORDER_TO_BETA msg=Get customer id from beta")

            if self.partner_id.is_non_gst_customer:
                cursor.execute(get_beta_customer_id_for_non_gst_customer(), [self.partner_id.vat])
            else:
                cursor.execute(get_beta_customer_id_from_gstn(), [self.customer_branch.gstn])
            customer_id, status = get_beta_customer_id_and_status(cursor.fetchall())

            if status != 'UNBLOCK':
                raise UserError("This customer is in {} status".format(status))

            cursor.execute(get_customer_master_id_from_pan(), [self.partner_id.vat])
            _, customer_master_status = get_beta_customer_master_id(cursor.fetchall())

            if customer_master_status != 'UNBLOCK':
                raise UserError("This customer master is in {} status".format(customer_master_status))

            _logger.info("evt=SEND_ORDER_TO_BETA msg=Get billing godown id from beta")
            cursor.execute(get_beta_godown_id_by_name_query(self.bill_godown.name))
            beta_bill_godown_id = get_beta_godown_id(cursor.fetchone())

            _logger.info("evt=SEND_ORDER_TO_BETA msg=Get parent godown id from beta")
            cursor.execute(get_beta_godown_id_by_name_query(self.godown.name))
            beta_godown_id = get_beta_godown_id(cursor.fetchone())

            _logger.info("evt=SEND_ORDER_TO_BETA msg=Trying to save quotation")
            quotation_total = self._get_quotation_total()
            quotation = self._get_quotation_data(created_by, customer_id, beta_godown_id, quotation_total)
            cursor.execute(get_quotation_insert_query(), quotation)
            quotation_id = cursor.lastrowid
            _logger.info("evt=SEND_ORDER_TO_BETA msg=Quotation saved with id" + str(quotation_id))

            _logger.info("evt=SEND_ORDER_TO_BETA msg=Trying to save quoataion items")
            quotation_items = self._get_quotation_items_and_total(quotation_id)
            cursor.executemany(get_quotation_items_insert_query(), quotation_items)
            _logger.info("evt=SEND_ORDER_TO_BETA msg=Quotation items saved")

            _logger.info("evt=SEND_ORDER_TO_BETA msg=Trying to save quoataion items_log")
            quotation_items_log = self._get_quotation_items_and_total(quotation_id)
            cursor.executemany(get_quotation_items_log_insert_query(), quotation_items_log)
            _logger.info("evt=SEND_ORDER_TO_BETA msg=Quotation items log saved")

            _logger.info("evt=SEND_ORDER_TO_BETA msg=Generating job order number")
            job_order_number = self._generate_job_number(created_by, customer_id, quotation_id)
            self.job_order = job_order_number
            self.name = job_order_number

            _logger.info("evt=SEND_ORDER_TO_BETA msg=Get Place of supply code from beta query=" + get_state_code_from_state_alpha_query(self.place_of_supply.code))
            cursor.execute(get_state_code_from_state_alpha_query(self.place_of_supply.code))

            _logger.info("evt=SEND_ORDER_TO_BETA msg=Trying to create job order location")
            place_of_supply_code = cursor.fetchone()[0]
            cursor.execute(get_location_insert_query(), (job_order_number, place_of_supply_code))
            location_id = cursor.lastrowid
            _logger.info("evt=SEND_ORDER_TO_BETA msg=Location created with id" + str(location_id))

            _logger.info("evt=SEND_ORDER_TO_BETA msg=Trying to create order")
            order_data = self._get_order_data(created_by, customer_id, quotation_id, quotation_total, job_order_number,
                                              place_of_supply_code, beta_bill_godown_id, beta_godown_id, "0")
            cursor.execute(get_order_insert_query(), order_data)
            order_id = cursor.lastrowid

            self.beta_order_id = order_id
            # order
            _logger.info("evt=SEND_ORDER_TO_BETA msg=Order saved with id" + str(order_id))

            try:
                cursor.executemany(_get_contact_notification_insert_query(), self._get_contacts_to_notify(order_id))
                _logger.info("evt=SEND_ORDER_TO_BETA msg=Saved contacts to notify")
            except Error as err:
                _logger.error("evt=SEND_ORDER_TO_BETA msg="+str(err))

            if self.security_cheque:
                cursor.execute(_get_cheque_details_insert_query(), self._get_security_cheque_data(customer_id, order_id, cheque_ownership))

            # _logger.info("evt=SEND_ORDER_TO_BETA msg=Saving PO data")
            # cursor.execute(get_order_po_insert_query(), (order_id, self.po_number, self.total_po_amount, self.total_po_amount))
            # po_details = self._generate_po_details(order_id, quotation_items)
            #
            # _logger.info("evt=SEND_ORDER_TO_BETA msg=Saving PO details")
            # cursor.executemany(get_order_po_details_insert_query(), po_details)

            billing_process_data = self._get_billing_process_data(order_id, location_id)
            query = get_billing_process_insert_query()
            _logger.info(
                "evt=SEND_ORDER_TO_BETA msg=Saving Bill Submission details " + str(billing_process_data) + " query=")
            cursor.execute(query, billing_process_data)

            if self._is_to_be_auto_approved():
                _logger.info("evt=SEND_ORDER_TO_BETA msg=Updating quotation with order id and authorising it")
                cursor.execute(get_update_quotation_with_order_query(), (order_id, quotation_id))
                cursor.execute("UPDATE orders SET is_authorized = 1 WHERE id =" + str(order_id))

                _logger.info("evt=SEND_ORDER_TO_BETA msg=insert into order item feed")
                cursor.executemany(get_order_item_feed_insert_query(),
                                   _get_order_item_feed_details(job_order_number, quotation_items))

            if self.remark:
                _logger.info("evt=SEND_REMARKS_TO_BETA msg=Updating challan remarks history")
                cursor.execute(get_challan_remarks_history(), (self.beta_order_id, created_by, self.remark))

            super(SaleOrderInherit, self).action_confirm()

            try:
                planning = self.env['res.partner'].search([('email','=','planning@youngman.co.in')],limit=1)
                message = "A new order has been added for {} on {}. Please plan the delivery. Youngman India Pvt. Ltd.".format(self.job_order.split('/')[-1], self._get_current_date_time())
                self.env['ym.sms'].send_sms(planning, message)
            except Exception as e:
                _logger.error("evt=SEND_SMS msg=" + _(e))

            cursor.close()
            connection.commit()
            self._send_po_details_for_not_a_type()


        except UserError as ue:
            connection.rollback()
            raise ue
        except Error as err:
            _logger.error("evt=SEND_ORDER_TO_BETA msg=", exc_info=1)
            connection.rollback()
            raise UserError(_(err))
        except Exception as e:
            _logger.error("evt=SEND_ORDER_TO_BETA msg=", exc_info=1)
            connection.rollback()
            raise UserError(_(e))


    def _send_po_details_for_not_a_type(self):
        if self.po_details and self.po_available:
            self.env['sale.po.details']._send_po_details_to_beta(self.po_details,'ORDER')
        if not self.po_available:
            self.po_details.po_details_po_status = 'po_promise'
            self.env['sale.po.details']._send_mail_to_users(self.po_details)

    def _get_current_date_time(self):
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.datetime.now(ist)
        current_time = now.strftime("%I:%M:%S %p")
        return current_time

    def _get_contacts_to_notify(self, order_id):
        return [
            {'contact_crm_id': self.purchaser_name.id, 'order_id': order_id},
            {'contact_crm_id': self.site_contact_name.id, 'order_id': order_id},
            {'contact_crm_id': self.project_manager.id, 'order_id': order_id}
        ]



    def _create_branch_in_beta_if_not_exists(self):
        cursor = None
        try:
            # if self.partner_id.is_non_gst_customer:
            #    return

            connection = self._get_connection()
            cursor = connection.cursor()
            if not self.customer_branch.in_beta:
                if self.check_existing_customer_beta(self.customer_branch.gstn):
                    self.customer_branch.in_beta = True
                else:
                    user_email = self.partner_id.user_id.login
                    cursor.execute(get_customer_master_id_from_pan(), [self.partner_id.vat])
                    customer_master_id, _ = get_beta_customer_master_id(cursor.fetchall())
                    branch_data = self.env['customer.to.beta']._get_branch_data_for_saving_in_beta(self.customer_branch, user_email, customer_master_id)

                    beta_branch_save_endpoint = self._get_branch_creation_endpoint()

                    response = requests.request("POST", beta_branch_save_endpoint, headers={'Content-Type': 'application/json'}, data=json.dumps(branch_data), verify=False)
                    response.raise_for_status()

                    if not response.ok:
                        raise UserError(_("Unable to save customer branch in beta."))
                    else:
                        self.customer_branch.in_beta = True
        except requests.exceptions.HTTPError as errh:
            raise UserError("Http Error:" + _(errh))
        except requests.exceptions.ConnectionError as errc:
            raise UserError("Error Connecting:" + _(errc))
        except requests.exceptions.Timeout as errt:
            raise UserError("Timeout Error:" + _(errt))
        except requests.exceptions.RequestException as err:
            raise UserError("OOps:" + _(err))
        except Error as e:
            raise UserError(_(e))
        finally:
            if cursor is not None:
                cursor.close()

    def _get_branch_creation_endpoint(self):
        beta_branch_save_endpoint = self.env['ir.config_parameter'].sudo().get_param(
            'ym_beta_updates.beta_branch_save_endpoint')
        if not beta_branch_save_endpoint:
            raise UserError(
                _("Beta save customer branch endpoint is not configured. Please reach out to system admins."))
        return beta_branch_save_endpoint

    def _is_to_be_auto_approved(self):
        if self.partner_id.team_id.name == "PAM" and self.partner_id.credit_rating in ['A', 'B']:
            _logger.info("evt=SEND_ORDER_TO_BETA msg=Order will be auto approved")
            return True
        return False

    def _get_billing_process_data(self, order_id, location_id):
        billing_process_data = {
            'order_id': order_id,
            'odoo_site_contact': self.bill_site_contact.id,
            'odoo_office_contact': self.bill_office_contact.id,
            'bill_submission_location': location_id,
            'site_address': _concatenate_address_string([
                self.delivery_street,
                self.delivery_street2,
                self.delivery_city,
                self.delivery_state_id.name if self.delivery_state_id else False]),
            'site_pincode': self.delivery_zip,
            'office_address': _concatenate_address_string([
                self.bill_submission_office_branch.street,
                self.bill_submission_office_branch.street2,
                self.bill_submission_office_branch.city,
                self.bill_submission_office_branch.state_id.name if self.bill_submission_office_branch.state_id else False]),
            'office_pincode': self.bill_submission_office_branch.zip,
            'process': self.partner_id.bill_submission_process.name
        }
        return billing_process_data

    def _generate_po_details(self, order_id, quotation_items):
        po_details = []

        if self.po_number:
            for item in quotation_items:
                po_details.append({
                    'order_id': order_id,
                    'po_no': self.po_number,
                    'po_date': self.po_date.strftime('%Y-%m-%d'),
                    'po_amount': self.total_po_amount,
                    'item_code': item['item_code'],
                    'quantity': item['quantity'],
                })
        return po_details

    def _get_quotation_total(self):
        quotation_total = 0
        for order_line in self.order_line:
            quotation_total = quotation_total + (order_line.price_unit * order_line.product_uom_qty)
        return quotation_total

    def _get_quotation_items_and_total(self, quotation_id, amend_order_line = None):
        quotation_items = []
        if len(self.order_line) == 0:
            raise UserError("Please select quotation items.")

        for order_line in self.order_line:
            quotation_items.append({
                'quotation_id': quotation_id,
                'item_code': order_line.product_id.default_code,
                'unit_price': order_line.price_unit,
                'quantity': order_line.product_uom_qty
            })
        return quotation_items

    def _get_quotation_items_details_for_amend(self, quotation_id,quotation_items,existing_quotation_items_at_beta) :
        difference_quotation_items_log = []

        for odoo_item in quotation_items:
            for existing_quotation_item in existing_quotation_items_at_beta:
                if odoo_item['item_code'] == existing_quotation_item[0]:
                    difference_quotation_items_log.append({
                        'quotation_id': quotation_id,
                        'item_code': odoo_item['item_code'],
                        'unit_price': odoo_item['unit_price'],
                        'quantity': odoo_item['quantity'] - existing_quotation_item[1]
                    })
                    break

            else:
                difference_quotation_items_log.append({
                    'quotation_id': quotation_id,
                    'item_code': odoo_item['item_code'],
                    'unit_price': odoo_item['unit_price'],
                    'quantity': odoo_item['quantity']
                })


        return difference_quotation_items_log


    def _validate_order_before_confirming(self):
        if  self.order_type == 'Rental':
            if self.tentative_quo:
                raise ValidationError(_("Confirmation of tentative quotation is not allowed"))
            if self.po_available:
                if not self.po_number:
                    raise ValidationError(_('PO Number is mandatory for confirming a quotation'))
                if not self.total_po_amount:
                    raise ValidationError(_('PO Amount is mandatory for confirming a quotation'))
                if not self.po_date:
                    raise ValidationError(_('PO Date is mandatory for confirming a quotation'))
            if not self.place_of_supply:
                raise ValidationError(_('Place of Supply is mandatory for confirming a quotation'))
            if not self.rental_order and self.partner_id.rental_order is True:
                raise ValidationError(_('Rental Order is mandatory for this customer'))
            if not self.rental_advance and self.partner_id.rental_advance is True:
                raise ValidationError(_('Rental Advance is mandatory for this customer'))
            if not self.security_cheque and self.partner_id.security_cheque is True:
                raise ValidationError(_('Security Cheque is mandatory for this customer'))
            if not self.partner_id.vat:
                raise ValidationError(_("This customer does not have a PAN. Please check customer details"))
            if not self.partner_id.bill_submission_process:
                raise ValidationError(
                    _("This customer does not have a Bill submission process defined. Please check customer details"))
            if self.partner_id.bill_submission_process.code == 'email' and not self.bill_submission_email:
                raise ValidationError(_("Bill submission email is required."))
            if self.partner_id.bill_submission_process.code in ['site',
                                                                'site_office'] and not self.site_bill_submission_godown:
                raise ValidationError(_("Site Bill submission godown is required."))
            if self.partner_id.bill_submission_process.code in ['office',
                                                                'site_office'] and not self.office_bill_submission_godown:
                raise ValidationError(_("Office Bill submission godown is required."))
            if self.partner_id.bill_submission_process.code in ['site', 'site_office'] and not self.bill_site_contact:
                raise ValidationError(_("Bill Site Contact is required."))
            if self.partner_id.bill_submission_process.code in ['office', 'site_office'] and not self.bill_office_contact:
                raise ValidationError(_("Customer Bill Submission Office Contac"))
            if self.partner_id.bill_submission_process.code in ['office',
                                                                'site_office'] and not self.bill_submission_office_branch:
                raise ValidationError(_("Bill Submission Office Branch is required."))
            if not self.partner_id.team_id:
                raise ValidationError(_("Sales team for master customer is not available."))
            if not self.partner_id.user_id.email:
                raise ValidationError(_("Sales Person for master customer is not available."))
            if not self.partner_id.credit_rating:
                raise ValidationError(_("Credit Rating for master customer is not available."))

            if self.security_cheque and not (self.cheque_number or self.cheque_amount or self.bank):
                raise ValidationError(_("Please enter security cheque details"))

    def _generate_job_number(self, created_by, customer_id, quotation_id):
        today = datetime.date.today()
        job_order_number = str(today.year) + "/" + today.strftime("%b") + "/" + self.jobsite_id.name + "/" + str(created_by) + "/" + str(customer_id)
        if self.po_number:
            job_order_number = job_order_number + "/" + self.po_number

        job_order_number = job_order_number + "/" + str(quotation_id)
        return job_order_number

    def check_existing_customer_beta(self, gstn):
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(get_beta_branch_form_gstn_query(), [gstn])
            ids = cursor.fetchall()
            if ids and len(ids)>0:
                return True
            else:
                return False

        except Error as err:
            raise UserError(_(err))
        except Exception as e:
            raise UserError(_(e))
        finally:
            cursor.close()

    def _get_security_cheque_data(self, customer_id, order_id, account_manager):
        return {
            'customer_id': customer_id,
            'order_id': order_id,
            'cheque_no': self.cheque_number,
            'cheque_amount': self.cheque_amount,
            'cheque_date' : self.cheque_date.strftime('%Y-%m-%d') if self.cheque_date else None,
            'bank': self.bank,
            'lapsed': 0,
            'verified': 0,
            'cheque_ownership': account_manager,
            'security_cheque': self._get_document_if_exists('security_cheque')
        }

    def _get_order_data(self, created_by, customer_id, quotation_id, quotation_total, job_order_number,
                        place_of_supply_code, beta_bill_godown_id, beta_godown_id, is_authorized):
        return {
            'quotation_id': quotation_id,
            'customer_id': customer_id,
            'job_order': job_order_number,
            'po_no': self.po_number,
            'place_of_supply': place_of_supply_code,
            'gstn': self.customer_branch.gstn,
            'security_cheque': self._get_document_if_exists('security_cheque'),
            'rental_advance': self._get_document_if_exists('rental_advance'),
            'rental_order': self._get_document_if_exists('rental_order'),
            'godown_id': beta_godown_id,
            'billing_godown': beta_bill_godown_id,
            'created_by': created_by,
            'total': quotation_total,
            'is_authorized': is_authorized,
            'crm_account_id':self.id,
            'po_status':'APPROVED',
            'po_stage':self._get_po_stage()

        }

    def _get_po_stage(self):
        for record in self:
            if record.partner_id.credit_rating == 'A':
                if record.po_available:
                    return 'PO'
                elif record.po_promise_date:
                    return 'PROMISE'
            elif record.partner_id.credit_rating in ('B', 'C'):
                if record.po_available:
                    return 'PO'
                elif record.po_promise_date:
                    return 'PROMISE'
                else:
                    return 'N/A'
        return 'NoCredit'


    def _get_document_if_exists(self, field_name):
        attachment = self.env['ir.attachment'].sudo().search(
            [('res_model', '=', 'sale.order'), ('res_field', '=', field_name), ('res_id', '=', self.id), ('type', '=', 'url')])

        if not attachment:
            return None

        fname = attachment.url

        return fname[len("https://youngmanbeta.s3.amazonaws.com/"):] if fname else None

    def _get_quotation_data(self, created_by, customer_id, beta_godown_id, quotation_total):
        return {
            'created_by': created_by,
            'customer_id': customer_id,
            'contact_name': self.purchaser_name.name,
            'phone_number': self.purchaser_name.mobile,
            'site_name': self.jobsite_id.name,
            'price_type': self.price_type,
            'total': quotation_total,
            'freight': self.freight_amount,
            'gstn': 'Gstn Moved to Order',
            'billing_address_line': _concatenate_address_string(
                [self.billing_street, self.billing_street2, self.billing_city]),
            'billing_address_city': self.billing_state_id.name if self.billing_state_id else "",
            'billing_address_pincode': self.billing_zip,
            'delivery_address_line': _concatenate_address_string(
                [self.delivery_street, self.delivery_street2, self.delivery_city]),
            'delivery_address_city': self.delivery_state_id.name if self.delivery_state_id else "",
            'delivery_address_pincode': self.delivery_zip,
            'delivery_date': self.delivery_date.strftime('%Y-%m-%d'),
            'pickup_date': self.pickup_date.strftime('%Y-%m-%d'),
            'security_amt': self.security_amount if self.security_amount else 0.0,
            'freight_payment': _get_beta_compatible_freight_type(self.freight_paid_by),
            'godown_id': beta_godown_id,
            'sign_type': 'MANUAL',
            'crm_account_id': self.id,
            'computed_freight_amount':self.computed_freight_amount,
            'overidden_freight':self.overidden_freight,
            'computed_vehicle_type':self.vehicle_type
        }

    def _get_connection(self):
        connection = False
        cursor = False
        try:
            beta_db_url = self.env['ir.config_parameter'].sudo().get_param('ym_beta_updates.beta_db_url')
            beta_db_port = self.env['ir.config_parameter'].sudo().get_param('ym_beta_updates.beta_db_port')
            beta_db = self.env['ir.config_parameter'].sudo().get_param('ym_beta_updates.beta_db')
            beta_db_username = self.env['ir.config_parameter'].sudo().get_param('ym_beta_updates.beta_db_username')
            beta_db_password = self.env['ir.config_parameter'].sudo().get_param('ym_beta_updates.beta_db_password')

            if not (beta_db_url or beta_db_port or beta_db or beta_db_username or beta_db_password):
                raise UserError("Beta Database is not configured. Please as system admins to configure it")

            connection = mysql.connector.connect(
                host=beta_db_url,
                port=beta_db_port,
                user=beta_db_username,
                password=beta_db_password,
                database=beta_db
            )
            return connection
        except Error as e:
            _logger.error("Error while connecting to MySQL using Connection pool ", e)
            raise e

    def _execute_single_update(self, statement, args):
        connection = False
        cursor = False
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(statement, args)
        except Error as e:
            raise UserError(_("Could not perform selection action: " + str(e)))
        except UserError as e:
            raise e
        except Exception as e:
            raise UserError(_("Could not perform selection action: " + str(e)))
        finally:
            if connection and connection.is_connected() and cursor:
                cursor.close()

    def open_force_pickup(self):
        if not self.id:
            raise UserError('You must save the po Before force pickup')
        if not self.job_order:
            raise UserError('You must have and order to confirm ')
        for record in self:
            data = {
                'order_id': record.beta_order_id,
                'date': fields.Datetime.now().strftime('%Y-%m-%d')
            }

            headers = {
                'Content-Type': 'application/json',
            }

            beta_force_pickup_endpoint = self.env['ir.config_parameter'].sudo().get_param(
                'ym_configs.ym_beta_force_pickup_endpoint')

            try:
                response = requests.post(beta_force_pickup_endpoint, json=data, headers=headers,
                                         verify=False)
                response.raise_for_status()
                response_data = response.json()
                if response_data.get('status') == 'success' and 'message' in response_data:
                    self._create_log_note(response_data)
                    self._block_jobsite_or_customer()

                    _logger.info("Request successful. Response: {}".format(response_data))

            except requests.exceptions.RequestException as e:
                _logger.error("Error: Failed to hit the API: {}".format(e))
                raise UserError("Failed to hit the API: {}".format(e))

    def _create_log_note(self, response_data):
        message_body = response_data.get('message')
        if message_body:
            note_subtype = self.env['mail.message.subtype'].search([('name', '=', 'Note')], limit=1)
            if note_subtype:
                self.env['mail.message'].create({
                    'body': message_body,
                    'subtype_id': note_subtype.id,
                    'model': self._name,
                    'res_id': self.id,
                })
                return True
        return False

    def _block_jobsite_or_customer(self):
        if self.partner_id.credit_rating == 'A':
            if self.partner_id.id not in self.jobsite_id.blocked_customer_list.blocked_customer_id.ids:
                self.env['jobsite.blocked.customers'].create({
                    'jobsite_id': self.jobsite_id.id,
                    'blocked_customer_id': self.partner_id.id,
                })
        else:
            if self._update_customer_status_on_beta():
                self.partner_id.cpl_status = 'BLOCKED'
            else:
                raise UserError("Failed to update customer status on beta ")

    def _update_customer_status_on_beta(self):
        try:
            connection = self._get_connection()
            connection.autocommit = False
            cursor = connection.cursor()

            cursor.execute(
                "SELECT customer_master_id FROM customers WHERE id = (SELECT customer_id FROM orders WHERE id = %s)",
                (self.beta_order_id,)
            )
            customer_master_id = cursor.fetchone()

            if customer_master_id:
                customer_master_id = customer_master_id[0]

                cursor.execute("UPDATE customer_masters SET status = 'BLOCK' WHERE id = %s", (customer_master_id,))
                cursor.execute("UPDATE customers SET status = 'BLOCK' WHERE customer_master_id = %s",
                               (customer_master_id,))
            connection.commit()
            return True
        except Exception as e:
            connection.rollback()
            _logger.error(f"An error occurred: {e}")
            return False
        finally:
            cursor.close()
            connection.close()


    def _get_project_manager(self, order_id):
        return {'contact_crm_id': self.project_manager.id, 'order_id': order_id}

    def _send_project_manager_to_beta(self):
        try:
            connection = self._get_connection()
            connection.autocommit = False
            cursor = connection.cursor()
            order_id = self.beta_order_id
            cursor.execute(_get_contact_notification_insert_query(), self._get_project_manager(order_id))
            connection.commit()
            return True
        except Exception as e:
            connection.rollback()
            _logger.error(f"An error occurred: {e}")
            return False
        finally:
            cursor.close()
            connection.close()




