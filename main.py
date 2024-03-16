import praw
import os
from dotenv import load_dotenv
import requests
import json
import http.client
from datetime import datetime, timezone, timedelta
import pymysql
import sqlite3


# Load environment variables from .env file
load_dotenv()

# Reddit API
reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
reddit_user_agent = os.getenv("REDDIT_USER_AGENT")

# MySQL database
mysql_host = os.getenv("MYSQL_HOST")
mysql_user = os.getenv("MYSQL_USER")
mysql_password = os.getenv("MYSQL_PASSWORD")
mysql_db = os.getenv("MYSQL_DB")

# SQLite database
sqlite_db_path = 'processed_posts.db'

# OpenAI API
openai_api_key = os.getenv("OPENAI_API_KEY")

custom_prompt = "You are RedditAIAnalystan ,an AI assistant dedicated to analysing and evaluating AI-related content on Reddit. Your task is to review this piece of content, analyse and evaluate the quality, information value and importance of this content in terms of AI Daily writing. Give a score from 0-10, with 10 being the most important. For high-quality content with a score of 6 or above, extract the core points and key information, and organise them in an easy-to-read format. Use a concise and clear paragraph of Chinese to summarize the content and avoid lengthy and redundant information.Use json of Chinese return format, including fields：score、content_Summary.Example：\{ \"score\": "",  \"content_Summary\": \"Chinese content Summary\"\}"

def init_db(db_path='processed_posts.db'):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS processed_posts (id TEXT PRIMARY KEY)')
    conn.commit()
    conn.close()

def is_post_processed(post_id):
    conn = sqlite3.connect(sqlite_db_path)
    c = conn.cursor()
    c.execute('SELECT id FROM processed_posts WHERE id=?', (post_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_post_as_processed(post_id):
    conn = sqlite3.connect(sqlite_db_path)
    c = conn.cursor()
    c.execute('INSERT INTO processed_posts (id) VALUES (?)', (post_id,))
    conn.commit()
    conn.close()

# Function to get Reddit content
def get_reddit_content(subreddit_name='LocalLlama', limit=10):
    reddit = praw.Reddit(client_id=reddit_client_id,
                         client_secret=reddit_client_secret,
                         user_agent=reddit_user_agent)
    
    subreddit = reddit.subreddit(subreddit_name)
    posts = []

    for post in subreddit.new(limit=limit):
        if is_post_processed(post.id):
            continue  # 已经处理过的帖子，跳过

        # 过滤掉帖子的 flair 为 'Question | Help'
        if post.link_flair_text in ['Question | Help', 'Discussion', 'Other', 'Funny']:
            continue

        created_utc = datetime.utcfromtimestamp(post.created_utc)
        created_utc += timedelta(hours=8)  # 转换为中国+8时区

        # 将标题和内容组合为一个字段
        combined_content = f"{post.title}\n\n{post.selftext}"

        posts.append({
            'id': post.id,
            'title': post.title,
            'content': post.selftext,
            'combined_content': combined_content,
            'created_utc': created_utc.strftime('%Y-%m-%d %H:%M:%S'),  # 格式化时间
            'author': post.author.name if post.author else None,
            'url': f"https://www.reddit.com{post.permalink}",
            'link_flair_text': post.link_flair_text if post.link_flair_text else None
        })

    return posts


def write_to_mysql(processed_posts):
    connection = pymysql.connect(host=mysql_host,
                                 user=mysql_user,
                                 password=mysql_password,
                                 database=mysql_db,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
    
    try:
        with connection.cursor() as cursor:
            for post in processed_posts:
                sql = """
                    INSERT INTO rss_data 
                    (processed_content, timestamp, poster, rating, original_content_link, selected_for_ai_daily	) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    post['processed_content'],
                    post['created_utc'],
                    post['author'],
                    post.get('rating', None),  # Assuming 'rating' is a key in processed_post
                    post['url'],
                    post['selected_for_ai_daily'],
                ))
        
        connection.commit()
    finally:
        connection.close()

# Function to process content with AI
def process_content_with_ai(custom_prompt, content):
   conn = http.client.HTTPSConnection("www.dwyu.top")
   payload = json.dumps({
      "model": "gpt-3.5-turbo-1106",
      "messages": [
         {
            "role": "user",
            "content": content
         },
         {
            "role": "system",
            "content": custom_prompt
         }
      ]
   })
   headers = {
      'Authorization': f'Bearer {openai_api_key}',
      'Accept': 'application/json',
      'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
      'Content-Type': 'application/json'
   }
   conn.request("POST", "/v1/chat/completions", payload, headers)
   res = conn.getresponse()
   data = res.read()
   parsed_data = json.loads(data)
   content_value = parsed_data['choices'][0]['message']['content']
   return content_value

# Main function
def main():
    init_db()  # 确保数据库初始化
    # Get Reddit content
    reddit_posts = get_reddit_content()
    
    # Process content with AI and write to MySQL for each post
    for post in reddit_posts:
        try:
            processed_content_result1 = process_content_with_ai(custom_prompt, post['combined_content'])
            processed_content_result = json.loads(processed_content_result1)
            mark_post_as_processed(post['id'])
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from process_content_with_ai: {e}")
            print(f"Original content: {processed_content_result1}")
            continue

        processed_content = processed_content_result.get('content_Summary', '')
        rating = processed_content_result.get('score', None)

        processed_post = {
            'processed_content': processed_content,
            'created_utc': post['created_utc'],
            'author': post['author'],
            'rating': rating,
            'url': post['url'],
            'selected_for_ai_daily': '0'
        }

        # Write to MySQL for each post
        write_to_mysql([processed_post])


if __name__ == "__main__":
    main()
