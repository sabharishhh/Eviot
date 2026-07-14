from openai import OpenAI

client = OpenAI(api_key="YOUR_KEY")

print(client.models.list())