## Description
The application is vulnerable to Cross-Site Scripting (XSS). The endpoint at {URL} does not properly sanitize user-supplied input.

## Impact
An attacker could hijack user sessions, deface the website, or redirect users to malicious sites.

## Validation Steps
1. Navigate to the vulnerable URL.
2. Insert a standard XSS payload.
3. Observe execution.

## Fix Recommendation
Implement context-aware output encoding on all user-supplied data. Utilize CSP.
