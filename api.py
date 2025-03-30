from flask import Flask, jsonify, request, send_file
from bs4 import BeautifulSoup
import requests
import re
import json
import os

app = Flask(__name__)

# Global session for requests
session = requests.Session()
session.headers.update({
    'authority': 'animepahe.ru',
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'en-US,en;q=0.9',
    'cookie': '__ddg2_=;',
    'dnt': '1',
    'sec-ch-ua': '"Not A(Brand";v="99", "Microsoft Edge";v="121", "Chromium";v="121"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'x-requested-with': 'XMLHttpRequest',
    'referer': 'https://animepahe.ru',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
})





s = requests.session()

def step_2(s, seperator, base=10):
    mapped_range = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/"
    numbers = mapped_range[0:base]
    max_iter = 0
    for index, value in enumerate(s[::-1]):
        max_iter += int(value if value.isdigit() else 0) * (seperator**index)
    mid = ''
    while max_iter > 0:
        mid = numbers[int(max_iter % base)] + mid
        max_iter = (max_iter - (max_iter % base)) / base
    return mid or '0'

def step_1(data, key, load, seperator):
    payload = ""
    i = 0
    seperator = int(seperator)
    load = int(load)
    while i < len(data):
        s = ""
        while data[i] != key[seperator]:
            s += data[i]
            i += 1
        for index, value in enumerate(key):
            s = s.replace(value, str(index))
        payload += chr(int(step_2(s, seperator, 10)) - load)
        i += 1
    payload = re.findall(
        r'action="([^\"]+)" method="POST"><input type="hidden" name="_token"\s+value="([^\"]+)', payload
    )[0]
    return payload

def get_dl_link(link: str):
    resp = s.get(link)
    data, key, load, seperator = re.findall(r'\("(\S+)",\d+,"(\S+)",(\d+),(\d+)', resp.text)[0]
    url, token = step_1(data=data, key=key, load=load, seperator=seperator)
    data = {"_token": token}
    headers = {'referer': link}
    resp = s.post(url=url, data=data, headers=headers, allow_redirects=False)
    return resp.headers["location"]

@app.route('/')
def index():
    return jsonify({
        "message": f"Anime Pahe API [MADE BY RAHAT]",
        "endpoints": {
            "/download/<session_id>/<episode_session>": "Get download links",
            "/episodes/<session_id>/<page>": "Get episode list",
            "/anime/<session_id>": "Get anime details",
            "/search/<query>": "Search for anime"
        }
    })


@app.route('/frontend')
def frontend():
    return send_file('index.html')



@app.route('/search/<query>')
def search_anime(query):
    """Search for anime on AnimePahe"""
    search_url = f"https://animepahe.ru/api?m=search&q={query.replace(' ', '+')}"
    try:
        response = session.get(search_url).json()
        if response['total'] == 0:
            return jsonify({"error": "Anime not found"}), 404
        
        results = []
        for anime in response['data']:
            results.append({
                "id": anime['id'],
                "title": anime['title'],
                "session_id": anime['session'],
                "type": anime['type'],
                "episodes": anime['episodes'],
                "season": anime['season'],
                "id": anime['id'],
                "year": anime['year'],
                "score": anime['score'],
                "poster": anime['poster']
            })
        
        return jsonify(
            {"results": results,
             "api made by": "RAHAT"
             }
        )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
