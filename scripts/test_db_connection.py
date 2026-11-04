from stock_analytics.db.connection import test_connection


if __name__ == "__main__":
    database, user = test_connection()

    print(f"Connected to database: {database}")
    print(f"PostgreSQL user: {user}")