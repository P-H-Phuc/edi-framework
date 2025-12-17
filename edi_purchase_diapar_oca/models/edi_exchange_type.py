from odoo import fields, models


class EDIExchangeType(models.Model):
    _inherit = "edi.exchange.type"

    field_mapping_ids = fields.One2many(
        comodel_name="edi.field.mapping",
        inverse_name="exchange_type_id",
        string="Field Mappings",
    )
    header_code = fields.Char()
    lines_code = fields.Char()
    delivery_sign = fields.Char()
