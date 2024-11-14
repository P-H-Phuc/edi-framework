# Copyright 2022 Camptocamp SA
# @author: Simone Orsi <simahawk@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest import mock

from odoo.tests.common import SavepointCase

from odoo.addons.edi_oca.tests.common import EDIBackendTestMixin

from .common import OrderInboundTestMixin, get_xml_handler

# TODO: split in different tests w/ SingleTransaction


class TestOrderInboundFull(SavepointCase, EDIBackendTestMixin, OrderInboundTestMixin):

    _schema_path = "base_ubl:data/xsd-2.2/maindoc/UBL-OrderResponse-2.2.xsd"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_env()
        cls.backend = cls._get_backend()
        cls._setup_inbound_order(cls.backend)
        cls.edi_conf = cls.env.ref(
            "edi_sale_ubl_oca.demo_ubl_edi_configuration_confirmed"
        )

    @classmethod
    def _get_backend(cls):
        return cls.env.ref("edi_ubl_oca.edi_backend_ubl_demo")

    # No need to test sending data
    @mock.patch("odoo.addons.edi_oca.models.edi_backend.EDIBackend._exchange_send")
    def test_new_order(self, mock_send):
        self.backend._check_input_exchange_sync()
        self.assertEqual(self.exc_record_in.edi_exchange_state, "input_processed")
        order = self._find_order()
        order.partner_id.edi_sale_conf_ids = self.edi_conf
        self.assertEqual(self.exc_record_in.record, order)
        order_msg = order.message_ids[0]
        self.assertIn("Exchange processed successfully", order_msg.body)
        self.assertIn(self.exc_record_in.identifier, order_msg.body)
        order.invalidate_cache()
        # Test relations
        self.assertEqual(len(order.exchange_record_ids), 1)
        exc_record = order.exchange_record_ids.filtered(
            lambda x: x.type_id == self.exc_type_in
        )
        self.assertEqual(exc_record, self.exc_record_in)
        # Confirm the order
        order.action_confirm()
        # Should give us a valid order response ack record
        ack_exc_record = order.exchange_record_ids.filtered(
            lambda x: x.type_id == self.exc_type_out
        )
        file_content = ack_exc_record._get_file_content()
        self.assertTrue(file_content)
        # TMP /
        # path = "/tmp/order.response.test.xml"
        # with open(path, "w") as out:
        #     out.write(file_content)
        # / TMP
        handler = get_xml_handler(self.backend, self._schema_path)
        # Test is a valid file
        err = handler.validate(file_content)
        self.assertEqual(err, None, err)
        # TODO: test data
