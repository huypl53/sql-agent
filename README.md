# SQL QA Project

This is a SQL Question Answering application that allows users to interact with a database using natural language. The application uses LangChain and Mistral AI to translate natural language questions into SQL queries and provide answers.

## Project Structure

```text
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

```mermaid

sequenceDiagram
    participant User
    participant System as Text2SQL System
    participant SchemaSelector
    participant PromptEngine
    participant Generator
    participant Validator
    participant Executor

    Note over System: Main Flow with Optional Components

    User->>System: "Show me all customers from California"
    
    Note right of System: 1. Schema Selection<br/>- Analyzes question<br/>- Selects relevant tables<br/>- Returns focused schema
    System->>SchemaSelector: Find relevant tables
    SchemaSelector-->>System: Selected tables (customers, addresses)
    
    Note right of System: 2. Prompt Construction<br/>- Builds LLM prompt<br/>- Optional: Add examples<br/>- Optional: Add metadata
    System->>PromptEngine: Create prompt(question + schema)
    Note over PromptEngine: Optional Features:<br/>• Few-shot examples<br/>• Chain-of-thought<br/>• Metadata enrichment
    PromptEngine-->>System: Formatted prompt
    
    Note right of System: 3. SQL Generation<br/>- Multiple strategies (optional)<br/>- Multiple LLMs (optional)<br/>- Candidate ranking
    System->>Generator: Generate SQL(prompt)
    Note over Generator: Generation Options:<br/>• Direct generation<br/>• Chain-of-thought<br/>• Few-shot learning<br/>• Multiple candidates
    Generator-->>System: SQL candidate(s)
    
    Note right of System: 4. Validation & Fixing<br/>- Syntax check<br/>- Schema validation<br/>- Auto-fix if needed
    System->>Validator: Validate & fix SQL
    Note over Validator: Validation Steps:<br/>• Syntax checking<br/>• Schema validation<br/>• Auto-fixing with LLM<br/>• Re-validation
    Validator-->>System: Valid SQL
    
    Note right of System: 5. Execution<br/>- Safe execution<br/>- Result evaluation<br/>- Feedback collection
    System->>Executor: Execute SQL
    Note over Executor: Execution Features:<br/>• Query sanitization<br/>• Time limits<br/>• Result evaluation<br/>• Feedback collection
    Executor-->>System: Query results
    
    System-->>User: Display results + SQL query
    
    Note over User, Executor: Optional Feedback Loop:<br/>User feedback → Example store → Improved future queries
```

## Prerequisites

- Python 3.10+

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
uv sync
```

4. Set up environment variables:
   - Create a `.env` file in the project root using `.env.example`

5. Generate sample database (if using SQLite):

```bash
curl -s https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_Sqlite.sql | sqlite3 Chinook.db
```

## Usage

Run the application:

```bash
# API version
uv run uvicorn src.sql_qa.cli:app --reload --port 8000

# Then test
curl -X POST http://localhost:8000/v1/chat/completions \
-H "Content-Type: application/json" \
-d '{
  "model": "gpt-3.5-turbo",
  "messages": [
    {
      "role": "user",
      "content": "có bao nhiêu khách hàng trong CSDL?"
    }
  ],
  "temperature": 0.7,
  "stream": false
}'

# UI version
uv run streamlit run ./src/sql_qa/ui.py

# Benchmark 
uv run ./cli.py benchmark --file data/GSV/generated-data/gen_success_data.csv

# Evaluation
# For separate files
python -m src.sql_qa.metrics.evaluation evaluate-files \
    --predicted-file predicted_queries.sql \
    --ground-truth-file ground_truth_queries.sql \
    --output-file results.json

# For CSV file
python -m src.sql_qa.metrics.evaluation evaluate-csv \
    --input-file benchmark_results.csv \
    --output-file results.json
```

Options:

- `--verbose`: Enable verbose mode to see agent thoughts (default: True)

## License

[Specify your license here]

## Challenges

```text
E:\code\AI\agentic-AI\SQL-QA\.venv\Lib\site-packages\langchain_community\utilities\sql_database.py:348: SAWarning: Cannot correctly sort tables; there are unresolvable cycles between tables "employee, examination, package, patient, return_customer, user", which is usually caused by mutually dependent foreign key constraints.  Foreign key constraints involving these tables will not be considered; this warning may raise an error in a future release.
```
