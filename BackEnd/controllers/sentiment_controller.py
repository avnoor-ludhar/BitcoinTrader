from fastapi import APIRouter, HTTPException, Query
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from pydantic import BaseModel
from typing import List
from datetime import date, datetime
from BackEnd.database.database import get_connection
import praw
import os

# Create a router instance for the sentiment endpoints
router = APIRouter()

reddit = praw.Reddit(
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    user_agent=os.getenv("USER_AGENT")
)

# Define the Pydantic model for request validation
class DailySentiment(BaseModel):
    date: date
    compound_score: float
    positive_score: float = 0
    neutral_score: float = 0
    negative_score: float = 0

class RedditPost(BaseModel):
    title: str
    body: str
    created: date  # Use a string to store the formatted date
    score: int

class RedditPostsRequest(BaseModel):
    posts: List[RedditPost]

class DateRequest(BaseModel):
    date: date

# Instantiate the VADER sentiment analyzer
analyzer = SentimentIntensityAnalyzer()

@router.post("/daily-sentiment-by-date/", response_model=DailySentiment)
def get_daily_sentiment_by_date(date_request: DateRequest):
    date = date_request.date  # Access the date from the request body
    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM daily_sentiment WHERE date = %s"
        cursor.execute(query, (date,))
        result = cursor.fetchone()
        print(result)

        if result is None:
            raise HTTPException(status_code=404, detail="No sentiment data found for the given date")

        return DailySentiment(
            date=result['date'],
            positive_score=result['positive_score'],
            neutral_score=result['neutral_score'],
            negative_score=result['negative_score'],
            compound_score=result['compound_score']
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"{str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.post("/calculate_sentiment/")
def calculate_sentiment(data: RedditPostsRequest):
    weighted_scores = []
    total_reddit_score = 0

    for post in data.posts:
        compound_score = analyzer.polarity_scores(f"{post.title} {post.body}")["compound"]
        weighted_score = compound_score * post.score
        weighted_scores.append(weighted_score)
        total_reddit_score += post.score

    if(total_reddit_score > 0):
        weighted_compound_score = sum(weighted_scores) / total_reddit_score
    else:
        weighted_compound_score = 0

    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = """
        INSERT INTO daily_sentiment (date, compound_score)
        VALUES (%s, %s)
        RETURNING *;
        """
        values = (data.posts[0].created, weighted_compound_score)
        cursor.execute(query, values)
        result = cursor.fetchone()
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to store sentiment score: {e}")
    finally:
        cursor.close()
        conn.close()
    
    return {"average_compound_score": round(weighted_compound_score, 5), "stored_record": result}


@router.post("/daily-sentiment/")
def create_daily_sentiment(sentiment: DailySentiment):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = """
        INSERT INTO daily_sentiment (date, positive_score, neutral_score, negative_score, compound_score)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *;
        """
        values = (sentiment.date, sentiment.positive_score, sentiment.neutral_score, sentiment.negative_score, sentiment.compound_score)
        cursor.execute(query, values)
        result = cursor.fetchone()
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to insert data: {e}")
    finally:
        cursor.close()
        conn.close()
    
    return result

@router.get("/daily-sentiment/", response_model=List[DailySentiment])
def get_daily_sentiments():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM daily_sentiment"
        cursor.execute(query)
        results = cursor.fetchall()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to retrieve data: {e}")
    finally:
        cursor.close()
        conn.close()

    return results


@router.get("/reddit-posts/")
def get_latest_reddit_posts(subreddit: str = Query(..., description="Subreddit name to fetch posts from")):
    subreddit_obj = reddit.subreddit(subreddit)  # Use the user-specified subreddit
    posts = []

    # Get current time in UNIX timestamp and calculate the time for 7 days ago
    current_time = int(datetime.time())  # Current time in UNIX timestamp
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
