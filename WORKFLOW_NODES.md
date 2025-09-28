# Workflow Automation Nodes Documentation

This document provides an overview of the available workflow nodes and their functionality in the workflow automation system.

## Condition Node

The condition node allows you to create branching logic in your workflows based on various conditions.

### Features:

- Supports multiple paths with True/False branching
- Provides detailed evaluation of each condition for debugging
- Supports nested field access with dot notation
- Automatically converts data types for comparison (string, number, boolean)

### Available Operators:

- `==` (equals)
- `!=` (not equals)
- `>` (greater than)
- `>=` (greater than or equal to)
- `<` (less than)
- `<=` (less than or equal to)
- `contains` (checks if a string/array/object contains a value)
- `not_contains` (checks if a string/array/object does not contain a value)
- `startswith` (checks if a string starts with a value)
- `endswith` (checks if a string ends with a value)
- `is_empty` (checks if a value is empty or null)
- `is_not_empty` (checks if a value is not empty or null)
- `matches_regex` (checks if a string matches a regex pattern)
- `in_list` (checks if a value is in a list)
- `not_in_list` (checks if a value is not in a list)
- `length_equals` (checks if the length equals a value)
- `length_greater_than` (checks if the length is greater than a value)
- `length_less_than` (checks if the length is less than a value)
- `date_before` (checks if a date is before another date)
- `date_after` (checks if a date is after another date)
- `date_equals` (checks if a date equals another date)
- `date_between` (checks if a date is between two dates)
- `type_equals` (checks if the type matches a specified type)

### Logical Operators:

- `AND` - All conditions must be true
- `OR` - At least one condition must be true

### Example:

A condition node could check if a value meets certain criteria, such as:
- If the temperature is greater than 75°F, follow path 1
- If the temperature is less than or equal to 75°F, follow path 2

## Merge Node

The merge node combines data from multiple sources or paths in the workflow.

### Features:

- Supports accessing nested fields with dot notation
- Provides various merge operations for different data types
- Handles error cases gracefully

### Merge Functions:

- **Pick First**: Uses the first non-null value from the input paths
- **Join All**: Joins all values (with customizable delimiter for text)
- **Concatenate Arrays**: Combines multiple arrays into a single array
- **Merge Objects**: Deeply merges multiple JSON objects
- **Average**: Calculates the average of numeric values
- **Min**: Finds the minimum value
- **Max**: Finds the maximum value
- **Create Object**: Creates a new object with keys from path names and values from those paths

### Example:

A merge node could combine user data from different sources, like:
- Merging profile information from a database with preferences from an API
- Combining results from multiple API calls into a single response

## Time Node

The time node provides various time-related operations and formatting.

### Features:

- Supports multiple time zones
- Can parse dates from various formats
- Provides time arithmetic operations
- Outputs comprehensive time information

### Time Operations:

- **current_time**: Get the current time
- **parse_input**: Parse a date/time from input
- **add_time**: Add a specified time period
- **subtract_time**: Subtract a specified time period
- **start_of**: Get the start of a time period (day, week, month, quarter, year)
- **end_of**: Get the end of a time period (day, week, month, quarter, year)
- **next_weekday**: Get the next occurrence of a specific weekday
- **previous_weekday**: Get the previous occurrence of a specific weekday

### Time Units:

- Seconds
- Minutes
- Hours
- Days
- Weeks
- Months
- Years
- Business days (skips weekends)

### Example:

A time node could be used to:
- Get the current time in a specific timezone
- Calculate a deadline by adding business days to the current date
- Find the start of the current month for reporting purposes

## Text to SQL Node

The text to SQL node converts natural language queries to SQL statements using AI.

### Features:

- Supports multiple database types (MySQL, PostgreSQL, SQLite, SQL Server, Oracle)
- Provides query validation and optional execution
- Offers query explanation in plain language
- Supports parameter substitution in queries
- Maintains a history of successful queries for reference

### Database Types:

- MySQL/MariaDB
- PostgreSQL
- SQLite
- SQL Server
- Oracle

### Example:

A text to SQL node could be used to:
- Convert "Find all customers who made a purchase last month" into a proper SQL query
- Execute the generated query against a database
- Provide a plain language explanation of what the query does

## General Node Features

All workflow nodes include:

- **Detailed Logging**: Comprehensive logging for debugging purposes
- **Error Handling**: Graceful error handling with meaningful error messages
- **Execution Timing**: Performance metrics for each node execution
- **Input Type Handling**: Automatic conversion of input types where possible 