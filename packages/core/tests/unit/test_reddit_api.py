from datetime import UTC

import pytest
from ai_shorts.adapters.reddit_api import (
    RedditListing,
    parse_listing,
    parse_reddit_post,
    reddit_listing_path,
)
from ai_shorts.schemas.trend_item import Platform


def test_parse_reddit_post_to_trend_item() -> None:
    post = parse_reddit_post(
        {
            "data": {
                "id": "abc123",
                "subreddit": "SideProject",
                "title": "I built a useful tool",
                "author": "maker",
                "permalink": "/r/SideProject/comments/abc123/tool/",
                "url": "https://example.com/tool",
                "score": 420,
                "upvote_ratio": 0.95,
                "num_comments": 32,
                "created_utc": 1_767_312_000,
            }
        }
    )

    trend = post.to_trend_item()

    assert trend.platform == Platform.REDDIT
    assert trend.source_id == "abc123"
    assert trend.title == "I built a useful tool"
    assert trend.like_count == 420
    assert trend.comment_count == 32
    assert trend.published_at is not None
    assert trend.published_at.tzinfo == UTC
    assert trend.raw["subreddit"] == "SideProject"


def test_parse_listing() -> None:
    posts = parse_listing(
        {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "one",
                            "subreddit": "test",
                            "title": "one",
                            "permalink": "/r/test/comments/one/",
                            "url": "https://example.com/one",
                        }
                    },
                    {"kind": "more"},
                ]
            }
        }
    )

    assert [post.post_id for post in posts] == ["one"]


def test_reddit_listing_path() -> None:
    assert reddit_listing_path("SideProject", RedditListing.HOT) == "/r/SideProject/hot.json"
    assert reddit_listing_path("SideProject", RedditListing.TOP_WEEK).endswith("t=week")
    assert reddit_listing_path("SideProject", RedditListing.TOP_MONTH).endswith("t=month")
    with pytest.raises(ValueError):
        reddit_listing_path("", RedditListing.HOT)
