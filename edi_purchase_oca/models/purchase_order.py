# Copyright 2022 ForgeFlow S.L. (https://www.forgeflow.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import models


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = [
        "purchase.order",
        "edi.exchange.consumer.mixin",
    ]

    def _edi_config_field_relation(self):
        return self.partner_id.edi_purchase_conf_ids
