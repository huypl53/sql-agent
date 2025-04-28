# SQL QA Project

This is a SQL Question Answering application that allows users to interact with a database using natural language. The application uses LangChain and Mistral AI to translate natural language questions into SQL queries and provide answers.

## Project Structure

```
SQL-QA
├── main.py                 # Main application entry point
├── shared/                 # Shared utilities
│   └── src/
│       └── shared/
│           ├── db.py       # Database connection utilities
│           └── logger.py   # Logging utilities
├── logs/                   # Log files directory
├── requirements.txt        # Project dependencies
└── README.md              # Project documentation
```

## Features

- Natural language to SQL query translation
- Interactive command-line interface
- Comprehensive logging of all interactions
- Support for various SQL databases (MySQL, SQLite)
- Verbose mode for debugging and understanding agent reasoning

## Prerequisites

- Python 3.8+
- Mistral AI API key
- Database connection (optional, defaults to SQLite Chinook sample database)

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd SQL-QA
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
# On Windows
.venv\Scripts\activate
# On Unix or MacOS
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Set up environment variables:
   - Create a `.env` file in the project root
   - Add your Mistral AI API key: `MISTRAL_API_KEY=your_api_key`
   - Optionally add database connection string: `DB_CONN=mysql+pymysql://username:password@host:port/database_name`

5. Generate sample database (if using SQLite):

```bash
curl -s https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_Sqlite.sql | sqlite3 Chinook.db
```

## Usage

Run the application:

```bash
python main.py
```

Options:

- `--verbose`: Enable verbose mode to see agent thoughts (default: True)

The application will prompt you to enter questions about the database. Type your questions in natural language, and the agent will translate them to SQL queries and provide answers.

To exit the application, type `q` or `quit`.

## Logging

All interactions are logged to the `logs/` directory. Log files include:

- User input
- Agent responses
- Agent thoughts (in verbose mode)
- Any errors or warnings

Log files use UTF-8 encoding to support international characters.

## Troubleshooting

If you encounter encoding errors when logging, ensure that:

1. The logs directory exists
2. Your system supports UTF-8 encoding
3. The logger is properly configured with UTF-8 encoding (already implemented)

## License

[Specify your license here]

## SQL agnet

## Challenges

```text
E:\code\AI\agentic-AI\SQL-QA\.venv\Lib\site-packages\langchain_community\utilities\sql_database.py:348: SAWarning: Cannot correctly sort tables; there are unresolvable cycles between tables "employee, examination, package, patient, return_customer, user", which is usually caused by mutually dependent foreign key constraints.  Foreign key constraints involving these tables will not be considered; this warning may raise an error in a future release.
```
