import sqlite3
import json
import sys
import os

# Check for command line arguments
if len(sys.argv) != 2:
    print("Usage: insert_json_to_sqlite.py <database_path>")
    sys.exit(1)

db_path = sys.argv[1]
json_dir = 'test_database'

# Connect to the SQLite database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Loop through all JSON files in the test_database directory
for file_name in os.listdir(json_dir):
    if file_name.endswith('.json'):
        table = file_name.split('_')[0]
        json_file_path = os.path.join(json_dir, file_name)

        print(f"Processing {json_file_path}...")

        # Load the JSON data
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Assuming each JSON file is an array of dictionaries
        for entry in data:
            # Dynamically generate the query based on keys
            keys = ', '.join(entry.keys())
            question_marks = ', '.join(['?' for _ in entry.keys()])
            values = tuple(entry.values())

            # Insert data into the SQLite database
            cursor.execute(f'''
                INSERT INTO {table} ({keys})
                VALUES ({question_marks})
            ''', values)

# Commit changes and close connection
conn.commit()
conn.close()

print("All JSON data successfully inserted into the SQLite database.")
