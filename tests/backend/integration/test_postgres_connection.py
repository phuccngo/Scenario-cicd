"""Smoke-test real PostgreSQL SQL execution in the CI service.

This deliberately tests the database service and PostgreSQL driver only.
Application ORM/model integration tests should be added after the Scenario
database configuration and model definitions have been inspected.
"""
import os

import psycopg2


def test_postgres_executes_sql_and_persists_rows_within_transaction():
    database_url = os.environ["TEST_DATABASE_URL"]

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TEMPORARY TABLE ci_sql_probe (
                    id INTEGER PRIMARY KEY,
                    value TEXT NOT NULL
                ) ON COMMIT DROP
                """
            )
            cursor.execute(
                "INSERT INTO ci_sql_probe (id, value) VALUES (%s, %s)",
                (1, "scenario-ci"),
            )
            cursor.execute(
                "SELECT value FROM ci_sql_probe WHERE id = %s",
                (1,),
            )

            row = cursor.fetchone()

    assert row == ("scenario-ci",)
