import requests
import json
import re
from urllib.parse import urlparse, parse_qs
from datetime import datetime

def extract_m3u8_from_iframe(iframe_url):
    """Extract m3u8 URL from iframe source"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://topembed.pw/'
        }
        
        response = requests.get(iframe_url, headers=headers, timeout=10)
        content = response.text
        
        # Search for m3u8 URLs in the iframe content
        m3u8_patterns = [
            r'["\'](https?://[^"\']*\.m3u8[^"\']*)["\']',
            r'source\s*:\s*["\'](https?://[^"\']*\.m3u8[^"\']*)["\']',
            r'file\s*:\s*["\'](https?://[^"\']*\.m3u8[^"\']*)["\']',
        ]
        
        for pattern in m3u8_patterns:
            matches = re.findall(pattern, content)
            if matches:
                return matches[0]
        
        return None
    except Exception as e:
        print(f"Error extracting m3u8 from {iframe_url}: {e}")
        return None

def fetch_events():
    """Fetch events from the API"""
    api_url = "https://topembed.pw/api.php?format=json"
    
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        print(f"Error fetching events: {e}")
        return None

def process_events(events_data):
    """Process events and extract m3u8 links"""
    processed_events = []
    
    if not events_data:
        return processed_events
    
    # Handle different possible API response structures
    events = events_data if isinstance(events_data, list) else events_data.get('events', [])
    
    for event in events:
        iframe_url = event.get('iframe') or event.get('embed') or event.get('stream_url')
        
        if not iframe_url:
            continue
        
        print(f"Processing: {event.get('title', 'Unknown event')}")
        
        m3u8_url = extract_m3u8_from_iframe(iframe_url)
        
        event_info = {
            'id': event.get('id'),
            'title': event.get('title'),
            'description': event.get('description'),
            'category': event.get('category'),
            'time': event.get('time'),
            'date': event.get('date'),
            'iframe_url': iframe_url,
            'm3u8_url': m3u8_url,
            'playback_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://topembed.pw/',
                'Origin': 'https://topembed.pw'
            },
            'last_updated': datetime.utcnow().isoformat()
        }
        
        processed_events.append(event_info)
    
    return processed_events

def save_to_json(data, filename='events_m3u8.json'):
    """Save processed events to JSON file"""
    output = {
        'updated_at': datetime.utcnow().isoformat(),
        'total_events': len(data),
        'events': data
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(data)} events to {filename}")

def main():
    print("Fetching events from API...")
    events_data = fetch_events()
    
    if not events_data:
        print("No events data retrieved")
        return
    
    print("Processing events and extracting m3u8 links...")
    processed_events = process_events(events_data)
    
    print(f"Successfully processed {len(processed_events)} events")
    save_to_json(processed_events)
    
    # Print summary
    m3u8_found = sum(1 for e in processed_events if e.get('m3u8_url'))
    print(f"\nSummary:")
    print(f"Total events: {len(processed_events)}")
    print(f"M3U8 links found: {m3u8_found}")

if __name__ == "__main__":
    main()
