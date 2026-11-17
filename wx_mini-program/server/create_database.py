"""Create the PostgreSQL schema for the household ledger.

Usage (from ``server``)::

    $env:DATABASE_URL = "postgresql+psycopg://ledger:secret@localhost:5432/ledger"
    D:\Anaconda3\envs\llm\python.exe create_database.py
"""

from ledger.database import Database


if __name__ == "__main__":
    database = Database()
    database.create_schema()
    print("Household ledger database schema created.")
