#!/usr/bin/env python3
"""
Debug WebSocket Connection Script

This script tests the WebSocket connection to the mission control dashboard
and provides detailed debugging information.
"""

import asyncio
import json
import logging
import websockets
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_websocket_connection():
    """Test WebSocket connection to mission control endpoint."""
    
    # WebSocket URL - update with your actual server domain
    websocket_url = "wss://monitor.yspanel.com/ws/mission-control"  # Change to your server URL
    
    logger.info(f"Testing WebSocket connection to: {websocket_url}")
    
    try:
        # Connect to WebSocket
        async with websockets.connect(websocket_url) as websocket:
            logger.info("✅ WebSocket connection established successfully!")
            
            # Listen for messages
            message_count = 0
            start_time = datetime.now()
            
            async for message in websocket:
                message_count += 1
                elapsed = (datetime.now() - start_time).total_seconds()
                
                try:
                    # Try to parse as JSON
                    parsed_message = json.loads(message)
                    message_type = parsed_message.get('type', 'unknown')
                    
                    logger.info(f"📨 Message #{message_count} ({elapsed:.1f}s): Type='{message_type}'")
                    
                    if message_type == 'connection_established':
                        logger.info("🎉 Connection confirmation received!")
                    elif message_type == 'error':
                        logger.error(f"❌ Error message: {parsed_message.get('message', 'Unknown error')}")
                    elif message_type == 'dashboard_update':
                        # For dashboard updates, just log a summary
                        logger.info("📊 Dashboard update received")
                    else:
                        logger.info(f"📄 Raw message preview: {message[:200]}...")
                        
                except json.JSONDecodeError:
                    # Not JSON, log as plain text
                    logger.info(f"📄 Plain text message: {message[:200]}...")
                
                # Stop after receiving 5 messages for testing
                if message_count >= 5:
                    logger.info("✅ Test completed successfully! Received 5 messages.")
                    break
                    
    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"❌ WebSocket connection closed: {e}")
    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"❌ WebSocket connection failed with status code: {e}")
    except websockets.exceptions.InvalidURI as e:
        logger.error(f"❌ Invalid WebSocket URI: {e}")
    except ConnectionRefusedError:
        logger.error("❌ Connection refused. Is the server running on localhost:8000?")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")

async def test_basic_api_connection():
    """Test basic API connection first."""
    import aiohttp
    
    api_url = "https://monitor.yspanel.com/api/mission-control/test"  # Change to your server URL
    logger.info(f"Testing basic API connection to: {api_url}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ API connection successful: {data}")
                else:
                    logger.error(f"❌ API returned status {response.status}")
    except Exception as e:
        logger.error(f"❌ API connection failed: {e}")

async def main():
    """Main function to run all tests."""
    logger.info("🚀 Starting WebSocket connection debug test...")
    
    # Test basic API first
    await test_basic_api_connection()
    
    # Wait a moment
    await asyncio.sleep(1)
    
    # Test WebSocket connection
    await test_websocket_connection()
    
    logger.info("🏁 Debug test completed!")

if __name__ == "__main__":
    asyncio.run(main())
