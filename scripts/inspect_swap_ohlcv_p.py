import asyncio

from sqlalchemy import text

from src.database import get_async_session


async def main():
    async for session in get_async_session():
        cols_res = await session.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name='swap_ohlcv_p' ORDER BY ordinal_position"
            )
        )
        cols = cols_res.fetchall()
        print("columns:")
        for c in cols:
            print(" -", c)

        try:
            sample_res = await session.execute(
                text("SELECT * FROM swap_ohlcv_p LIMIT 3")
            )
            rows = sample_res.fetchall()
            print("sample rows (3):", len(rows))
            for r in rows:
                print(r)
        except Exception as e:
            print("sample error:", type(e).__name__, str(e))
        break


if __name__ == "__main__":
    asyncio.run(main())
