"""
Absolute minimal test to see if basic handler works
"""

def handler(event, context):
    """Minimal handler for testing"""
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": '{"status": "ok", "message": "Minimal handler works!"}'
    }
