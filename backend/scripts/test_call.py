"""
Quick smoke test: initiate a test call to a Twilio echo number.
Run with: python3 scripts/test_call.py
"""

import asyncio
import json
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:8765")

# Twilio's echo test number — reads back what you say
ECHO_TEST_NUMBER = "+15005550006"  # Twilio magic test number (no actual PSTN)

TEST_JOB = {
    "job_id": "test-001",
    "to_number": ECHO_TEST_NUMBER,
    "negotiation_type": "bill_lower_rate",
    "context": {
        "provider": "comcast",
        "current_bill": "$94",
        "target": "$65",
        "walkaway": "$80",
        "tenure": 3,
        "service_type": "Internet 400 Mbps",
        "leverage_points": "1. T-Mobile Home Internet $50/mo\n2. 3-year tenure on autopay\n3. No-bundle status",
    },
}


async def main():
    async with aiohttp.ClientSession() as session:
        print(f"Starting test call via {SERVER_URL}/outbound ...")
        async with session.post(f"{SERVER_URL}/outbound", json=TEST_JOB) as resp:
            result = await resp.json()
            print(f"Response: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
