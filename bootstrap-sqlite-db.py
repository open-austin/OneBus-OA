import pandas as pd
import sqlite3
import glob

conn = sqlite3.connect('db.one-bus')
for csv_file in glob.glob('data/*.csv'):
    df = pd.read_csv(csv_file)
    table_name = csv_file.replace('data/', '').replace('.csv', '')
    df.to_sql(table_name, conn, if_exists='replace', index=False)
conn.close()