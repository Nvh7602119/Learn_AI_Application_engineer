
from openai import OpenAI
import json
import httpx
import os
import csv
from dotenv import load_dotenv
import logging
from datetime import datetime

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
base_url = os.getenv('BASE_URL')
model = os.getenv('MODEL')
# Initialize OpenAI client with custom http_client
client = OpenAI(
    api_key=api_key,
    base_url=base_url,
    http_client=http_client,
    timeout=30.0
)

# CSV file path
MOVIES_CSV = 'movies.csv'

def get_movies(movie_name=None, show_date=None):
    """
    Lấy danh sách phim đang chiếu từ file CSV.
    
    Args:
        movie_name (str, optional): Tên phim để lọc (không phân biệt hoa thường)
        show_date (str, optional): Ngày chiếu để lọc (format: YYYY-MM-DD)
    
    Returns:
        list: Danh sách các suất chiếu phim
    """
    movies = []
    
    try:
        with open(MOVIES_CSV, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Lọc theo tên phim nếu được cung cấp
                if movie_name:
                    if movie_name.lower() not in row['Tên phim'].lower():
                        continue
                
                # Lọc theo ngày chiếu nếu được cung cấp
                if show_date:
                    if row['Ngày chiếu'] != show_date:
                        continue
                
                movies.append({
                    'Tên phim': row['Tên phim'],
                    'Ngày chiếu': row['Ngày chiếu'],
                    'Giờ chiếu': row['Giờ chiếu'],
                    'Rạp': row['Rạp'],
                    'Số ghế trống': int(row['Số ghế trống']),
                    'Giá vé': int(row['Giá vé'])
                })
    except FileNotFoundError:
        return {"error": f"Không tìm thấy file {MOVIES_CSV}"}
    except Exception as e:
        return {"error": f"Lỗi khi đọc file CSV: {str(e)}"}
    
    return movies

def book_ticket(movie_name, show_date, show_time, number_of_tickets=1, customer_name=None):
    """
    Đặt vé xem phim.
    
    Args:
        movie_name (str): Tên phim
        show_date (str): Ngày chiếu (format: YYYY-MM-DD)
        show_time (str): Giờ chiếu (format: HH:MM)
        number_of_tickets (int): Số lượng vé (mặc định: 1)
        customer_name (str, optional): Tên khách hàng
    
    Returns:
        dict: Thông tin đặt vé thành công hoặc lỗi
    """
    # Tìm suất chiếu phù hợp
    movies = get_movies(movie_name=movie_name, show_date=show_date)
    
    if isinstance(movies, dict) and 'error' in movies:
        return movies
    
    # Tìm suất chiếu với giờ chiếu chính xác
    matching_show = None
    for movie in movies:
        if movie['Giờ chiếu'] == show_time:
            matching_show = movie
            break
    
    if not matching_show:
        return {
            "error": f"Không tìm thấy suất chiếu cho phim '{movie_name}' vào ngày {show_date} lúc {show_time}"
        }
    
    # Kiểm tra số ghế trống
    if matching_show['Số ghế trống'] < number_of_tickets:
        return {
            "error": f"Không đủ ghế trống. Chỉ còn {matching_show['Số ghế trống']} ghế."
        }
    
    # Tính tổng tiền
    total_price = matching_show['Giá vé'] * number_of_tickets
    
    # Tạo mã đặt vé (đơn giản)
    booking_id = f"BK{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    result = {
        "success": True,
        "booking_id": booking_id,
        "movie_name": movie_name,
        "show_date": show_date,
        "show_time": show_time,
        "theater": matching_show['Rạp'],
        "number_of_tickets": number_of_tickets,
        "price_per_ticket": matching_show['Giá vé'],
        "total_price": total_price,
        "customer_name": customer_name or "Khách hàng",
        "message": f"Đặt vé thành công! Mã đặt vé: {booking_id}"
    }
    
    return result
def apply_discount(total_amount):
    """
    Tính tổng số tiền sau khi áp dụng giảm giá cho tất cả hóa đơn.
    """
    if total_amount > 1000000:
        return total_amount * 0.9
    elif total_amount > 500000:
        return total_amount * 0.95
    return total_amount
