<<<<<<< HEAD

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

=======
#!/usr/bin/env python3
"""
Test script to verify database migration and share code generation
"""

import sqlite3
import os

def test_database():
    """Test the database structure and migration"""
    db_name = 'lekshare.db'
    
    if not os.path.exists(db_name):
        print("❌ Database file not found!")
        return
    
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    
    # Check table structure
    c.execute("PRAGMA table_info(shares)")
    columns = c.fetchall()
    
    print("📊 Database Structure:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    # Check if share_code column exists
    column_names = [col[1] for col in columns]
    if 'share_code' in column_names:
        print("✅ share_code column exists!")
    else:
        print("❌ share_code column missing!")
        return
    
    # Check existing records
    c.execute("SELECT COUNT(*) FROM shares")
    count = c.fetchone()[0]
    print(f"📈 Total records: {count}")
    
    # Show sample records
    c.execute("SELECT id, share_code, original_name, file_type FROM shares LIMIT 5")
    records = c.fetchall()
    
    if records:
        print("\n📋 Sample Records:")
        for record in records:
            print(f"  - ID: {record[0]}, Code: {record[1]}, File: {record[2]}, Type: {record[3]}")
    else:
        print("\n📋 No records found in database")
    
    conn.close()
    print("\n✅ Database test completed!")

if __name__ == "__main__":
    test_database()
>>>>>>> b7ba4ffd24021a83426d5741a4a7b62c0fa41bf6
