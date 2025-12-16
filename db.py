import pymysql

conn = pymysql.connect(
    host="147.50.254.12",
    user="finorfin_pic",
    password="G5F&2!taRct9sdyv",
    charset="utf8"
)

def fetch_one(sql, params=None):
    cursor = conn.cursor()
    cursor.execute(sql, params or ())
    result = cursor.fetchone()
    cursor.close() 
    return result

def fetch_all(sql, params=None):
    cursor = conn.cursor()
    cursor.execute(sql, params or ())
    results = cursor.fetchall()
    cursor.close() 
    return results

def execute(sql, params=None):
    cursor = conn.cursor()
    cursor.execute(sql, params or ())
    conn.commit()
    cursor.close() 
