import logging

from odoo import SUPERUSER_ID, api
from odoo.tools import sql

_logger = logging.getLogger(__name__)


ENCODING = "iso-8859-1"
FILE_EXT = "txt"
EXCHANGE_CODES = [
    "diapar_out_order",
    "diapar_in_despatch_advice",
    "diapar_in_purchase_price",
]
DIRECTION_MAPPING = {
    "input_dir_pending": "IN/PENDING",
    "input_dir_done": "IN/DONE",
    "input_dir_error": "IN/ERROR",
    "output_dir_pending": "OUT/PENDING",
    "output_dir_done": "OUT/DONE",
    "output_dir_error": "OUT/ERROR",
}


def _skip_migration(env, version=None):
    if not version:
        return
    tables_to_check = [
        "edi_config_system",
        "edi_backend_type",
        "edi_backend",
        "edi_exchange_type",
    ]
    if any(not sql.table_exists(env.cr, table_name) for table_name in tables_to_check):
        _logger.warning(
            "One or more required tables do not exist. Skipping migration..."
        )
        return True

    return False


def _get_edi_config_values(env):
    cols = [
        "ftp_host",
        "ftp_port",
        "ftp_login",
        "ftp_password",
        "supplier_id",
        "parent_supplier_id",
        "constant_file_start",
        "constant_file_end",
        "vrp_code",
        "customer_code",
        "header_code",
        "lines_code",
        "delivery_sign",
    ]
    env.cr.execute(
        sql.SQL(
            """
        SELECT cfg.id AS config_id, %(col_names)s
        FROM edi_config_system AS cfg
        """,
            col_names={", ".join(f"cfg.{col}" for col in cols)},
        )
    )
    config_infos = []
    for row in env.cr.fetchall():
        config_info = dict(zip(cols, row[1:], strict=False))
        config_infos.append(config_info)
    return config_infos


def _check_fs_storage(env, config_info):
    values_to_insert = {
        "name": "Diapar FTP Storage",
        "code": "diapar_ftp",
        "protocol": "ftp",
        "options": {
            "host": f"{config_info.get('ftp_host', '')}",
            "port": f"{config_info.get('ftp_port', '')}",
            "login": f"{config_info.get('ftp_login', '')}",
            "password": f"{config_info.get('ftp_password', '')}",
        },
    }
    values_to_insert["options"] = str(values_to_insert["options"])
    if sql.table_exists(env.cr, "tbl_temp_fs_storage"):
        env.cr.execute(
            sql.SQL(
                """
            -- Insert values
            INSERT
                INTO tbl_temp_fs_storage (%(col_names)s)
                VALUES (%(values_to_insert)s)
            ON CONFLICT (code) DO NOTHING;

            -- Return the id of the inserted or existing record
            SELECT id FROM tbl_temp_fs_storage WHERE code = 'diapar_ftp';
            """,
                col_names=", ".join(values_to_insert.keys()),
                values_to_insert=", ".join(
                    f"%({key})s" for key in values_to_insert.keys()
                ),
                **values_to_insert,
            )
        )
        result = env.cr.fetchone()
        return result[0] if result else None
    # Create temp table if it does not exist
    env.cr.execute(
        sql.SQL(
            """
        -- Create a temporary table
        CREATE TEMPORARY TABLE
            tbl_temp_fs_storage (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            code VARCHAR(255),
            protocol VARCHAR(50),
            options TEXT
        );

        -- Insert values
        INSERT INTO tbl_temp_fs_storage (%(col_names)s) VALUES (%(values_to_insert)s)
        ON CONFLICT (code) DO NOTHING;

        -- Return the id of the inserted or existing record
        SELECT id FROM tbl_temp_fs_storage WHERE code = 'diapar_ftp';
        """,
            col_names=", ".join(values_to_insert.keys()),
            values_to_insert=", ".join(f"%({key})s" for key in values_to_insert.keys()),
            **values_to_insert,
        )
    )
    result = env.cr.fetchone()
    return result[0] if result else None


