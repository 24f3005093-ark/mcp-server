import hashlib

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

EMAIL = "24f3005093@ds.study.iitm.ac.in".strip().lower()

app = FastAPI()

TOOL = {
    "name": "solve_challenge",
    "description": "Returns the exam answer for the challenge sent in the HTTP headers.",
    "inputSchema": {"type": "object", "properties": {}},
}


def handle(msg: dict, headers):
    """Handle ONE JSON-RPC message. Returns a reply dict, or None for notifications."""
    method = msg.get("method")
    msg_id = msg.get("id")

    # Notifications have no "id" -> we must not reply with a JSON body.
    if msg_id is None:
        return None

    if method == "initialize":
        client_version = (msg.get("params") or {}).get("protocolVersion", "2025-03-26")
        result = {
            "protocolVersion": client_version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "exam-mcp-server", "version": "1.0.0"},
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [TOOL]}
    elif method == "tools/call":
        name = (msg.get("params") or {}).get("name")
        if name != "solve_challenge":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32602, "message": f"Unknown tool: {name}"},
            }
        challenge = headers.get("x-exam-challenge", "")
        answer = hashlib.sha256(f"{challenge}:{EMAIL}".encode()).hexdigest()[:16]
        result = {"content": [{"type": "text", "text": answer}]}
    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


@app.post("/mcp")
@app.post("/")
async def mcp_endpoint(request: Request):
    body = await request.json()

    if isinstance(body, list):  # JSON-RPC batch
        replies = [r for r in (handle(m, request.headers) for m in body) if r]
        if not replies:
            return Response(status_code=202)
        return JSONResponse(replies)

    reply = handle(body, request.headers)
    if reply is None:
        return Response(status_code=202)
    return JSONResponse(reply)


@app.get("/mcp")
@app.get("/")
async def not_supported():
    # We don't offer a server-to-client stream; this is allowed by the spec.
    return Response(status_code=405, headers={"Allow": "POST"})
