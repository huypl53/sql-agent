schem_linking_table_selection_prompt = """As an experienced and professional database administrator, your task is to analyze a user question and a database schema to provide relevant information. You are given an 'SQL Question', 'DB schema' containing the database schema.
Think step by step. Identify and list all the relevant tables names from the DB schema based on the user question and database schema provided. Make sure you include all of them.

SQL Question: {query}

DB schema: {schema}
    """
