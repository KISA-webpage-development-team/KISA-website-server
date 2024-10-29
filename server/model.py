"""KISAWEB model (connection with mySQL database)."""
import server
import MySQLdb.cursors

class Cursor:
    def __init__(self):
        self.cursor = server.db.connection.cursor(MySQLdb.cursors.DictCursor)
    
    def execute(self, sql, argsdict):
        self.cursor.execute(sql, argsdict)

    def fetchall(self):
        return self.cursor.fetchall()
    
    def fetchone(self):
        return self.cursor.fetchone()
    
    def lastrowid(self):
        return self.cursor.lastrowid
    
    def __del__(self):
        server.db.connection.commit()
        self.cursor.close()
