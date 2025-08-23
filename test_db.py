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
