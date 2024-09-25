import frappe
from payments.utils import get_payment_gateway_controller


def get_payment_gateway():
	return frappe.db.get_single_value("LMS Settings", "payment_gateway")


def get_controller(payment_gateway):
	return get_payment_gateway_controller(payment_gateway)


def validate_currency(payment_gateway, currency):
	controller = get_controller(payment_gateway)
	controller().validate_transaction_currency(currency)


@frappe.whitelist()
def get_payment_link(doctype, docname, amount, total_amount, currency, address):
	payment_gateway = get_payment_gateway()
	address = frappe._dict(address)
	amount_with_gst = total_amount if total_amount != amount else 0

	payment = record_payment(address, doctype, docname, amount, currency, amount_with_gst)
	controller = get_controller(payment_gateway)

	if controller.doctype == "Stripe Settings":
		print(controller.as_dict())
		doctype = "Stripe Settings"
		docname = controller.name

	payment_details = {
		"amount": total_amount,
		"title": f"Payment for {doctype} {docname}",
		"description": f"{address.billing_name}'s payment for {doctype} {docname}",
		"reference_doctype": doctype,
		"reference_docname": docname,
		"payer_email": frappe.session.user,
		"payer_name": address.billing_name,
		"order_id": docname,
		"currency": currency,
		"payment_gateway": payment_gateway,
		"redirect_to": f"/lms/batches/{docname}",
		"payment": payment.name,
	}
	print(controller)
	url = controller.get_payment_url(**payment_details)

	return url


def record_payment(address, doctype, docname, amount, currency, amount_with_gst=0):
	address = frappe._dict(address)
	address_name = save_address(address)

	payment_doc = frappe.new_doc("LMS Payment")
	payment_doc.update(
		{
			"member": frappe.session.user,
			"billing_name": address.billing_name,
			"address": address_name,
			"amount": amount,
			"currency": currency,
			"amount_with_gst": amount_with_gst,
			"gstin": address.gstin,
			"pan": address.pan,
			"source": address.source,
			"payment_for_document_type": doctype,
			"payment_for_document": docname,
		}
	)
	payment_doc.save(ignore_permissions=True)
	return payment_doc


def save_address(address):
	filters = {"email_id": frappe.session.user}
	exists = frappe.db.exists("Address", filters)
	if exists:
		address_doc = frappe.get_last_doc("Address", filters=filters)
	else:
		address_doc = frappe.new_doc("Address")

	address_doc.update(address)
	address_doc.update(
		{
			"address_title": frappe.db.get_value("User", frappe.session.user, "full_name"),
			"address_type": "Billing",
			"is_primary_address": 1,
			"email_id": frappe.session.user,
		}
	)
	address_doc.save(ignore_permissions=True)
	return address_doc.name