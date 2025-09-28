#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv('.env')
api_key = os.getenv('OPENAI_API_KEY')

print(f'Testing API key: {api_key[:25]}...')

try:
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model='gpt-3.5-turbo',
        messages=[{'role': 'user', 'content': 'Hello! Just say SUCCESS if you receive this.'}],
        max_tokens=50
    )
    print('✅ API KEY WORKS!')
    print('Response:', response.choices[0].message.content)
    print('Tokens used:', response.usage.total_tokens)
except Exception as e:
    print('❌ API Error:', str(e)) 