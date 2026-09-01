
Test script for verifying the database structure,
migration, and share code records.
"""

import os
import sqlite3


DB_NAME = "lekshare.db"


def test_database():
    

    # Check whether the database exists.
    if not os.path.exists(DB_NAME):
        print("❌ Database file not found!")
        return

    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()

            # Check the shares table structure.
            cursor.execute("PRAGMA table_info(shares)")
            columns = cursor.fetchall()

            print("📊 Database Structure:")

            if not columns:
                print("  ❌ 'shares' table not found!")
                return

            for column in columns:
                name = column[1]
                data_type = column[2]
                print(f"  - {name} ({data_type})")

            # Verify the share_code column.
            column_names = [column[1] for column in columns]

            if "share_code" not in column_names:
                print("❌ share_code column missing!")
                return

            print("✅ share_code column exists!")

            # Count total records.
            cursor.execute("SELECT COUNT(*) FROM shares")
            total_records = cursor.fetchone()[0]

            print(f"📈 Total records: {total_records}")

            # Display sample records.
            cursor.execute(
                """
                SELECT id, share_code, original_name, file_type
                FROM shares
                LIMIT 5
                """
            )
            records = cursor.fetchall()

            print("\n📋 Sample Records:")

            if not records:
                print("  No records found in database.")
            else:
                for record in records:
                    share_id, share_code, filename, file_type = record

                    print(
                        f"  - ID: {share_id}, "
                        f"Code: {share_code}, "
                        f"File: {filename}, "
                        f"Type: {file_type}"
                    )

            print("\n✅ Database test completed!")

    except sqlite3.Error as error:
        print(f"❌ Database error: {error}")


if __name__ == "__main__":
    test_database()

