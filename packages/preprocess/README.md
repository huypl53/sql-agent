# Preprocessing for Text2Sql

## Generate M-Schema

- XiYan-SQL

## Workflows

```bash

python main.py --dataset spider --db_prefix_path E:/code/AI/agentic-AI/SQL-QA/data/spider_data/test_database --tables_json_path E:/code/AI/agentic-AI/SQL-QA/data/spider_data/test_tables.json --out_metadata_path E:/code/AI/agentic-AI/SQL-QA/data/spider_data/test_metadata.json 

python index_db.py --metadata_path E:/code/AI/agentic-AI/SQL-QA/data/spider_data/test_metadata.json  --save_path output/db_index/spider_dev_test
```
