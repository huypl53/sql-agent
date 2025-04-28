from langchain_community.utilities import SQLDatabase

db = SQLDatabase.from_uri("sqlite:///Chinook.db")

if __name__ == '__main__':
    print(db.dialect)
    print(db.get_usable_table_names())
    db.run("SELECT * FROM Artist LIMIT 10;")