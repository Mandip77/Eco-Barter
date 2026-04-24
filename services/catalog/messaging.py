import os
import logging
from nats.aio.client import Client as NATS
from nats.js.errors import NotFoundError
import json

logger = logging.getLogger(__name__)

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
STREAM_NAME = "ECOBARTER"
SUBJECT_PATTERN = "item.preference.*"
PUBLISH_SUBJECT = "item.preference.updated"

class Messaging:
    nc = NATS()
    js = None

messaging = Messaging()

async def connect_to_nats():
    logger.info("Connecting to NATS...")
    nats_token = os.getenv("NATS_AUTH_TOKEN")
    connect_kwargs = {"servers": NATS_URL, "token": nats_token} if nats_token else {"servers": NATS_URL}
    try:
        await messaging.nc.connect(**connect_kwargs)
        messaging.js = messaging.nc.jetstream()
        
        # Ensure stream exists
        try:
            await messaging.js.stream_info(STREAM_NAME)
            logger.info(f"Stream '{STREAM_NAME}' already exists.")
        except NotFoundError:
            logger.info(f"Stream '{STREAM_NAME}' not found, creating it...")
            await messaging.js.add_stream(name=STREAM_NAME, subjects=[SUBJECT_PATTERN])
            logger.info(f"Stream '{STREAM_NAME}' created successfully.")
            
        logger.info("Connected to NATS and initialized JetStream.")
    except Exception as e:
        logger.error(f"Failed to connect to NATS or setup JetStream: {e}")

async def close_nats_connection():
    if messaging.nc.is_connected:
        logger.info("Closing NATS connection...")
        await messaging.nc.close()
        logger.info("NATS connection closed.")

async def publish_preference_update(product_dict: dict):
    if messaging.js is None:
        logger.warning("JetStream not initialized, skipping publish.")
        return
    
    try:
        payload = json.dumps(product_dict, default=str).encode('utf-8')
        ack = await messaging.js.publish(PUBLISH_SUBJECT, payload)
        logger.info(f"Published event to {PUBLISH_SUBJECT}, seq: {ack.seq}")
    except Exception as e:
        logger.error(f"Failed to publish event to {PUBLISH_SUBJECT}: {e}")
