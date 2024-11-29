# -*- coding: utf-8 -*-

from odoo import models, fields
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    manager_reference = fields.Text()
    auto_workflow = fields.Boolean()

    def action_confirm(self):
        sale_order_limit = self.env['ir.config_parameter'].sudo().get_param('sale_modification.sale_order_limit') or 0
        if self.amount_total > float(sale_order_limit) and not self.env.user.has_group('sale_modification.group_sale_admin'):
            raise UserError(("Order Amount exceeds the defined Sale Order Limit (%s)") % ("%.2f" % float(sale_order_limit)))
        if self.auto_workflow:
            product_dict = {}
            for lines in self.order_line:
                if lines.product_id in product_dict:
                    product_dict[lines.product_id] += lines.product_uom_qty
                else:
                    product_dict[lines.product_id] = lines.product_uom_qty

            for product in product_dict:
                delivery_id = self.env['stock.picking'].create({
                    'partner_id': self.partner_id.id,
                    'scheduled_date': self.date_order,
                    'date_deadline': self.date_order,
                    'origin': self.name,
                    'location_dest_id':self.env.ref('stock.stock_location_customers').id,
                    'location_id': self.env.ref('stock.stock_location_stock').id,
                    'picking_type_id':self.env.ref('stock.picking_type_out').id,
                    'move_ids_without_package': [(0, 0, {
                        'name': product.name,
                        'product_id': product.id,
                        'product_uom_qty': product_dict[product],
                        'location_dest_id': self.env.ref('stock.stock_location_customers').id,
                        'location_id': self.env.ref('stock.stock_location_stock').id,
                    })]
                })

                delivery_id.button_validate()
                self.picking_ids += delivery_id
                invoice_id = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create({
                    'partner_id': self.partner_id.id,
                    'move_type': 'out_invoice',
                    'invoice_line_ids': [(0, 0,{
                        'sale_line_ids': [(6, 0, lines.ids)],
                        'product_id': lines.product_id.id,
                        'name': lines.product_id.name,
                        'quantity': lines.product_uom_qty,
                        'price_unit': lines.product_id.list_price,
                        'tax_ids': [(6, 0, lines.product_id.taxes_id.ids)]
                    }) for lines in self.order_line]
                })
                invoice_id.action_post()
                for line in invoice_id.invoice_line_ids:
                    for sale_line in line.sale_line_ids:
                        sale_line.invoice_lines = [(6, 0, line.ids)]

                popup = self.env['account.payment.register'].with_context({
                    'active_model': 'account.move.line',
                    'active_ids': invoice_id.line_ids.ids
                }).create({})
                popup.action_create_payments()
        return super(SaleOrder, self).action_confirm()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        if self.order_id.auto_workflow:
            return True
        return super(SaleOrderLine, self)._action_launch_stock_rule(previous_product_uom_qty)

