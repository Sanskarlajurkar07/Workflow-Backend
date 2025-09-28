# Test imports for backend server
try:
    import fastapi
    print("✅ Successfully imported fastapi")
except ImportError as e:
    print(f"❌ Failed to import fastapi: {e}")

try:
    import uvicorn
    print("✅ Successfully imported uvicorn")
except ImportError as e:
    print(f"❌ Failed to import uvicorn: {e}")

try:
    import motor
    print("✅ Successfully imported motor")
except ImportError as e:
    print(f"❌ Failed to import motor: {e}")

try:
    import redis
    print("✅ Successfully imported redis")
except ImportError as e:
    print(f"❌ Failed to import redis: {e}")

try:
    import pydantic_settings
    print("✅ Successfully imported pydantic_settings")
except ImportError as e:
    print(f"❌ Failed to import pydantic_settings: {e}")

# Try to import from the main module
try:
    import main
    print("✅ Successfully imported main module")
except ImportError as e:
    print(f"❌ Failed to import main module: {e}")
    import traceback
    traceback.print_exc() 