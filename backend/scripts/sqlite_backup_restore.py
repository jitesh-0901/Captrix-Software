"""
Captrix AI — SQLite Database Backup and Recovery Utility
Provides point-in-time snapshot backup, integrity verification, and recovery for development SQLite database.
"""

import os
import shutil
import sqlite3
from datetime import datetime

BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db.sqlite3')

def backup_database():
    """Performs consistent SQLite backup using online backup API"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f"captrix_backup_{timestamp}.sqlite3")

    if not os.path.exists(DB_PATH):
        print(f"Error: Database at {DB_PATH} not found.")
        return None

    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(backup_path)
    with dst:
        src.backup(dst, pages=100)
    dst.close()
    src.close()

    print(f"Backup created successfully: {backup_path}")
    verify_database(backup_path)
    return backup_path

def verify_database(db_file=DB_PATH):
    """Executes PRAGMA integrity_check on the database"""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check;")
    result = cursor.fetchall()
    conn.close()
    status = result[0][0] if result else "FAILED"
    print(f"Integrity check for {os.path.basename(db_file)}: {status}")
    return status == 'ok'

def restore_database(backup_file):
    """Restores database from a verified backup snapshot"""
    if not os.path.exists(backup_file):
        print(f"Error: Backup file {backup_file} not found.")
        return False

    if not verify_database(backup_file):
        print("Error: Backup failed integrity check. Aborting restore.")
        return False

    # Create safety copy of current db
    if os.path.exists(DB_PATH):
        safety_copy = f"{DB_PATH}.safety_{int(datetime.now().timestamp())}"
        shutil.copy2(DB_PATH, safety_copy)
        print(f"Current database backed up to safety copy: {safety_copy}")

    shutil.copy2(backup_file, DB_PATH)
    print(f"Restored {backup_file} to {DB_PATH}")
    return verify_database(DB_PATH)

if __name__ == '__main__':
    import sys
    print("Captrix AI — SQLite Backup & Recovery Utility")
    if len(sys.argv) > 1 and sys.argv[1] == 'verify':
        target = sys.argv[2] if len(sys.argv) > 2 else DB_PATH
        verify_database(target)
    elif len(sys.argv) > 1 and sys.argv[1] == 'restore':
        if len(sys.argv) < 3:
            print("Usage: python sqlite_backup_restore.py restore <backup_file_path>")
        else:
            restore_database(sys.argv[2])
    else:
        bk = backup_database()
