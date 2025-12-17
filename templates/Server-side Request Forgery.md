## Description
The application contains a Server-Side Request Forgery (SSRF) vulnerability at {URL}. The application accepts a user-supplied URL and processes it without validating the destination. This allows an attacker to induce the server to make HTTP requests to arbitrary domains, including internal systems that are not exposed to the internet.

## Impact
An attacker can scan the internal network, access internal services (like Redis, weak internal APIs), or read sensitive cloud instance metadata (e.g., AWS metadata at `169.254.169.254`). In some cases, this can lead to Remote Code Execution (RCE) if vulnerable internal services are reachable.

## Validation Steps
1. Identify the input field or parameter that processes a URL (e.g., a webhook configuration or profile image upload).
2. Input a URL pointing to a service you control (like Burp Collaborator) to test for external connectivity.
3. If successful, attempt to access internal resources, such as `http://localhost`, `http://127.0.0.1`, or cloud metadata endpoints.
4. Analyze the response to see if internal data is returned or if the response time indicates a connection was made.

## Fix Recommendation
Validate and sanitize all user-supplied URLs. Implement a strict allowlist of permitted domains, protocols, and ports. Disable unused URL schemes (like `file://`, `gopher://`). If fetching external resources is required, ensure the request is made from an isolated network segment (DMZ) with restricted access to the internal network.
