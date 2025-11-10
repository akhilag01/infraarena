import sys
import os
import traceback

# Diagnostic endpoint to see what's failing
def handler(event, context):
    try:
        # Test 1: Basic Python
        result = {
            "status": "running",
            "python_version": sys.version,
            "platform": sys.platform,
            "cwd": os.getcwd(),
            "env_vars": {
                "SUPABASE_URL": "set" if os.getenv("SUPABASE_URL") else "missing",
                "SUPABASE_KEY": "set" if os.getenv("SUPABASE_KEY") else "missing",
                "OPENAI_API_KEY": "set" if os.getenv("OPENAI_API_KEY") else "missing",
            }
        }
        
        # Test 2: Import FastAPI
        try:
            from fastapi import FastAPI
            result["fastapi"] = "ok"
        except Exception as e:
            result["fastapi"] = f"error: {str(e)}"
        
        # Test 3: Import Mangum
        try:
            from mangum import Mangum
            result["mangum"] = "ok"
        except Exception as e:
            result["mangum"] = f"error: {str(e)}"
        
        # Test 4: Import OpenAI
        try:
            from openai import OpenAI
            result["openai"] = "ok"
        except Exception as e:
            result["openai"] = f"error: {str(e)}"
        
        # Test 5: Import Supabase
        try:
            from supabase import create_client
            result["supabase"] = "ok"
        except Exception as e:
            result["supabase"] = f"error: {str(e)}"
        
        # Test 6: Import ElevenLabs
        try:
            from elevenlabs import ElevenLabs
            result["elevenlabs"] = "ok"
        except Exception as e:
            result["elevenlabs"] = f"error: {str(e)}"
        
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": str(result)
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/plain"},
            "body": f"ERROR: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        }
