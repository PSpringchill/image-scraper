import os
import time
import requests
from PIL import Image
from tqdm import tqdm
from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import numpy as np
from collections import Counter
from urllib3.util.retry import Retry
import json
from urllib.parse import urljoin
import traceback
import re
import platform
import hashlib
import socket
import urllib.parse

class ImageScraper:
    def __init__(self, output_dir="dataset", target_size=None):
        """Initialize the scraper with output directory and optional target size"""
        self.base_url = "https://www5.javmost.com/pornstar/all/"
        self.output_dir = output_dir
        self.target_size = target_size
        self.categories = set()
        
        # Configure retry strategy with longer delays
        retry_strategy = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        # Create session with retry strategy
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # Enhanced browser-like headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'Referer': 'https://www.google.com/'
        }
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize metadata storage
        self.metadata = []
        
        print(f"Initialized scraper with output directory: {output_dir}")
        if target_size:
            print(f"Target image size: {target_size}")

    def clean_category_name(self, text):
        """Clean and normalize category name from alt text"""
        if not text:
            return "uncategorized"
        
        # Convert to lowercase and remove special characters
        text = text.lower()
        text = ''.join(c for c in text if c.isalnum() or c.isspace())
        
        # Split by spaces and take first few meaningful words
        words = text.split()
        if len(words) > 3:
            words = words[:3]  # Take first 3 words for category name
        
        # Join words with underscores
        category = '_'.join(words)
        
        # Handle empty or invalid cases
        if not category or len(category) < 2:
            return "uncategorized"
        
        return category

    def analyze_page_structure(self, soup):
        """Analyze the page structure and return relevant selectors"""
        try:
            print("\nAnalyzing page structure...")
            
            # Store all found patterns
            patterns = {
                'image_containers': set(),
                'image_classes': set(),
                'title_classes': set()
            }
            
            # Find all elements with class attributes
            elements_with_class = soup.find_all(class_=True)
            print(f"\nFound {len(elements_with_class)} elements with classes")
            
            # Analyze class patterns
            for element in elements_with_class:
                classes = element.get('class', [])
                
                # Look for potential image-related classes
                class_str = ' '.join(classes).lower()
                if any(term in class_str for term in ['img', 'image', 'photo', 'thumb', 'avatar']):
                    patterns['image_classes'].update(classes)
                
                # Look for potential title/name classes
                if any(term in class_str for term in ['title', 'name', 'heading', 'caption']):
                    patterns['title_classes'].update(classes)
                
                # Look for potential container classes
                if element.find('img'):
                    patterns['image_containers'].update(classes)
            
            # Print found patterns
            print("\nFound patterns:")
            for pattern_type, pattern_set in patterns.items():
                if pattern_set:
                    print(f"\n{pattern_type}:")
                    for pattern in sorted(pattern_set):
                        print(f"- {pattern}")
            
            return patterns
            
        except Exception as e:
            print(f"Error analyzing page structure: {str(e)}")
            return None

    def extract_image_info(self, element):
        """Extract image information from an element and its context"""
        info = {
            'url': None,
            'alt': None,
            'title': None,
            'labels': []
        }
        
        # Find image
        img = element.find('img') if element.name != 'img' else element
        if not img:
            return None
            
        # Get image URL
        info['url'] = img.get('data-src') or img.get('src')
        if not info['url']:
            return None
            
        # Clean URL
        if info['url'].startswith('//'):
            info['url'] = 'https:' + info['url']
        elif not info['url'].startswith(('http://', 'https://')):
            info['url'] = 'https://' + info['url'].lstrip('/')
        
        # Get text information
        info['alt'] = img.get('alt', '')
        info['title'] = img.get('title', '')
        
        # Look for labels in surrounding context
        parent = img.parent
        for _ in range(3):  # Check up to 3 levels up
            if not parent:
                break
                
            # Check text content
            text = parent.get_text(strip=True)
            if text and text not in info['labels']:
                info['labels'].append(text)
            
            # Check attributes
            for attr in ['title', 'aria-label', 'data-title']:
                if parent.get(attr) and parent.get(attr) not in info['labels']:
                    info['labels'].append(parent.get(attr))
            
            # Check header or link elements
            for elem in parent.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'a']):
                text = elem.get_text(strip=True)
                if text and text not in info['labels']:
                    info['labels'].append(text)
            
            parent = parent.parent
        
        return info

    def scrape_with_bs4(self):
        """Scrape images using BeautifulSoup"""
        try:
            print("Scraping images with BeautifulSoup...")
            print(f"Accessing URL: {self.base_url}")
            
            response = self.session.get(
                self.base_url,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            print(f"Response status: {response.status_code}")
            print(f"Content type: {response.headers.get('content-type', 'unknown')}")
            
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Analyze page structure
            patterns = self.analyze_page_structure(soup)
            if not patterns:
                print("Could not analyze page structure")
                return {}
            
            # Find images using discovered patterns
            images = []
            
            # Method 1: Find images directly
            for img in soup.find_all('img'):
                if img.get('src'):
                    images.append(img)
            
            # Method 2: Find images in containers
            for container_class in patterns['image_containers']:
                containers = soup.find_all(class_=container_class)
                for container in containers:
                    img = container.find('img')
                    if img and img.get('src'):
                        images.append(img)
            
            # Method 3: Find images by image classes
            for img_class in patterns['image_classes']:
                imgs = soup.find_all('img', class_=img_class)
                for img in imgs:
                    if img.get('src'):
                        images.append(img)
            
            print(f"\nFound {len(images)} total images")
            
            # Process images
            categorized_images = {}
            processed_urls = set()
            
            for img in images:
                try:
                    # Get image URL
                    img_src = img.get('data-src') or img.get('src')
                    if not img_src or img_src in processed_urls:
                        continue
                    
                    # Clean up URL
                    if img_src.startswith('//'):
                        img_src = 'https:' + img_src
                    elif not img_src.startswith('http'):
                        img_src = urljoin(self.base_url, img_src)
                    
                    # Skip small images and icons
                    if any(x in img_src.lower() for x in ['icon', 'logo', 'banner', '.svg', '.ico']):
                        continue
                    
                    processed_urls.add(img_src)
                    
                    # Try to get title/name
                    category = None
                    
                    # Method 1: Check img attributes
                    category = img.get('alt') or img.get('title')
                    
                    # Method 2: Check parent elements for title classes
                    if not category:
                        parent = img.parent
                        for _ in range(3):  # Look up to 3 levels
                            if not parent or not isinstance(parent, Tag):
                                break
                            
                            # Check for elements with title classes
                            for class_name in patterns['title_classes']:
                                title_elem = parent.find(class_=class_name)
                                if title_elem:
                                    category = title_elem.get_text(strip=True)
                                    break
                        
                            if category:
                                break
                            parent = parent.parent
                    
                    # Fallback to filename
                    if not category:
                        category = os.path.splitext(os.path.basename(img_src))[0]
                    
                    # Clean category name
                    category = self.clean_category_name(category)
                    if not category or len(category) < 3:
                        category = 'uncategorized'
                    
                    # Create category directory
                    category_dir = os.path.join(self.output_dir, category)
                    os.makedirs(category_dir, exist_ok=True)
                    
                    # Add to categories set
                    self.categories.add(category)
                    
                    # Store image info
                    if category not in categorized_images:
                        categorized_images[category] = []
                    
                    image_data = {
                        'url': img_src,
                        'alt': img.get('alt', ''),
                        'title': img.get('title', ''),
                        'category': category
                    }
                    
                    categorized_images[category].append(image_data)
                    print(f"Found image: {img_src} -> {category}")
                    
                except Exception as e:
                    print(f"Error processing image: {str(e)}")
                    continue
            
            # Print summary
            if categorized_images:
                print("\nFound categories:")
                for category in sorted(self.categories):
                    count = len(categorized_images.get(category, []))
                    print(f"- {category}: {count} images")
            else:
                print("No images found")
            
            return categorized_images
            
        except Exception as e:
            print(f"Error in scraping: {str(e)}")
            traceback.print_exc()
            return {}

    def scrape_with_selenium(self):
        """Scrape images using Selenium for dynamic content"""
        try:
            print("\nSetting up Selenium...")
            options = webdriver.ChromeOptions()
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-notifications')
            
            # Add more browser-like behavior
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Add custom headers
            for key, value in self.headers.items():
                options.add_argument(f'--header={key}:{value}')
            
            # Set up ChromeDriver
            service = Service()
            driver = webdriver.Chrome(service=service, options=options)
            
            # Set window size
            driver.set_window_size(1920, 1080)
            
            # Set cookies and local storage to appear more like a real browser
            driver.execute_cdp_cmd('Network.enable', {})
            driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {'headers': self.headers})
            
            print(f"\nAccessing URL: {self.base_url}")
            driver.get(self.base_url)
            
            # Wait for content to load
            time.sleep(5)
            
            # Print page info for debugging
            print(f"Page Title: {driver.title}")
            print(f"Current URL: {driver.current_url}")
            
            # Implement infinite scrolling
            print("\nStarting infinite scroll...")
            last_height = driver.execute_script("return document.body.scrollHeight")
            scroll_count = 0
            max_scrolls = 20  # Adjust this value to control how many times to scroll
            
            while scroll_count < max_scrolls:
                # Scroll down to bottom
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # Wait for new content to load
                time.sleep(2)
                
                # Calculate new scroll height
                new_height = driver.execute_script("return document.body.scrollHeight")
                
                # Break if no new content loaded (height didn't change)
                if new_height == last_height:
                    print("No more content to load")
                    break
                    
                last_height = new_height
                scroll_count += 1
                print(f"Scrolled {scroll_count} times, loading more content...")
            
            # Save page source for analysis
            with open("page_source.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("\nSaved page source to page_source.html for analysis")
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Find all elements with class attributes
            elements_with_class = soup.find_all(class_=True)
            print(f"\nFound {len(elements_with_class)} elements with classes")
            
            # Find all images using multiple methods
            images = []
            
            # Method 1: Direct img tags
            print("\nLooking for direct img tags...")
            for img in soup.find_all('img'):
                if img.get('src'):
                    print(f"Found image: {img.get('src')}")
                    images.append(img)
            
            # Method 2: Look for images in article content
            print("\nLooking for images in article content...")
            article_content = soup.find('div', class_='box-body')
            if article_content:
                for img in article_content.find_all('img'):
                    if img.get('src'):
                        print(f"Found article image: {img.get('src')}")
                        images.append(img)
            
            # Method 3: Look for lazy-loaded images
            print("\nLooking for lazy-loaded images...")
            for img in soup.find_all('img', class_='lazy'):
                src = img.get('data-src') or img.get('data-lazy-src') or img.get('src')
                if src:
                    print(f"Found lazy image: {src}")
                    images.append(img)
            
            # Method 4: Background images
            print("\nLooking for background images...")
            for elem in soup.find_all(style=True):
                style = elem.get('style', '')
                if 'background-image' in style:
                    url_match = re.search(r'url\(["\']?([^"\']+)["\']?\)', style)
                    if url_match:
                        url = url_match.group(1)
                        print(f"Found background image: {url}")
                        img_tag = soup.new_tag('img', src=url)
                        images.append(img_tag)
            
            print(f"\nFound {len(images)} total images")
            
            # Process images
            categorized_images = {}
            processed_urls = set()
            
            for img in images:
                try:
                    # Get image URL
                    img_src = img.get('data-src') or img.get('data-lazy-src') or img.get('src')
                    if not img_src or img_src in processed_urls:
                        continue
                    
                    # Clean up URL
                    if img_src.startswith('//'):
                        img_src = 'https:' + img_src
                    elif not img_src.startswith('http'):
                        img_src = urljoin(self.base_url, img_src)
                    
                    # Skip small images and icons
                    if any(x in img_src.lower() for x in ['icon', 'logo', 'banner', '.svg', '.ico']):
                        continue
                    
                    processed_urls.add(img_src)
                    
                    # Get category from context
                    category = None
                    parent = img.parent if isinstance(img, Tag) else None
                    
                    # Try to find category in parent elements
                    for _ in range(3):
                        if not parent or not isinstance(parent, Tag):
                            break
                        
                        # Look for text in headers and links
                        for elem in parent.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'a', 'p']):
                            text = elem.get_text(strip=True)
                            if text and len(text) > 2:
                                category = text
                                break
                        
                        if category:
                            break
                        parent = parent.parent
                    
                    # Fallback to image attributes
                    if not category:
                        category = img.get('alt') or img.get('title')
                    
                    # Clean category name
                    if category:
                        category = self.clean_category_name(category)
                    
                    if not category or len(category) < 3:
                        category = 'uncategorized'
                    
                    # Create category directory
                    category_dir = os.path.join(self.output_dir, category)
                    os.makedirs(category_dir, exist_ok=True)
                    
                    # Add to categories set
                    self.categories.add(category)
                    
                    # Store image info
                    if category not in categorized_images:
                        categorized_images[category] = []
                    
                    image_data = {
                        'url': img_src,
                        'alt': img.get('alt', ''),
                        'title': img.get('title', ''),
                        'category': category
                    }
                    
                    categorized_images[category].append(image_data)
                    print(f"Found image: {img_src} -> {category}")
                    
                except Exception as e:
                    print(f"Error processing image: {str(e)}")
                    continue
            
            # Close the browser
            driver.quit()
            
            # Print summary
            if categorized_images:
                print("\nFound categories:")
                for category in sorted(self.categories):
                    count = len(categorized_images.get(category, []))
                    print(f"- {category}: {count} images")
            else:
                print("No images found")
            
            return categorized_images
            
        except Exception as e:
            print(f"Error in Selenium scraping: {str(e)}")
            traceback.print_exc()
            if 'driver' in locals():
                driver.quit()
            return {}

    def process_image(self, image_path):
        """
        Process the downloaded image
        - Optionally resize to target size if specified
        - Convert to RGB if needed
        - Return the processed image
        """
        try:
            img = Image.open(image_path)
            
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Only resize if target_size is specified
            if self.target_size:
                img = img.resize(self.target_size, Image.Resampling.LANCZOS)
            
            return img
                
        except Exception as e:
            print(f"Error processing image {image_path}: {str(e)}")
            return None

    def scrape(self):
        """Main scraping function"""
        print("Starting image scraping...")
        
        try:
            # Try Selenium first
            print("Attempting to scrape with Selenium...")
            images = self.scrape_with_selenium()
            
            if not images:
                # Fall back to BeautifulSoup if Selenium fails
                print("\nFalling back to BeautifulSoup...")
                images = self.scrape_with_bs4()
            
            if not images:
                print("No images found. Exiting...")
                return
            
            # Download images
            self.download_images(images)
            
        except Exception as e:
            print(f"Error during scraping: {str(e)}")
            traceback.print_exc()

    def download_images(self, categorized_images):
        """Download and process images by category"""
        if not categorized_images:
            return
        
        total_images = sum(len(images) for images in categorized_images.values())
        print(f"\nDownloading {total_images} images...")
        
        # Track success and failure counts
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        for category, images in categorized_images.items():
            print(f"\nProcessing category: {category}")
            category_dir = os.path.join(self.output_dir, category)
            os.makedirs(category_dir, exist_ok=True)
            
            for image_data in tqdm(images, desc=f"Downloading {category} images"):
                try:
                    url = image_data['url']
                    
                    # Skip if URL is invalid
                    if not url or not url.startswith('http'):
                        print(f"Skipping invalid URL: {url}")
                        skipped_count += 1
                        continue
                    
                    # Generate filename from URL
                    filename = os.path.basename(url).split('?')[0]
                    if not filename:
                        filename = hashlib.md5(url.encode()).hexdigest()[:10] + '.jpg'
                    
                    # Ensure filename has an extension
                    if not os.path.splitext(filename)[1]:
                        filename += '.jpg'
                    
                    # Create full path
                    filepath = os.path.join(category_dir, filename)
                    
                    # Skip if file already exists
                    if os.path.exists(filepath):
                        print(f"Skipping existing file: {filepath}")
                        skipped_count += 1
                        continue
                    
                    # Download image with timeout and retries
                    try:
                        # Try to resolve the hostname first
                        parsed_url = urllib.parse.urlparse(url)
                        try:
                            socket.gethostbyname(parsed_url.hostname)
                        except socket.gaierror:
                            print(f"Could not resolve hostname for: {url}")
                            failed_count += 1
                            continue
                        
                        response = self.session.get(
                            url,
                            headers=self.headers,
                            timeout=30,
                            stream=True,
                            verify=False  # Skip SSL verification
                        )
                        response.raise_for_status()
                        
                        # Check if it's actually an image
                        content_type = response.headers.get('content-type', '')
                        if not content_type.startswith('image/'):
                            print(f"Skipping non-image content: {url} ({content_type})")
                            skipped_count += 1
                            continue
                        
                        # Save image
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        # Process image if needed
                        if self.target_size:
                            try:
                                img = Image.open(filepath)
                                img = img.resize(self.target_size, Image.Resampling.LANCZOS)
                                img.save(filepath)
                            except Exception as e:
                                print(f"Error processing image {filepath}: {str(e)}")
                                if os.path.exists(filepath):
                                    os.remove(filepath)
                                failed_count += 1
                                continue
                        
                        # Store metadata
                        self.metadata.append({
                            'url': url,
                            'category': category,
                            'filename': filename,
                            'title': image_data.get('title', ''),
                            'alt': image_data.get('alt', '')
                        })
                        
                        success_count += 1
                        
                    except requests.exceptions.RequestException as e:
                        print(f"Error downloading {url}: {str(e)}")
                        failed_count += 1
                        continue
                    
                except Exception as e:
                    print(f"Error processing {url}: {str(e)}")
                    failed_count += 1
                    continue
        
        # Print summary
        print(f"\nDownload Summary:")
        print(f"Successful: {success_count}")
        print(f"Failed: {failed_count}")
        print(f"Skipped: {skipped_count}")
        print(f"Total Processed: {success_count + failed_count + skipped_count}")
        
        # Save metadata
        if self.metadata:
            metadata_file = os.path.join(self.output_dir, 'metadata.json')
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
            print(f"\nSaved metadata to {metadata_file}")

def main():
    """Main function to run the scraper"""
    try:
        # Create scraper instance
        scraper = ImageScraper()
        
        # Scrape images and categories
        scraper.scrape()
        
        # Save metadata
        if scraper.metadata:
            metadata_file = os.path.join(scraper.output_dir, 'metadata.json')
            with open(metadata_file, 'w') as f:
                json.dump(scraper.metadata, f, indent=2)
            print(f"\nMetadata saved to {metadata_file}")
        
        print("\nScraping completed successfully!")
        
    except Exception as e:
        print(f"Error in main: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
