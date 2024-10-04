#!/bin/bash
# localdb

# Stop on errors
set -Eeuo pipefail

# Sanity check command line options
usage() {
  echo "Usage: $0 (create|destroy|reset)"
}

if [ $# -ne 1 ]; then
  usage
  exit 1
fi

# Parse argument.  $1 is the first argument
case $1 in
  "create")
    if [ -e "test_database/localdb.sqlite3" ]; then
      echo "Error: database already exists"
      exit 1
    fi
    sqlite3 test_database/localdb.sqlite3 < test_database/schema.sql
    python3 test_database/insert_json_to_sqlite.py test_database/localdb.sqlite3
    ;;

  "destroy")
    rm -rf test_database/localdb.sqlite3
    ;;

  "reset")
    rm -rf test_database/localdb.sqlite3
    sqlite3 test_database/localdb.sqlite3 < test_database/schema.sql
    python3 test_database/insert_json_to_sqlite.py test_database/localdb.sqlite3
    ;;
esac
