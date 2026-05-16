import argparse
import asyncio

from ai_shorts.agents.pm.conversational import handle_message


async def run(thread_id: str, message: str) -> str:
    return await handle_message(thread_id=thread_id, user_text=message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase 0 PM smoke handler.")
    parser.add_argument("thread_id")
    parser.add_argument("message")
    args = parser.parse_args()

    print(asyncio.run(run(thread_id=args.thread_id, message=args.message)))


if __name__ == "__main__":
    main()
