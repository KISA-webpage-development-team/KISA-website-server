"""KISAWEB model (connection with mySQL database)."""
import server
import MySQLdb.cursors

def cursor():
    return server.db.connection.cursor(MySQLdb.cursors.DictCursor)

def commit_close(cursor):
    server.db.connection.commit()
    cursor.close()