def _check_edi_backend(env, fs_storage_id):
    # Backend type
    env.cr.execute(
        sql.SQL(
            """
        -- Insert values
        INSERT INTO edi_backend_type (name, code)
            VALUES ('DIAPAR', 'diapar')
        ON CONFLICT (code) DO NOTHING;

        -- Return the id of the inserted or existing record
        SELECT id FROM edi_backend_type WHERE code = 'diapar';
        """
        )
    )
    backend_type_id = env.cr.fetchone()[0]
    # Backend
    values_to_insert = {
        "name": "Diapar",
        "backend_type_id": backend_type_id,
        "storage_id": fs_storage_id,
    }
    values_to_insert.update(DIRECTION_MAPPING)
    env.cr.execute(
        sql.SQL(
            """
        SELECT id FROM edi_backend WHERE backend_type_id = %(backend_type_id)s
        """,
            backend_type_id=backend_type_id,
        )
    )
    result = env.cr.fetchone()
    if not result:
        env.cr.execute(
            sql.SQL(
                """
            -- Insert values
            INSERT INTO edi_backend (%(col_names)s)
                VALUES (%(values_to_insert)s);

            -- Return the id of the inserted or existing record
            SELECT id FROM edi_backend WHERE backend_type_id = %(backend_type_id)s;
            """,
                col_names=", ".join(values_to_insert.keys()),
                backend_type_id=backend_type_id,
                values_to_insert=", ".join(
                    f"%({key})s" for key in values_to_insert.keys()
                ),
                **values_to_insert,
            )
        )
        result = env.cr.fetchone()
    backend_id = result[0]
    return backend_id, backend_type_id


def _prepare_exchange_type_datas(config_info, backend_id, backend_type_id):
    common_values = {
        "exchange_file_ext": FILE_EXT,
        "encoding": ENCODING,
        "backend_id": backend_id,
        "backend_type_id": backend_type_id,
    }
    exchange_types_data = []
    for code in EXCHANGE_CODES:
        exchange_type_data = {
            "code": code,
            "name": code,
        }
        exchange_type_data.update(common_values)
        if code == "diapar_out_order":
            exchange_type_data.update(
                {
                    "direction": "output",
                    "exchange_filename_pattern": "LD{dt[0:8]}H{dt[9:13]}.C99",
                    "exchange_file_ext": "C99",
                    "generate_model_id": False,  # To be set in post-migration
                    "advanced_settings_edit": """
                        filename_pattern:
                            date_pattern: %Y%m%d %H%M%S
                    """,
                }
            )
        elif code == "diapar_in_despatch_advice":
            exchange_type_data.update(
                {
                    "direction": "input",
                    "exchange_filename_pattern": "BLE*",
                    "header_code": config_info["header_code"] or "H",
                    "lines_code": config_info["lines_code"] or "L",
                    "delivery_sign": config_info["delivery_sign"] or "+",
                    "process_model_id": False,  # To be set in post-migration
                }
            )
        elif code == "diapar_in_purchase_price":
            exchange_type_data.update(
                {
                    "direction": "input",
                    "exchange_filename_pattern": "CH*",
                    "process_model_id": False,  # To be set in post-migration
                }
            )
        exchange_types_data.append(exchange_type_data)
    return exchange_types_data


def _check_exchange_types(env, config_info, backend_type_id, backend_id):
    exchange_types_data = _prepare_exchange_type_datas(
        config_info, backend_id, backend_type_id
    )
    for exchange_type in exchange_types_data:
        env.cr.execute(
            sql.SQL(
                """
            -- Insert values
            INSERT INTO edi_exchange_type (%(col_names)s)
                VALUES (%(values_to_insert)s)
            ON CONFLICT (code) DO NOTHING;
            """,
                col_names=", ".join(exchange_type.keys()),
                values_to_insert=", ".join(
                    f"%({key})s" for key in exchange_type.keys()
                ),
                **exchange_type,
            )
        )

    env.cr.execute(
        sql.SQL(
            """
        SELECT id, code FROM edi_exchange_type WHERE code IN %s
        """,
            (tuple(EXCHANGE_CODES),),
        )
    )
    return {row[1]: row[0] for row in env.cr.fetchall()}


