# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools import sql

_logger = logging.getLogger(__name__)


MAPPING_EXCODE_PROCESS = {
    "diapar_out_order": ("generate_model_id", "model_edi_output_diapar_handler"),
    "diapar_in_despatch_advice": (
        "process_model_id",
        "model_edi_input_diapar_despatch_advice_handler",
    ),
    "diapar_in_purchase_price": (
        "process_model_id",
        "model_edi_input_diapar_purchase_price_handler",
    ),
}


def _migrate_fs_storage(env):
    tmp_table = "tbl_temp_fs_storage"
    if any(
        [
            not sql.table_exists("fs_storage"),
            not sql.table_exists(tmp_table),
        ]
    ):
        return
    env.cr.execute(
        sql.SQL(
            """
        -- Insert values from temporary table to fs_storage
        INSERT INTO fs_storage (name, code, protocol, options)
        SELECT name, code, protocol, options
        FROM %(tmp_table)s
        WHERE code = 'diapar_ftp'
        ON CONFLICT (code) DO NOTHING;

        -- Drop the temporary table
        DROP TABLE IF EXISTS %(tmp_table)s;
        """,
            tmp_table=tmp_table,
        )
    )


def _migrate_exchange_type(env):
    """
    Update the generate_model_id and process_model_id fields
    """
    exchange_type_model = env["edi.exchange.type"]
    for code, process in MAPPING_EXCODE_PROCESS.items():
        existing_type = exchange_type_model.search([("code", "=", code)], limit=1)
        if not existing_type:
            continue
        mmodel = f"edi_purchase_diapar_oca.{process[1]}"
        if getattr(existing_type, process[0]):
            existing_type.write({process[0]: mmodel})
            _logger.info("Updated %s for exchange type '%s'", process[0], code)


def _migrate_field_mapping(env):
    tmp_table = "tbl_temp_edi_field_mapping"
    if not sql.table_exists(env.cr, tmp_table):
        _logger.warning(
            f"Temp table {tmp_table} does not exist. Skipping field mapping migration."
        )  # noqa: E501
        return

    standard_cols = [
        "sequence",
        "position",
        "name",
        "sequence_start",
        "sequence_end",
        "is_numeric",
        "is_date",
        "decimal_precision",
    ]
    env.cr.execute(
        sql.SQL(
            """
        -- Insert values from temporary table to edi_field_mapping
        INSERT INTO edi_field_mapping (
            %(standard_cols)s,
            field_mapping_id,
            exchange_type_id
        )
        SELECT
            %(standard_cols)s,
            imf.id AS field_mapping_id,
            ext.id AS exchange_type_id
        FROM tbl_temp_edi_field_mapping tfm
        LEFT JOIN ir_model_fields imf ON imf.model = tfm.res_field_model
                                      AND imf.name = tfm.res_field_name
        LEFT JOIN edi_exchange_type ext ON ext.code = tfm.exchange_type_code
        ON CONFLICT (name) DO NOTHING;

        -- Drop the temporary table
        DROP TABLE IF EXISTS %(tmp_table)s;
        """,
            standard_cols=", ".join(standard_cols),
            tmp_table=tmp_table,
        )
    )


def _migrate_template_output(env):
    template_name = "edi_exchange_template_output_diapar_3"
    template = env.ref(
        f"edi_purchase_diapar_oca.{template_name}",
        raise_if_not_found=False,
    )
    if not template:
        _logger.warning(
            "Template '%s' not found. Skipping template output migration.",
            template_name,
        )  # noqa: E501
        return

    tmp_table = "tbl_temp_edi_template_output"
    if not sql.table_exists(env.cr, tmp_table):
        _logger.warning(
            f"Temp table {tmp_table} does not exist. Skipping tmp output migration."
        )  # noqa: E501
        return

    standard_cols = [
        "name",
        "backend_type_id",
        "backend_id",
        "code",
        "output_type",
        "generator",
        "customer_code",
        "vrp_code",
        "constant_file_start",
        "constant_file_end",
    ]
    env.cr.execute(
        sql.SQL(
            """
        -- Insert values from temporary table to edi_exchange_template_output
        INSERT INTO edi_exchange_template_output (
            %(standard_cols)s,
            template_id
        )
        SELECT
            %(standard_cols)s,
            %(template_id)s
        FROM %(tmp_table)s
        ON CONFLICT (code) DO NOTHING;

        -- Drop the temporary table
        DROP TABLE IF EXISTS %(tmp_table)s;
        """,
            standard_cols=", ".join(standard_cols),
            template_id=template.id,
            tmp_table=tmp_table,
        )
    )


def migrate(cr, version):
    """Post-migration script for Odoo 18 upgrade."""
    _logger.info("Starting post-migration data adjustments...")

    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    _migrate_fs_storage(env)
    _migrate_exchange_type(env)
    _migrate_field_mapping(env)
    _migrate_template_output(env)

    _logger.info("Post-migration data adjustments completed.")
