import asyncio
import json
import uuid
import datetime
from nats.aio.client import Client as NATS

async def main():
    nc = NATS()
    
    # Using local instance port from docker-compose maps if available
    # Assuming docker-compose nats runs on 4222
    await nc.connect("nats://localhost:4222")

    js = nc.jetstream()

    # We will simulate 3 products being pushed onto the stream:
    # A wants B's category
    # B wants C's category
    # C wants A's category
    # Meaning A -> B -> C -> A
    
    events = [
        {
            "_id": str(uuid.uuid4()),
            "owner_id": "alice_uuid",
            "title": "Macbook Pro 2020",
            "emoji": "💻",
            "category": "electronics",
            "wants": {"category": "furniture"},
            "tags": ["tech", "apple"],
            "created_at": datetime.datetime.utcnow().isoformat() + "Z"
        },
        {
            "_id": str(uuid.uuid4()),
            "owner_id": "bob_uuid",
            "title": "Vintage Oak Desk",
            "emoji": "🪑",
            "category": "furniture",
            "wants": {"category": "clothing"},
            "tags": ["vintage", "wood"],
            "created_at": datetime.datetime.utcnow().isoformat() + "Z"
        },
        {
            "_id": str(uuid.uuid4()),
            "owner_id": "charlie_uuid",
            "title": "Designer Jacket",
            "emoji": "🧥",
            "category": "clothing",
            "wants": {"category": "electronics"},
            "tags": ["fashion", "designer"],
            "created_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
    ]
    
    for evt in events:
        data = json.dumps(evt).encode()
        print(f"Publishing user {evt['owner_id']} wanting {evt['wants']['category']}...")
        await js.publish("item.preference.updated", data)
        await asyncio.sleep(1) # Give goroutine workers a second to log processing

    print("✅ All 3 events published to JetStream!")
    
    await nc.drain()

if __name__ == '__main__':
    asyncio.run(main())
