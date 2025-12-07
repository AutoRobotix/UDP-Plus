import asyncio
from udp_plus import UDP_Plus

async def main():
    # Start UDP Plus instance
    udp_plus = UDP_Plus('127.0.0.1', 25252)
    await udp_plus.start()

    # Send a message directly using put_message
    await udp_plus.put_message('127.0.0.1', 25252, 'Hello, World!')

    # Wait for a message to be available in recv bucket
    sender, msg = await udp_plus.get_message()

    # Show message
    print(f'{sender}: {msg}')

    # Stop
    udp_plus.stop()  

asyncio.run(main())