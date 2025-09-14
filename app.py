from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import json
import os

app = Flask(__name__)
visited = set()
corrections_file = 'corrections.json'

# تحميل التصحيحات إن وجدت
if os.path.exists(corrections_file):
    with open(corrections_file, 'r', encoding='utf-8') as f:
        corrections = json.load(f)
else:
    corrections = {}

def is_valid_url(url):
    parsed = urlparse(url)
    return parsed.scheme in ['http', 'https']

def get_text_from_page(soup):
    return ' '.join(p.get_text().strip() for p in soup.find_all(['p', 'h1', 'h2']) if len(p.get_text()) > 30)

def summarize_text(text, max_sentences=3):
    sentences = text.split('.')
    summary = '. '.join(sentences[:max_sentences]) + '.' if len(sentences) > max_sentences else text
    return apply_corrections(summary)

def apply_corrections(text):
    for wrong, correct in corrections.items():
        text = text.replace(wrong, correct)
    return text

def save_correction(wrong, correct):
    corrections[wrong] = correct
    with open(corrections_file, 'w', encoding='utf-8') as f:
        json.dump(corrections, f, ensure_ascii=False, indent=2)

def crawl_and_summarize(start_url, depth=1, max_pages=5):
    results = []
    queue = [(start_url, 0)]

    while queue and len(results) < max_pages:
        current_url, current_depth = queue.pop(0)
        if current_url in visited or current_depth > depth:
            continue
        visited.add(current_url)

        try:
            response = requests.get(current_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.content, 'html.parser')
            text = get_text_from_page(soup)
            summary = summarize_text(text)

            results.append({
                'url': current_url,
                'summary': summary or 'لا يوجد محتوى قابل للتلخيص.',
            })

            for link in soup.find_all('a', href=True):
                full_url = urljoin(current_url, link['href'])
                if is_valid_url(full_url) and full_url not in visited:
                    queue.append((full_url, current_depth + 1))

        except Exception as e:
            results.append({
                'url': current_url,
                'summary': f'خطأ أثناء الزحف: {str(e)}',
            })

        time.sleep(1)

    return results

def search_from_engines(query, max_links=10):
    headers = {'User-Agent': 'Mozilla/5.0'}
    links = set()

    # Bing
    try:
        res = requests.get(f"https://www.bing.com/search?q={query}", headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            url = a['href']
            if is_valid_url(url):
                links.add(url)
                if len(links) >= max_links:
                    break
    except:
        pass

    # Yahoo
    try:
        res = requests.get(f"https://search.yahoo.com/search?p={query}", headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            url = a['href']
            if is_valid_url(url):
                links.add(url)
                if len(links) >= max_links:
                    break
    except:
        pass

    return list(links)

def crawl_multiple_links(urls, depth=1, max_pages=5):
    all_results = []
    for url in urls:
        result = crawl_and_summarize(url, depth=depth, max_pages=max_pages)
        all_results.extend(result)
    return all_results

def safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

@app.route('/', methods=['GET', 'POST'])
def index():
    results = []
    if request.method == 'POST':
        query = request.form.get('query')
        depth = safe_int(request.form.get('depth'), 1)
        max_pages = safe_int(request.form.get('max_pages'), 5)
        urls = search_from_engines(query)
        results = crawl_multiple_links(urls, depth=depth, max_pages=max_pages)
    return render_template('index.html', results=results)

@app.route('/correction', methods=['POST'])
def correction():
    wrong = request.form.get('wrong')
    correct = request.form.get('correct')
    if wrong and correct:
        save_correction(wrong, correct)
    return 'تم الحفظ بنجاح'

if __name__ == '__main__':
    app.run(debug=True)
