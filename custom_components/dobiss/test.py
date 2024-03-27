import dobiss
import time
import sys
import asyncio

DEFAULT_IP = "192.168.1.118"
DEFAULT_PORT = 10001


async def main():
    # IP address of the installation
    ip = DEFAULT_IP
    if len(sys.argv) > 1:
        ip = str(sys.argv[1])

    # TCP port
    port = DEFAULT_PORT
    if len(sys.argv) > 2:
        port = int(sys.argv[2])

    d = dobiss.DobissSystem(ip, port)
    await d.importFullInstallation()
    await d.requestAllStatus()

    while True:
        time.sleep(1)
        await d.requestAllStatus()
        print(f"time: ", time.time(), " value: ", d.values)
        # print(d.values)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())