"""
Script to directly store Notion credentials in the database
"""

import asyncio
import motor.motor_asyncio
from datetime import datetime

async def store_notion_credentials():
    """Store Notion credentials directly in the database"""
    
    # Your Notion token
    notion_token = "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"
    
    # Connect to MongoDB
    client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["flowmind"]
    collection = db["integration_credentials"]
    
    # For this example, we'll use a test user ID
    # In a real scenario, you'd get this from the authenticated user
    test_user_id = "test_user_123"
    
    print("🔧 Storing Notion credentials in database...")
    
    # Check if credentials already exist
    existing_creds = await collection.find_one({
        "user_id": test_user_id,
        "integration_type": "notion"
    })
    
    if existing_creds:
        # Update existing credentials
        await collection.update_one(
            {"user_id": test_user_id, "integration_type": "notion"},
            {"$set": {
                "credentials": {"access_token": notion_token},
                "updated_at": datetime.utcnow()
            }}
        )
        print("✅ Updated existing Notion credentials")
    else:
        # Insert new credentials
        await collection.insert_one({
            "user_id": test_user_id,
            "integration_type": "notion",
            "credentials": {"access_token": notion_token},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        print(f"✅ Stored new Notion credentials with ID: {test_user_id}")
    
    print("🎉 Notion token stored successfully!")
    print("Your Notion node should now work in the workflow builder.")
    
    # Close the connection
    client.close()

if __name__ == "__main__":
    print("🔧 Notion Credentials Storage Script")
    print("=" * 50)
    
    try:
        asyncio.run(store_notion_credentials())
        print("\n✅ Script completed successfully!")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("Make sure MongoDB is running and accessible.")
    
    print("\n" + "=" * 50)
    print("Done!") 