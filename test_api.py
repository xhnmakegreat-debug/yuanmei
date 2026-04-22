from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, timeout=60)
r = client.chat.completions.create(
    model=DEEPSEEK_MODEL,
    messages=[{"role": "user", "content": "回复数字1"}],
    max_tokens=10,
)
print("OK:", r.choices[0].message.content)
