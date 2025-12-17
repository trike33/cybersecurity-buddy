## Description
The application is vulnerable to SQL Injection. A parameter at {URL} is directly used in a database query.

## Impact
Successful exploitation could lead to unauthorized access to sensitive data or full server compromise.

## Validation Steps
1. Identify vulnerable parameter.
2. Submit payload `' OR 1=1 --`.
3. Confirm altered response.

## Fix Recommendation
Use parameterized queries (prepared statements) for all database interactions.
