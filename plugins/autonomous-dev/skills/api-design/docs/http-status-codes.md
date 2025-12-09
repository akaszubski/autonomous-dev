# Http Status Codes

## HTTP Status Codes

### Success Codes (2xx)

```
200 OK                  - Request succeeded (GET, PUT, PATCH)
201 Created             - Resource created (POST)
204 No Content          - Success, no response body (DELETE)
```

**Examples**:
```python
# 200 OK - Return resource
@app.get("/users/{user_id}")
def get_user(user_id: int):
    user = db.get_user(user_id)
    return JSONResponse(content=user, status_code=200)

# 201 Created - Return created resource + Location header
@app.post("/users")
def create_user(user: User):
    created = db.create_user(user)
    return JSONResponse(
        content=created,
        status_code=201,
        headers={"Location": f"/users/{created['id']}"}
    )

# 204 No Content - No body needed
@app.delete("/users/{user_id}")
def delete_user(user_id: int):
    db.delete_user(user_id)
    return Response(status_code=204)
```

### Client Error Codes (4xx)

```
400 Bad Request         - Invalid request body/parameters
401 Unauthorized        - Authentication required
403 Forbidden           - Authenticated but not allowed
404 Not Found           - Resource doesn't exist
409 Conflict            - Conflict (e.g., duplicate email)
422 Unprocessable       - Validation error
429 Too Many Requests   - Rate limit exceeded
```

### Server Error Codes (5xx)

```
500 Internal Server Error - Unexpected server error
503 Service Unavailable   - Server temporarily down
```

---