def _mapping_fields(env, exchange_type_infos):
    """
    Two table (edi_price_mapping, edi_ble_mapping) is deprecated,
    and in v18.0, create a new edi_field_mapping table to replace them.
    """

    if any(
        [
            not sql.table_exists(env.cr, "edi_price_mapping"),
            not sql.table_exists(env.cr, "edi_ble_mapping"),
        ]
    ):
        # Skip if the old table does not exist as there is nothing to migrate
        _logger.warning(
            "Tables %s and %s do not exist. Skipping mapping fields migration...",
            "edi_price_mapping",
            "edi_ble_mapping",
        )  # noqa: E501
        return

    env.cr.execute(
        sql.SQL(
            """
        -- Create a temporary table
        CREATE TEMPORARY TABLE
        tbl_temp_edi_field_mapping (
            id SERIAL PRIMARY KEY,

            -- Standard columns
            sequence INTEGER,
            position INTEGER NOT NULL,
            name VARCHAR(255),
            sequence_start INTEGER,
            sequence_end INTEGER,
            is_numeric BOOLEAN,
            is_date BOOLEAN,
            decimal_precision INTEGER,

            -- Relational columns
            res_field_model VARCHAR(255),
            res_field_name VARCHAR(255),
            exchange_type_code VARCHAR(255)
        );
        """
        )
    )
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

    def _insert_mapping_fields(table_name, code):
        env.cr.execute(
            sql.SQL(
                """
            -- Insert values
            INSERT INTO tbl_temp_edi_field_mapping (
                %(col_names)s,
                res_field_model, res_field_name, exchange_type_code
            )
            SELECT
                %(col_names)s,
                imf.model AS res_field_model,
                imf.name AS res_field_name,
                ext.code AS exchange_type_code
            FROM %(table_name)s epm
            LEFT JOIN ir_model_fields imf ON imf.id = epm.mapping_field_id
            LEFT JOIN edi_exchange_type ext ON ext.code = %(code)s
            """,
                col_names=", ".join(standard_cols),
                table_name=table_name,
                code=code,
            )
        )

    for code, _id in exchange_type_infos.items():
        _insert_mapping_fields("edi_price_mapping", code)
        _insert_mapping_fields("edi_ble_mapping", code)


def _template_output(env, config_info, backend_id, backend_type_id):
    env.cr.execute(
        sql.SQL(
            """
            -- Create a temporary table
            CREATE TEMPORARY TABLE
            tbl_temp_edi_template_output (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                backend_type_id INTEGER NOT NULL,
                backend_id INTEGER NOT NULL,
                code VARCHAR(255) NOT NULL,
                output_type VARCHAR(50) NOT NULL,
                generator VARCHAR(50) NOT NULL,
                customer_code VARCHAR(255),
                vrp_code VARCHAR(255),
                constant_file_start VARCHAR(255),
                constant_file_end VARCHAR(255)
            );

            -- Insert values
            INSERT INTO tbl_temp_edi_template_output (
                name, backend_type_id, backend_id, code, output_type,
                generator, customer_code, vrp_code,
                constant_file_start, constant_file_end
            )
            VALUES (
                'Diapar Output Exchange Template',
                %(backend_type_id)s,
                %(backend_id)s,
                'diapar.output.exchange.template',
                'text',
                'qweb',
                %(customer_code)s,
                %(vrp_code)s,
                %(constant_file_start)s,
                %(constant_file_end)s
            );
        """,
            backend_type_id=backend_type_id,
            backend_id=backend_id,
            customer_code=config_info["customer_code"],
            vrp_code=config_info["vrp_code"],
            constant_file_start=config_info["constant_file_start"],
            constant_file_end=config_info["constant_file_end"],
        )
    )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    if _skip_migration(env, version):
        return

    config_infos = _get_edi_config_values(env)
    if not config_infos:
        _logger.warning(
            "No configuration found in edi_config_system. Skipping migration..."
        )  # noqa: E501
        return

    for config_info in config_infos:
        fs_storage_id = _check_fs_storage(env, config_info)
        backend_id, backend_type_id = _check_edi_backend(env, fs_storage_id)
        exchange_type_infos = _check_exchange_types(
            env, config_info, backend_type_id, backend_id
        )
        _mapping_fields(env, exchange_type_infos)
        _template_output(env, config_info, backend_id, backend_type_id)

    _logger.info("Pre-migration data adjustments completed.")
