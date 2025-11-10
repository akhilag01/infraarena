"""
Wrapper that catches all errors and returns them as HTTP responses
"""
import sys
import traceback
import json

def handler(event, context):
    """Wrapper handler that catches and reports all errors"""
    try:
        # Try to import and run the main handler
        from main import handler as main_handler
        return main_handler(event, context)
    except Exception as e:
        # Return the error as an HTTP response so we can see it
        error_info = {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "python_version": sys.version,
            "event_keys": list(event.keys()) if isinstance(event, dict) else str(type(event))
        }
        
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps(error_info, indent=2)
        }
