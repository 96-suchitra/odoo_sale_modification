from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sale_order_limit = fields.Float(config_parameter='sale_modification.sale_order_limit')
