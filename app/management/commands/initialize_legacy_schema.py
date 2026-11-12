import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Create missing legacy tables and safely add supported nullable columns.'

    def handle(self, *args, **options):
        if connection.vendor != 'mysql':
            raise CommandError('initialize_legacy_schema requires a MySQL/MariaDB database.')

        schema_path = Path(__file__).resolve().parents[3] / 'baza_danych.sql'
        if not schema_path.is_file():
            raise CommandError(f'Schema file was not found: {schema_path}')

        sql = re.sub(r'(?m)^\s*--.*$', '', schema_path.read_text(encoding='utf-8'))
        statements = [statement.strip() for statement in sql.split(';') if statement.strip()]
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)

            tables = {
                table.lower(): table
                for table in connection.introspection.table_names(cursor)
            }
            for required_table in ('UZYTKOWNIK', 'PACJENT', 'BADANIE', 'USTAWIENIA_SYSTEMU'):
                if required_table.lower() not in tables:
                    raise CommandError(f'Required table was not created: {required_table}')

            self._add_column_if_missing(
                cursor, tables['badanie'], 'wyniki_json', 'LONGTEXT NULL'
            )
            self._add_column_if_missing(
                cursor, tables['badanie'], 'test_type', 'VARCHAR(50) NULL'
            )
            self._add_column_if_missing(
                cursor, tables['uzytkownik'], 'auth_user_id', 'INT NULL'
            )
            self._ensure_auth_user_constraints(cursor, tables['uzytkownik'])

        self.stdout.write(
            self.style.SUCCESS(
                'Schemat utworzony/zweryfikowany; brakujące kolumny dodano bez usuwania danych.'
            )
        )

    @staticmethod
    def _column_names(cursor, table):
        return {
            column.name.lower()
            for column in connection.introspection.get_table_description(cursor, table)
        }

    def _add_column_if_missing(self, cursor, table, column, definition):
        if column.lower() not in self._column_names(cursor, table):
            cursor.execute(
                f'ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}'
            )

    @staticmethod
    def _ensure_auth_user_constraints(cursor, table):
        constraints = connection.introspection.get_constraints(cursor, table)
        profile_key = ['auth_user_id']
        has_unique = any(
            info.get('unique')
            and [name.lower() for name in info.get('columns', [])] == profile_key
            for info in constraints.values()
        )
        if not has_unique:
            cursor.execute(
                f'ALTER TABLE `{table}` '
                'ADD UNIQUE KEY `uq_uzytkownik_auth_user_id` (`auth_user_id`)'
            )

        constraints = connection.introspection.get_constraints(cursor, table)
        has_foreign_key = any(
            [name.lower() for name in info.get('columns', [])] == profile_key
            and info.get('foreign_key')
            and info['foreign_key'][0].lower() == 'auth_user'
            and info['foreign_key'][1].lower() == 'id'
            for info in constraints.values()
        )
        if not has_foreign_key:
            cursor.execute(
                f'ALTER TABLE `{table}` '
                'ADD CONSTRAINT `fk_uzytkownik_auth_user` '
                'FOREIGN KEY (`auth_user_id`) REFERENCES `auth_user` (`id`) '
                'ON DELETE SET NULL'
            )
