
from openai import OpenAI
import json
import httpx
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY không được tìm thấy trong file .env. Vui lòng kiểm tra lại!")


# Proxy configuration
proxy_url = os.getenv('HTTP_PROXY') or os.getenv('HTTPS_PROXY')
# SSL verification - set to 'false' in .env if you have certificate issues
verify_ssl_str = os.getenv('VERIFY_SSL', 'false').lower()
verify_ssl = verify_ssl_str == 'true'
logger.info(f"SSL verification: {verify_ssl}")

# Set proxy environment variables if provided
if proxy_url:
    os.environ['HTTP_PROXY'] = proxy_url
    os.environ['HTTPS_PROXY'] = proxy_url

# Configure httpx client with proxy and SSL settings
http_client_kwargs = {
    'timeout': 30.0,
    'verify': verify_ssl
}

if proxy_url:
    http_client_kwargs['proxies'] = {
        'http://': proxy_url,
        'https://': proxy_url
    }

# Create httpx client
http_client = httpx.Client(**http_client_kwargs)
base_url= os.getenv('BASE_URL')
model =os.getenv('MODEL')
# Initialize OpenAI client with custom http_client
client = OpenAI(
    api_key=api_key,
    base_url=base_url,
    http_client=http_client,
    timeout=30.0
)

# 1. Define a list of callable tools for the model
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_horoscope",
            "description": "Get today's horoscope for an astrological sign.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sign": {
                        "type": "string",
                        "description": "An astrological sign like Taurus or Aquarius",
                    },
                },
                "required": ["sign"],
            },
        },
    },
]

def get_horoscope(sign):
    return f"{sign}: Next Tuesday you will befriend a baby otter."

# Create a running messages list we will add to over time
input_list = [
    {"role": "user", "content": "What is my horoscope? I am an Aquarius."}
]

# 2. Prompt the model with tools defined
response = client.chat.completions.create(
    model=model,
    messages=input_list,
    tools=tools,
)
# Save function call outputs for subsequent requests
message = response.choices[0].message
input_list.append(message)

def handle_tool_function(function_name, args, tool_call_id):
    result = None
    if function_name == "get_horoscope":
        # Separate parameter handling for get_horoscope
        sign = args.get("sign")
        if sign is not None:
            result_value = get_horoscope(sign)
            result = {"get_horoscope": result_value}
        else:
            result = {"error": "Missing required parameter 'sign' for get_horoscope."}
    # You can add more elif branches here for additional functions
    else:
        result = {"error": f"Function '{function_name}' not implemented."}

    input_list.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(result)
    })
# Check if the model wants to call a function
if message.tool_calls:
    for tool_call in message.tool_calls:
        
        # Example usage inside the tool_call loop:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        handle_tool_function(function_name, function_args, tool_call.id)


print("Final input:")
print(input_list)

response = client.chat.completions.create(
    model=model,
    messages=input_list,
    tools=tools,
)

# 5. The model should be able to give a response!
print("Final output:")
print(response.model_dump_json(indent=2))
print("\n" + response.choices[0].message.content)