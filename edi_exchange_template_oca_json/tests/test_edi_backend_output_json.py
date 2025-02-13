# Copyright 2025 Camptocamp SA
# @author Italo LOPES <italo.lopes@camptocamp.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).


import json

from odoo.addons.edi_exchange_template_oca.tests.test_edi_backend_output import (
    TestEDIBackendOutputBase,
)


class TestEDIBackendOutputJsonBase(TestEDIBackendOutputBase):
    @classmethod
    def _setup_records(cls):
        res = super()._setup_records()
        cls.type_out_json = cls._create_exchange_type(
            name="Template output JSON",
            direction="output",
            code="test_type_out_json",
            exchange_file_ext="txt",
            exchange_filename_pattern="{record.ref}-{type.code}-{dt}",
        )
        model = cls.env["edi.exchange.template.output"]
        cls.tmpl_out_json = model.create(
            {
                "generator": "json",
                "name": "Out JSON",
                "backend_type_id": cls.backend.backend_type_id.id,
                "code": "test_type_out_json",
                "output_type": "json",
                "code_snippet": """
result = {
            "name": record.name,
            "ref": record.ref
}
                """,
            }
        )
        cls.type_out_json.output_template_id = cls.tmpl_out_json
        vals = {
            "model": cls.partner._name,
            "res_id": cls.partner.id,
            "type_id": cls.tmpl_out_json.id,
        }
        cls.record_json = cls.backend.create_record("test_type_out_json", vals)
        return res


class TestEDIBackendOutputJson(TestEDIBackendOutputJsonBase):
    def test_00_get_template_json(self):
        self.assertEqual(
            self.backend._get_output_template(self.record_json), self.tmpl_out_json
        )

    def test_01_generate_json(self):
        self.backend.exchange_generate(self.record_json)
        expected = json.dumps({"name": self.partner.name, "ref": self.partner.ref})
        file_content = self.record_json._get_file_content()
        self.assertEqual(file_content.strip(), expected)
