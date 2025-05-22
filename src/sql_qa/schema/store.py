from typing import List, Literal, TypedDict, Optional, Dict, Set
from collections import defaultdict
from pydantic import BaseModel
import json
from sql_qa.config import settings


class Column(BaseModel):
    name: str
    type: str
    description: str
    example: Optional[str] = None


class Table(BaseModel):
    name: str
    description: Optional[str] = None
    columns: List[Column]


class Schema(BaseModel):
    name: str
    description: Optional[str] = None
    tables: Optional[List[Table]] = None
    foreign_keys: Optional[List[str]] = None

    @classmethod
    def load(cls, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        schema = Schema(**data)
        # Debug prints to show nested structure
        print(f"Schema: {schema.name}")
        return schema


class SchemaStore(BaseModel):
    schemas: Dict[str, Schema] = {}

    def get_schema(self, schema_name: str) -> Schema:
        return self.schemas[schema_name]

    def add_schema(self, schema: Schema):
        self.schemas[schema.name] = schema

    def search_tables(
        self,
        queries: List[str],
        mode: Literal["exact", "connected", "same"] = "same",
        include_foreign_keys: bool = False,
    ) -> Dict[str, Schema]:
        """
        Search for tables matching queries with two modes:
        - exact: only return tables that match the queries
        - connected: return matching tables plus all tables connected via foreign keys

        Args:
            queries: List of table names to search for
            mode: "exact" or "connected"
            include_foreign_keys: If True, only include foreign key relationships between selected tables

        Returns:
            Dict[str, Schema] with filtered schema information
        """
        # First, find all matching tables
        matching_tables: Dict[str, Set[str]] = defaultdict(set)
        for schema_name, schema in self.schemas.items():
            for table in schema.tables:
                for query in queries:
                    if mode == "same":
                        matching_tables[schema_name].add(table.name)
                        continue
                    if query.lower() in table.name.lower():
                        matching_tables[schema_name].add(table.name)

        if mode == "exact":
            return self._create_filtered_schemas(matching_tables, include_foreign_keys)

        # For connected mode, find all related tables
        connected_tables: Dict[str, Set[str]] = defaultdict(set)
        for schema_name, schema in self.schemas.items():
            if not schema.foreign_keys:
                continue

            # Add initially matching tables
            connected_tables[schema_name].update(matching_tables[schema_name])

            # Find all tables connected via foreign keys
            for fk in schema.foreign_keys:
                # Parse foreign key string (assuming format: "table1.column1 -> table2.column2")
                try:
                    source, target = fk.split(" -> ")
                    source_table = source.split(".")[0]
                    target_table = target.split(".")[0]

                    # If either table is in matching_tables, add both to connected_tables
                    if (
                        source_table in matching_tables[schema_name]
                        or target_table in matching_tables[schema_name]
                    ):
                        connected_tables[schema_name].add(source_table)
                        connected_tables[schema_name].add(target_table)
                except ValueError:
                    continue  # Skip malformed foreign key strings

        return self._create_filtered_schemas(connected_tables, include_foreign_keys)

    def _create_filtered_schemas(
        self, selected_tables: Dict[str, Set[str]], include_foreign_keys: bool
    ) -> Dict[str, Schema]:
        """Helper method to create filtered schema dictionary"""
        filtered_schemas = {}

        for schema_name, schema in self.schemas.items():
            if schema_name not in selected_tables:
                continue

            # Create new schema with only selected tables
            filtered_schema = Schema(
                name=schema.name,
                description=schema.description,
                tables=[
                    table
                    for table in schema.tables
                    if table.name in selected_tables[schema_name]
                ],
            )

            # Handle foreign keys
            if include_foreign_keys and schema.foreign_keys:
                filtered_fks = []
                for fk in schema.foreign_keys:
                    try:
                        source, target = fk.split(" -> ")
                        source_table = source.split(".")[0]
                        target_table = target.split(".")[0]

                        # Only include foreign keys between selected tables
                        if (
                            source_table in selected_tables[schema_name]
                            and target_table in selected_tables[schema_name]
                        ):
                            filtered_fks.append(fk)
                    except ValueError:
                        continue

                filtered_schema.foreign_keys = filtered_fks

            filtered_schemas[schema_name] = filtered_schema

        return filtered_schemas

    def get_schema_tables(self, schema_name: str) -> List[Table]:
        return self.get_schema(schema_name).tables


if __name__ == "__main__":
    # Load and initialize schema
    schema = Schema.load(settings.schema_path)
    store = SchemaStore()
    store.add_schema(schema)

    # Example 1: Exact match mode
    print("\n=== Exact Match Mode ===")
    exact_result = store.search_tables(
        queries=["Customer", "Invoice"],  # Chinook database tables
        mode="exact",
        include_foreign_keys=True,
    )

    print("\nExact match results:")
    for schema_name, filtered_schema in exact_result.items():
        print(f"\nSchema: {schema_name}")
        print("Tables found:")
        for table in filtered_schema.tables:
            print(f"- {table.name}")
        if filtered_schema.foreign_keys:
            print("\nForeign keys between selected tables:")
            for fk in filtered_schema.foreign_keys:
                print(f"- {fk}")

    # Example 2: Connected mode
    print("\n=== Connected Mode ===")
    connected_result = store.search_tables(
        queries=["Customer"],  # Start with Customer table
        mode="connected",
        include_foreign_keys=True,
    )

    print("\nConnected tables results:")
    for schema_name, filtered_schema in connected_result.items():
        print(f"\nSchema: {schema_name}")
        print("Tables found (including connected ones):")
        for table in filtered_schema.tables:
            print(f"- {table.name}")
        if filtered_schema.foreign_keys:
            print("\nForeign keys between all related tables:")
            for fk in filtered_schema.foreign_keys:
                print(f"- {fk}")

    # Print comparison
    print("\n=== Comparison ===")
    print(
        "Exact mode tables:", [t.name for s in exact_result.values() for t in s.tables]
    )
    print(
        "Connected mode tables:",
        [t.name for s in connected_result.values() for t in s.tables],
    )
