from fastapi import FastAPI, Query
import praw
import os
from dotenv import load_dotenv
import time
from datetime import datetime
from BackEnd.controllers import sentiment_controller

app = FastAPI()

load_dotenv()

reddit = praw.Reddit(
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    user_agent=os.getenv("USER_AGENT")
)

# Include the router from the sentiment controller
app.include_router(sentiment_controller.router)

@app.get("/reddit-posts/")
def get_latest_reddit_posts(subreddit: str = Query(..., description="Subreddit name to fetch posts from")):
    subreddit_obj = reddit.subreddit(subreddit)  # Use the user-specified subreddit
    posts = []

    # Get current time in UNIX timestamp and calculate the time for 7 days ago
    current_time = int(time.time())  # Current time in UNIX timestamp
    seven_days_ago = current_time - (7 * 24 * 60 * 60)  # Subtract 7 days (in seconds)

    # Fetch the latest 100 posts from the specified subreddit
    for post in subreddit_obj.new(limit=1100):
        # Filter only posts created in the last 7 days
        if post.created_utc >= seven_days_ago:
            posts.append({
                "title": post.title,
                "body": post.selftext,
                "created": datetime.utcfromtimestamp(post.created_utc).strftime('%Y-%m-%d'),
                "score": post.score,
            })

    return {"posts": posts}