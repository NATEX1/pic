import pymysql

def get_connection():
    return pymysql.connect(
        host="147.50.254.12",
        user="finorfin_pic",
        password="G5F&2!taRct9sdyv",
        database='pic_2',
        charset="utf8",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=60,
        read_timeout=120,
        write_timeout=120
    )

def fetch_one(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchone()
    finally:
        conn.close()

def fetch_all(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchall()
    finally:
        conn.close()

def execute(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            conn.commit()
    finally:
        conn.close()

def executemany(sql, params):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.executemany(sql, params)
            conn.commit()
    finally:
        conn.close()