# 1. Define a list of callable tools for the model
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_movies",
            "description": "Lấy danh sách phim đang chiếu và các suất chiếu từ file CSV. Có thể lọc theo tên phim và/hoặc ngày chiếu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "movie_name": {
                        "type": "string",
                        "description": "Tên phim để tìm kiếm (không bắt buộc, nếu không có sẽ trả về tất cả phim)",
                    },
                    "show_date": {
                        "type": "string",
                        "description": "Ngày chiếu để lọc (format: YYYY-MM-DD, ví dụ: 2024-12-20). Không bắt buộc.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_ticket",
            "description": "Đặt vé xem phim sau khi đã chọn được phim, ngày và giờ chiếu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "movie_name": {
                        "type": "string",
                        "description": "Tên phim muốn đặt vé",
                    },
                    "show_date": {
                        "type": "string",
                        "description": "Ngày chiếu (format: YYYY-MM-DD, ví dụ: 2024-12-20)",
                    },
                    "show_time": {
                        "type": "string",
                        "description": "Giờ chiếu (format: HH:MM, ví dụ: 14:00)",
                    },
                    "number_of_tickets": {
                        "type": "integer",
                        "description": "Số lượng vé muốn đặt (mặc định: 1)",
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Tên khách hàng (không bắt buộc)",
                    },
                },
                "required": ["movie_name", "show_date", "show_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_discount",
            "description": "Tự đông tính tổng số tiền sau khi áp dụng giảm giá cho tất cả hóa đơn.",
            "parameters": {
                "type": "object",
                "properties": {
                    "total_amount": {
                        "type": "number",
                        "description": "Tổng số tiền của tất cả hóa đơn (đơn vị VND)."
                    }
                },
                "required": ["total_amount"],
            },
        },
    },

]


# Create a running messages list we will add to over time
input_list = [
    {"role": "system", "content": f"Bạn là một nhân viên bán vé xem phim. Bạn cần tính toán tổng số tiền sau khi áp dụng giảm giá cho tất cả hóa đơn. "},
    {"role": "user", "content": "Tôi muốn xem phim Dune vào ngày 29 tháng 11 Năm 2025. Nếu có suất lúc 14:00 thì đặt vé cho tôi 2 vé."},
    {"role": "user", "content": "Tôi muốn xem phim Oppenheimer vào ngày 30 tháng 11 Năm 2025. Nếu có suất lúc 15:00 thì đặt vé cho tôi 3 vé."}
   
]

def handle_tool_function(function_name, args, tool_call_id):
    result = None
    if function_name == "get_movies":
        movie_name = args.get("movie_name")
        show_date = args.get("show_date")
        result_value = get_movies(movie_name=movie_name, show_date=show_date)
        result = {"get_movies": result_value}
    elif function_name == "book_ticket":
        movie_name = args.get("movie_name")
        show_date = args.get("show_date")
        show_time = args.get("show_time")
        number_of_tickets = args.get("number_of_tickets", 1)
        customer_name = args.get("customer_name")
        
        if not movie_name or not show_date or not show_time:
            result = {"error": "Thiếu thông tin bắt buộc: movie_name, show_date, show_time"}
        else:
            result_value = book_ticket(
                movie_name=movie_name,
                show_date=show_date,
                show_time=show_time,
                number_of_tickets=number_of_tickets,
                customer_name=customer_name
            )
            result = {"book_ticket": result_value}
    elif function_name == "apply_discount":
        total_amount = args.get("total_amount")
        result_value = apply_discount(total_amount=total_amount)
        result = {"apply_discount": result_value}
    else:
        result = {"error": f"Function '{function_name}' not implemented."}

    input_list.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(result, ensure_ascii=False)
    })

# Main conversation loop
max_iterations = 4
iteration = 0

while iteration < max_iterations:
    iteration += 1
    print(f"\n=== Lần lặp {iteration} ===")
    
    # 2. Prompt the model with tools defined
    response = client.chat.completions.create(
        model=model,
        messages=input_list,
        tools=tools,
    )
    
    # Save function call outputs for subsequent requests
    message = response.choices[0].message
    input_list.append(message)
    
    # Check if the model wants to call a function
    if message.tool_calls:
        for tool_call in message.tool_calls:
            print(f"Tool call: {tool_call.function.name}")
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            handle_tool_function(function_name, function_args, tool_call.id)
    else:
        # No more tool calls, the model has given a final response
        print("\n=== Kết quả cuối cùng ===")
        print(response.choices[0].message.content)
        break
response = client.chat.completions.create(
        model=model,
        messages=input_list,
        tools=tools,
    )
print(response.choices[0].message.content)
# print("\n=== Lịch sử hội thoại ===")
# for i, msg in enumerate(input_list):
#     print(f"\nMessage {i+1}:")
#     print(json.dumps(msg, ensure_ascii=False, indent=2, default=str))

