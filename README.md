# Image Scraper for AI Training

A robust image scraping tool that can download and preprocess images for AI training. Supports both BeautifulSoup and Selenium approaches for maximum compatibility with different websites.

## Ethical Guidelines

1. **Always check website terms of service** before scraping
2. **Respect robots.txt** and implement rate limiting
3. **Verify image licenses** before using in your project
4. **Attribute sources** properly in your documentation
5. **Consider bandwidth impact** on source websites

## Recommended Image Sources

1. **Wikimedia Commons** - Millions of freely usable media files
2. **Flickr Creative Commons** - Photos with various CC licenses
3. **Pexels** - Free stock photos with clear licensing
4. **Unsplash** - Free high-resolution photos (API available)
5. **OpenImages Dataset** - Large-scale dataset for AI training

## Features

- Dual scraping methods (BeautifulSoup and Selenium)
- Automatic image preprocessing
- Progress tracking with tqdm
- Metadata storage
- Error handling and logging
- Support for various image formats
- Configurable image resizing

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Choose a legitimate source website that allows scraping
2. Update the `base_url` in `scraper.py`:
```python
base_url = "https://commons.wikimedia.org/wiki/Featured_pictures"  # Example using Wikimedia Commons
```

3. Run the scraper:
```bash
python scraper.py
```

## Configuration

You can customize the scraper by modifying these parameters:

```python
scraper = ImageScraper(
    base_url="https://example.com",
    output_dir="custom_output",
    target_size=(224, 224)  # Change target image size
)
```

## Alternative Data Sources

Instead of web scraping, consider these options:

1. **Public Datasets**:
   - ImageNet (academic/research use)
   - COCO dataset
   - Open Images Dataset
   - Google's Landmarks Dataset

2. **APIs**:
   - Unsplash API
   - Pexels API
   - Flickr API

3. **Data Generation**:
   - Synthetic data generation
   - Data augmentation
   - Self-collected datasets

## Legal and Ethical Considerations

- Always check and respect website terms of service
- Implement rate limiting to avoid server strain
- Keep records of image sources and licenses
- Consider using official APIs when available
- Respect copyright and attribution requirements
- Be prepared to remove content if requested by copyright holders
