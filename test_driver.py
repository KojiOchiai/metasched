import asyncio

from maholocon.driver import MaholoDriver


async def main():
    driver = MaholoDriver()
    res = await driver.run("getimage")
    print(res)


if __name__ == "__main__":
    asyncio.run(main())
