from odoo import models
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _consolidate_products(self):
        self.ensure_one()
        if not self.order_line:
            raise ValidationError(
                self.env._("No lines in this order %s!", self.name)
            ) from None
        lines = {}
        for line in self.order_line:
            if line.product_id in lines:
                if line.taxes_id != lines[line.product_id]["taxes_id"]:
                    raise ValidationError(
                        self.env._(
                            "Check taxes for lines with product %s!",
                            line.product_id.name,
                        )
                    )
                if line.price_unit != lines[line.product_id]["price_unit"]:
                    raise ValidationError(
                        self.env._(
                            "Check price for lines with product %s!",
                            line.product_id.name,
                        )
                    )
                lines[line.product_id]["quantity"] += line.product_qty
            else:
                code, origin_code = line.product_id._get_supplier_code_or_ean(
                    line.partner_id.id
                )
                values = {
                    "code": code,
                    "origin_code": origin_code,
                    "quantity": line.product_qty,
                    "price_unit": line.price_unit,
                    "taxes_id": line.taxes_id,
                }
                lines.update({line.product_id: values})
        return lines

    def generate_template_output_diapar(self, output_template, exchange_record):
        self.ensure_one()
        return output_template.exchange_generate(
            exchange_record,
            order_lines=self._consolidate_products(),
            env=self.env,
        )
