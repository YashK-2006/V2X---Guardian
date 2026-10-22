import asyncio

import websockets



async def main():

    try:

        async with websockets.connect('ws://127.0.0.1:8000/ws/telemetry') as ws:

            print("Connected!")

            for _ in range(3):

                msg = await ws.recv()

                print(f"Received: {msg[:200]}...")

    except Exception as e:

        print(f"Error: {e}")



if __name__ == "__main__":

    asyncio.run(main())
