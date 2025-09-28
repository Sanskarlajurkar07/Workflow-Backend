# Workflow Nodes Documentation

This document provides detailed information about the specialized workflow nodes available in the FlowMind AI platform.

## Table of Contents

1. [Condition Node](#condition-node)
2. [Merge Node](#merge-node)
3. [Time Node](#time-node)
4. [Text to SQL Node](#text-to-sql-node)

---

## Condition Node

The Condition Node enables decision-making within your workflows, allowing you to create branching paths based on input data.

### Parameters

| Parameter | Description |
|-----------|-------------|
| `paths` | Array of path objects, each containing clauses and a logical operator |
| `selectedType` | Type of comparison to make (text, number, date, etc.) |

### Path Structure

Each path contains:

- `id`: Unique identifier for the path
- `clauses`: Array of condition clauses
- `logicalOperator`: `AND` or `OR` operator to combine clauses

### Clause Structure

Each clause contains:

- `id`: Unique identifier for the clause
- `inputField`: The field from input data to evaluate (supports dot notation for nested fields)
- `operator`: Comparison operator (see below)
- `value`: Value to compare against

### Supported Operators

#### Text Operators
- `==`: Equals
- `!=`: Not equals
- `contains`: Text contains substring
- `startswith`: Text starts with substring
- `endswith`: Text ends with substring
- `is_empty`: Field is empty (null, empty string, empty array, or empty object)
- `is_not_empty`: Field is not empty
- `matches_regex`: Field matches a regular expression

#### Number Operators
- `==`: Equals
- `!=`: Not equals
- `>`: Greater than
- `>=`: Greater than or equal to
- `<`: Less than
- `<=`: Less than or equal to

#### Date Operators
- `date_before`: Date is before specified date
- `date_after`: Date is after specified date
- `date_equals`: Date is the same as specified date (ignores time)

### Example

```json
{
  "type": "condition",
  "data": {
    "params": {
      "paths": [
        {
          "id": "path_0",
          "clauses": [
            {
              "id": "clause_0", 
              "inputField": "status", 
              "operator": "==", 
              "value": "active"
            }
          ],
          "logicalOperator": "AND"
        },
        {
          "id": "path_1",
          "clauses": [
            {
              "id": "clause_1", 
              "inputField": "created_date", 
              "operator": "date_after", 
              "value": "2023-01-01"
            }
          ],
          "logicalOperator": "AND"
        }
      ]
    }
  }
}
```

---

## Merge Node

The Merge Node combines data from multiple paths, typically used after a Condition Node to recombine workflow paths.

### Parameters

| Parameter | Description |
|-----------|-------------|
| `paths` | Array of path identifiers to merge |
| `function` | Merge strategy to apply (see below) |
| `type` | Data type of the output |
| `joinDelimiter` | Delimiter for text joins (when function = "Join All" and type = "Text") |

### Merge Functions

- **Pick First**: Uses the first non-null value from the paths
- **Join All**: Combines all values into a single result
  - For Text: Joins with delimiter
  - For Integer/Float: Sums values
  - For JSON/Any: Returns array of all values
- **Concatenate Arrays**: Joins arrays from all paths into a single array
- **Merge Objects**: Deep merges objects from all paths, with later paths overriding earlier ones

### Example

```json
{
  "type": "merge",
  "data": {
    "params": {
      "paths": ["path1", "path2", "path3"],
      "function": "Join All",
      "type": "Text",
      "joinDelimiter": ", "
    }
  }
}
```

---

## Time Node

The Time Node provides timezone-aware date and time information and calculations.

### Parameters

| Parameter | Description |
|-----------|-------------|
| `timezone` | Timezone to use (e.g., "UTC", "America/New_York") |
| `operation` | Time operation to perform (default: "current_time") |
| `modifyValue` | Value for time arithmetic operations |
| `modifyUnit` | Unit for time arithmetic (seconds, minutes, hours, days, weeks, months, years) |
| `customFormat` | Custom date/time format string (using strftime format) |

### Operations

- **current_time**: Returns the current time in the specified timezone
- **add_time**: Adds the specified time value to the current time
- **subtract_time**: Subtracts the specified time value from the current time

### Output Fields

The Time Node outputs a rich object with many time-related fields:

- `iso`: ISO 8601 formatted date/time
- `timestamp`: Unix timestamp (seconds since epoch)
- `year`, `month`, `day`, `hour`, `minute`, `second`: Individual components
- `timezone`: The timezone used
- `formatted`: Standard formatted time string
- `human_readable`: Human-friendly time string
- `custom_formatted`: Time formatted according to customFormat
- `day_of_week`: Name of the day of the week
- `month_name`: Name of the month
- `unix_timestamp`: Integer unix timestamp
- `is_dst`: Whether daylight saving time is in effect
- `utc_offset`: Hours offset from UTC

### Example

```json
{
  "type": "time",
  "data": {
    "params": {
      "timezone": "America/New_York",
      "operation": "add_time",
      "modifyValue": 2,
      "modifyUnit": "days",
      "customFormat": "%B %d, %Y at %I:%M %p"
    }
  }
}
```

---

## Text to SQL Node

The Text to SQL Node converts natural language queries to SQL statements using AI.

### Parameters

| Parameter | Description |
|-----------|-------------|
| `query` | Natural language query to convert to SQL |
| `schema` | Database schema definition (tables, columns, etc.) |
| `database` | Database type (MySQL, PostgreSQL, etc.) |
| `parameters` | Optional parameters to influence SQL generation |
| `validateOnly` | If true, only validates the SQL without executing |
| `executeQuery` | If true, attempts to execute the SQL against a database |
| `connectionString` | Connection string for database execution |

### Output Fields

- `sql`: The generated SQL query
- `original_query`: The original natural language query
- `database_type`: The target database type
- `validation`: Results of SQL validation
- `execution`: Results of query execution (if executed)

### Example

```json
{
  "type": "ttsql",
  "data": {
    "params": {
      "query": "Find all active users who joined after January 2023",
      "schema": "CREATE TABLE users (id INT, username VARCHAR(50), status VARCHAR(20), joined_date DATE);",
      "database": "MySQL",
      "parameters": {
        "limit": 100
      },
      "validateOnly": true
    }
  }
}
```

---

## Integration with Other Nodes

These specialized nodes work together to create powerful workflows:

1. **Decision Making**: Use Condition Nodes to evaluate data and branch workflows
2. **Path Recombination**: Use Merge Nodes to bring together branched paths
3. **Time Awareness**: Use Time Nodes to add temporal logic
4. **Data Transformation**: Use Text to SQL Nodes to convert natural language to SQL

For best results, follow this pattern:

1. Input → Process → Condition → Specialized Processing → Merge → Output
2. Use Time Nodes to timestamp operations or modify schedules
3. Use Text to SQL Nodes when interfacing with databases 