import argparse

import uvicorn

from ai_shorts.web.app import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AI Shorts Studio dashboard.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=3000, type=int)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
