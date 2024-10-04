"""KISAWEB model (connection with mySQL database)."""
import server
import sqlite3
import re
import MySQLdb.cursors

class Cursor:
    def __init__(self):
        if server.args.l:
            self.connection = sqlite3.connect("test_database/localdb.sqlite3")
            self.connection.row_factory = lambda cursor, row: {cursor.description[idx][0]: value for idx, value in enumerate(row)}
            self.cursor = self.connection.cursor()
        else:
            self.cursor = server.db.connection.cursor(MySQLdb.cursors.DictCursor)

    def execute(self, sql, argsdict):
        if server.args.l:
            self.cursor.execute(
                re.sub(r'%\((.*?)\)s', r':\1', sql),
                argsdict
            )
        else:
            self.cursor.execute(sql, argsdict)

    def fetchall(self):
        return self.cursor.fetchall()
    
    def fetchone(self):
        return self.cursor.fetchone()
    
    def lastrowid(self):
        return self.cursor.lastrowid
    
    def __del__(self):
        if server.args.l:
            self.connection.commit()
            self.cursor.close()
            self.connection.close()
        else:
            server.db.connection.commit()
            self.cursor.close()
