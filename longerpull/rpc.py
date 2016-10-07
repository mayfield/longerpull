"""
Run commands on LP clients.
"""

async def call(conn, poll_id, request):
    await conn.send(poll_id, {
        "response_queue": None,
        "response_id": None,
        "request": request
    })
