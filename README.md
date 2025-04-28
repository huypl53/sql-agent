# Hello World Project

This is a simple "Hello World" application written in Python. It demonstrates the basic structure of a Python project.

## Project Structure

```
hello-world-project
├── src
│   └── main.py
├── requirements.txt
└── README.md
```

## How to Run

1. Generate sample database

```bash
curl -s https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_Sqlite.sql | sqlite3 Chinook.db
```

2. Ensure you have Python installed on your machine.
3. Navigate to the project directory.
4. Run the application using the following command:

```
python src/main.py
```

This will output "Hello, World!" to the console.