@app.route('/anime/<session_id>')
def get_anime_details(session_id):
    """Get details for a specific anime"""
    anime_url = f"https://animepahe.ru/anime/{session_id}"
    try:
        response = session.get(anime_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract basic info
        title = soup.select_one('.title-wrapper h1 span').text.strip()
        japanese_title = soup.select_one('.title-wrapper h2.japanese').text.strip() if soup.select_one('.title-wrapper h2.japanese') else None
        poster = soup.select_one('.anime-poster img')['data-src']
        
        # Extract synopsis
        synopsis = soup.select_one('.anime-synopsis').get_text(separator='\n').strip() if soup.select_one('.anime-synopsis') else None
        
        # Extract details from the sidebar
        details = {}
        info_items = soup.select('.anime-info > p:not(.external-links)')
        for item in info_items:
            key = item.find('strong').text.strip().replace(':', '').lower()
            # Remove the strong tag to get just the value
            value = ''.join(item.find_all(text=True, recursive=False)).strip()
            # Handle links in the value
            if item.find('a'):
                value = item.find('a').text.strip()
            details[key] = value
        
        # Extract genres
        genres = []
        genre_list = soup.select('.anime-genre a')
        for genre in genre_list:
            genres.append(genre.text.strip())
        
        # Extract external links
        external_links = {}
        external_links_section = soup.select_one('.external-links')
        if external_links_section:
            for link in external_links_section.find_all('a'):
                site = link.text.strip()
                url = link['href']
                external_links[site] = url
        
        # Extract relations (sequels, side stories, etc.)
        relations = {}
        relation_sections = soup.select('.anime-relation > div')
        for section in relation_sections:
            relation_type = section.find('h4').text.strip().lower().replace(' ', '_')
            relations[relation_type] = []
            
            for item in section.select('.col-12.col-sm-6.mb-3, .col-12.col-sm-12.mb-3'):
                relation = {
                    'title': item.select_one('h5 a').text.strip(),
                    'url': item.select_one('h5 a')['href'],
                    'type': item.select_one('strong a').text.strip(),
                    'episodes': item.select_one('br').previous_sibling.strip(),
                    'season': item.select_one('a[href*="/season/"]').text.strip() if item.select_one('a[href*="/season/"]') else None,
                    'poster': item.select_one('img')['data-src']
                }
                relations[relation_type].append(relation)
        
        # Extract recommendations
        '''recommendations = []
        rec_section = soup.select('.anime-recommendation .col-12.col-sm-6.mb-3')
        for rec in rec_section:
            recommendation = {
                'title': rec.select_one('h5 a').text.strip(),
                'url': rec.select_one('h5 a')['href'],
                'type': rec.select_one('strong a').text.strip(),
                'episodes': rec.select_one('br').previous_sibling.strip(),
                'season': rec.select_one('a[href*="/season/"]').text.strip() if rec.select_one('a[href*="/season/"]') else None,
                'poster': rec.select_one('img')['data-src']
            }
            recommendations.append(recommendation)'''
        
        return jsonify({
            "title": title,
            "japanese_title": japanese_title,
            "session_id": session_id,
            "poster": poster,
            "synopsis": synopsis,
            "details": details,
            "genres": genres,
            "external_links": external_links,
            "relations": relations,
            #"recommendations": recommendations,
            "link": anime_url,
            "api made by": "RAHAT"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/episodes/<session_id>/<page>')
def get_episodes(session_id, page):
    """Get list of episodes for an anime"""
    episodes_url = f"https://animepahe.ru/api?m=release&id={session_id}&sort=episode_asc&page={page}"
    
    try:
        response = session.get(episodes_url).json()
        last_page = int(response["last_page"])
        total = int(response["total"])
        current_page = int(response["current_page"])
        episodes = []
        
        for ep in response['data']:
            episodes.append({
                "page": current_page,
                "id": ep['id'],
                "anime_id": ep['anime_id'],
                "episode": ep['episode'],
                "session": ep['session'],
                "title": ep['title'],
                "audio": ep['audio'],
                "duration": ep['duration'],
                "snapshot": ep['snapshot'],
                "aired": ep['created_at']
            })
        
        return jsonify({
            "current_page": current_page,            
            "total_pages": last_page,
            "api made by": "RAHAT",
            "episodes": episodes
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download/<session_id>/<episode_session>')
def get_download_links(session_id, episode_session):
    """Get download links for a specific episode with direct download URLs"""
    episode_url = f"https://animepahe.ru/play/{session_id}/{episode_session}"
    
    
    try:
        response = session.get(episode_url)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Extract all download links and their titles
        download_links = soup.select("#pickDownload a.dropdown-item")
        
        if not download_links:
            return jsonify({"error": "No download links found"}), 404
        
        results = []
        for link in download_links:
            kwik_url = link['href']
            quality = link.get_text(strip=True)
            
            # First get the intermediate kwik.si link
            intermediate_link = extract_kwik_link(kwik_url)
            
            if not intermediate_link.startswith('http'):
                results.append({
                    "quality": quality,
                    "kwik_url": kwik_url,
                    "intermediate_url": None,
                    "direct_url": None,
                    "error": intermediate_link,
                    "success": False
                })
                continue
            
            # Then get the final direct link
            direct_link = get_dl_link(intermediate_link)
            
            if not direct_link.startswith('http'):
                results.append({
                    "quality": quality,
                    "kwik_url": kwik_url,
                    "intermediate_url": intermediate_link,
                    "direct_url": None,
                    "error": direct_link,
                    "success": False
                })
                continue
            
            results.append({
                "quality": quality,
                "kwik_url": kwik_url,
                "intermediate_url": intermediate_link,
                "direct_url": direct_link,
                "error": None,
                "success": True
            })
        
        return jsonify({
            "episode_session": episode_session,
            "results": results,
            "success_count": sum(1 for r in results if r['success']),
            "error_count": sum(1 for r in results if not r['success']),
            "api made by": "RAHAT"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500




def extract_kwik_link(url):
    """Helper function to extract Kwik link"""
    try:
        response = session.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        script_tags = soup.find_all('script', type="text/javascript")
        for script in script_tags:            
            match = re.search(r'https://kwik\.si/f/[\w\d]+', script.text)
            if match:
                return match.group(0)
        
        return "No kwik.si link found in the page."
    
    except Exception as e:
        return f"Error extracting kwik link: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Get PORT from environment variable or default to 5000
    app.run(host='0.0.0.0', port=port)  # Run on all network interfaces
