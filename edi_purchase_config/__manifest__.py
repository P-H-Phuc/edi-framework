# Copyright (C) 2016-Today: Druidoo (<http://www.druidoo.io/>)
# @author: Druidoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html

{
    "name": "EDI Purchase Config",
    "version": "18.0.1.0.0",
    "category": "Custom",
    "author": "Druidoo, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/edi-framework",
    "license": "AGPL-3",
    "depends": ["purchase"],
    "data": [
        "security/ir_module_category.xml",
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "views/actions.xml",
        "views/menus.xml",
        "views/edi_config_system_view.xml",
        "views/purchase_edi_log_view.xml",
        "views/res_partner_view.xml",
    ],
}
