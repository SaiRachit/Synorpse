import requests
import io
import os
import time
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLEAPIKEY")
CSE_ID = os.getenv("GOOGLE_CSE_ID")
SERP_API_KEY = os.getenv("SerpAPIKey")  # Fallback for when Google API reaches limit

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.google.com/',
    'Connection': 'keep-alive',
}

def search_serpapi_images(query, num=3):
    """Fallback image search using SerpAPI"""
    if not SERP_API_KEY:
        return []
    
    url = "https://serpapi.com/search"
    params = {
        "q": query,
        "api_key": SERP_API_KEY,
        "engine": "google_images",
        "num": num
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if "images_results" in data:
            return [item.get("original") for item in data["images_results"][:num] if item.get("original")]
        
        if "error" in data:
            pass
        
        return []
    except Exception as e:
        return []

def search_google_images(query, num=3):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": query,
        "cx": CSE_ID,
        "key": API_KEY,
        "searchType": "image",
        "num": num
    }

    try:
        response = requests.get(url, params=params)
        results = response.json()

        if "items" in results:
            return [item["link"] for item in results["items"]]
        
        # Check for errors and fallback to SerpAPI
        if "error" in results:
            error_code = results['error'].get('code', 0)
            error_message = results['error'].get('message', 'Unknown error')
            
            # Rate limit or quota exceeded - use SerpAPI fallback
            if error_code in [429, 403] or 'quota' in error_message.lower() or 'limit' in error_message.lower():
                return search_serpapi_images(query, num)
        
        return []
    
    except Exception as e:
        # Try SerpAPI as fallback
        return search_serpapi_images(query, num)

def is_valid_image_content(content):
    """Check if content starts with valid image file signatures"""
    if len(content) < 12:
        return False
    
    signatures = {
        b'\xFF\xD8\xFF': 'JPEG',
        b'\x89PNG\r\n\x1a\n': 'PNG',
        b'GIF87a': 'GIF',
        b'GIF89a': 'GIF',
        b'RIFF': 'WEBP',
        b'BM': 'BMP',
    }
    
    for sig, format_name in signatures.items():
        if content.startswith(sig):
            return True
    
    return False

def show_images(image_urls):
    temp_dir = "temp_images"
    os.makedirs(temp_dir, exist_ok=True)
    
    successful = 0
    for i, url in enumerate(image_urls, 1):
        try:
            
            response = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '').lower()
            if content_type and 'image' not in content_type:
                continue
            
            if len(response.content) < 100:
                continue
            
            if not is_valid_image_content(response.content):
                continue
            
            try:
                image = Image.open(io.BytesIO(response.content))
                image.verify()  
                
                image = Image.open(io.BytesIO(response.content))
                
            except Exception as e:
                continue
            
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                if image.mode in ('RGBA', 'LA'):
                    background.paste(image, mask=image.split()[-1])
                else:
                    background.paste(image)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            filepath = os.path.join(temp_dir, f"image_{i}.jpg")
            image.save(filepath, 'JPEG', quality=95)
            
            image.show()
            successful += 1
            
            time.sleep(0.5)
            
        except requests.exceptions.HTTPError as e:
            pass
        except requests.exceptions.RequestException as e:
            pass
        except Exception as e:
            pass
    
    return successful

if __name__ == "__main__":
    print("="*50)
    print("Google Image Search")
    print("Press Ctrl+C to exit")
    print("="*50)
    
    while True:
        try:
            query = input("\nEnter search query (or 'quit' to exit): ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if not query:
                print("Please enter a valid search query.")
                continue
            
            print(f"\n Searching for: {query}")
            images = search_google_images(query, num=3)

            if images:
                print(f"Found {len(images)} images. Downloading and displaying...\n")
                show_images(images)
            else:
                print("No images found.")
                
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break