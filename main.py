import os
import json
import hashlib
import requests
import psycopg2
import psycopg2.pool

from bs4 import BeautifulSoup
from psycopg2.errors import UniqueViolation
DB_USER = os.environ['DB_USER']
DB_PASS = os.environ['DB_PASS']
DB_NAME = os.environ['DB_NAME']
DB_CONNECTION = os.environ['DB_CONNECTION']
WEBHOOK = os.environ['HOOK']
URLS    = os.environ['URLS'] 

def get_connection(host):
    global pg_pool
    return psycopg2.pool.SimpleConnectionPool(10,25,
                                                               host=host,
                                                               database=DB_NAME,
                                                               user=DB_USER,
                                                               password=DB_PASS)

    #return psycopg2.connect(dbname=DB_NAME,password=DB_PASSWORD,user=DB_USER,host=host)
pg_pool = get_connection(DB_CONNECTION)

blacklist = [
	'[document]',
	'noscript',
	'header',
	'html',
	'meta',
	'head',
	'input',
	'script',
        'style',
	# there may be more elements you don't want, such as "style", etc.
]

print("\n> parse urls...")
url_hashes = {}
header = {'User-agent' : 'Mozilla/69.0 (Windows; U; Windows NT 5.1; de; rv:1.9.1.5) Gecko/20091102 Firefox/3.5.5'}
for url in URLS.split(","):
           print("\n- process url = [%s]..." % url)
           print("- get page...")
           webContent = requests.get(url, headers=header)
           print("- parse url...")
           s = BeautifulSoup(webContent.content, 'html.parser')
           text = s.find_all(text=True)
           output = ''
           for t in text:
               if t.parent.name not in blacklist:
                   output += '{} '.format(t).replace(' ', '').replace('\n', '')
           print("- calc url hash...")
           url_hashes["'" +url + "'"] =  "'" + hashlib.sha256(output.encode('utf-8')).hexdigest() + "'"
           print("- done")

print("\n> compare urls content...")
try:
    connection = pg_pool.getconn()
    if connection:
       with connection.cursor() as cursor:
           query = "SELECT page FROM pages WHERE hash NOT IN ( " + ','.join(list (url_hashes.values())) + ")"
           cursor.execute(query)
           for row in cursor.fetchall():
               if row[0] in URLS:
                   slack_data = {'text': "Page {} updated! :trollface:"}
                   slack_data['text'] = slack_data['text'].format(row[0])
                   requests.post(
                       WEBHOOK, data=json.dumps(slack_data),
                       headers={'Content-Type': 'application/json'}
                   )
                   cursor.execute ("UPDATE pages SET hash = " + url_hashes["'"+row[0]+"'"] + " WHERE page = " + "'"+ row[0]+"'" )
                   connection.commit()
finally:
    if (connection):
        pg_pool.putconn(connection)

# in this code we're inserting rows identidied as new into db
print("\n> save new urls hashes...")
try:
    connection = pg_pool.getconn()
    if connection:
       with connection.cursor() as cursor:
           pages = "select page from pages"
           cursor.execute(pages)

           pages_list_n = list( sum(cursor.fetchall(),()))
           for p in pages_list_n:
               print (p)
           for url in url_hashes.keys():
               url = url.replace ("'",'')
               if url not in pages_list_n:
                   try:
                      cursor.execute("INSERT INTO pages (page, hash) VALUES (" + "'"+ url +"'" +","+ url_hashes["'" + url + "'"] + ")")
                      connection.commit()
                   except UniqueViolation:
                      connection.commit()



finally:
    if (connection):
        pg_pool.putconn(connection)
