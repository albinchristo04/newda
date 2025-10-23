import requests
import json
import re
from datetime import datetime

def extract_m3u8_from_channel(channel_url):
    """Extract m3u8 URL from channel page"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://topembed.pw/'
        }
        
        response = requests.get(channel_url, headers=headers, timeout=15)
        content = response.text
        
        # Multiple patterns to find m3u8 URLs
        m3u8_patterns = [
            r'["\'](https?://[^"\']*\.m3u8[^"\']*)["\']',
            r'source\s*:\s*["\'](https?://[^"\']*\.m3u8[^"\']*)["\']',
            r'file\s*:\s*["\'](https?://[^"\']*\.m3u8[^"\']*)["\']',
            r'src\s*:\s*["\'](https?://[^"\']*\.m3u8[^"\']*)["\']',
            r'hlsUrl\s*:\s*["\'](https?://[^"\']*\.m3u8[^"\']*)["\']',
            r'stream\s*:\s*["\'](https?://[^"\']*\.m3u8[^"\']*)["\']',
        ]
        
        for pattern in m3u8_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                # Return the first valid m3u8 URL found
                return matches[0]
        
        # Also check for iframe that might contain the m3u8
        iframe_pattern = r'<iframe[^>]*src=["\'](https?://[^"\']+)["\']'
        iframe_matches = re.findall(iframe_pattern, content, re.IGNORECASE)
        if iframe_matches:
            # Try to extract m3u8 from the first iframe
            for iframe_url in iframe_matches[:2]:  # Check first 2 iframes
                try:
                    iframe_response = requests.get(iframe_url, headers=headers, timeout=10)
                    for pattern in m3u8_patterns:
                        matches = re.findall(pattern, iframe_response.text, re.IGNORECASE)
                        if matches:
                            return matches[0]
                except:
                    continue
        
        return None
    except Exception as e:
        print(f"  Error extracting m3u8 from {channel_url}: {e}")
        return None

def fetch_events():
    """Fetch events from the API"""
    api_url = "https://topembed.pw/api.php?format=json"
    
    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        print(f"Error fetching events: {e}")
        return None

def process_events(events_data):
    """Process events and extract m3u8 links"""
    processed_events = []
    
    if not events_data or 'events' not in events_data:
        print("No events found in API response")
        return processed_events
    
    events_by_date = events_data['events']
    
    for date, events_list in events_by_date.items():
        print(f"\n=== Processing events for {date} ===")
        
        for event in events_list:
            if not isinstance(event, dict):
                continue
            
            # Get event details
            sport = event.get('sport', 'Unknown')
            tournament = event.get('tournament', 'Unknown')
            match = event.get('match', 'Unknown')
            timestamp = event.get('unix_timestamp', 0)
            channels = event.get('channels', [])
            
            if not channels:
                continue
            
            print(f"\nProcessing: {sport} - {match}")
            print(f"  Channels found: {len(channels)}")
            
            # Process each channel URL
            channel_streams = []
            for idx, channel_url in enumerate(channels):
                print(f"  Extracting from channel {idx + 1}/{len(channels)}: {channel_url}")
                m3u8_url = extract_m3u8_from_channel(channel_url)
                
                if m3u8_url:
                    print(f"    ✓ Found m3u8: {m3u8_url[:80]}...")
                    channel_streams.append({
                        'channel_url': channel_url,
                        'm3u8_url': m3u8_url
                    })
                else:
                    print(f"    ✗ No m3u8 found")
                    channel_streams.append({
                        'channel_url': channel_url,
                        'm3u8_url': None
                    })
            
            # Create event info
            event_info = {
                'date': date,
                'unix_timestamp': timestamp,
                'sport': sport,
                'tournament': tournament,
                'match': match,
                'streams': channel_streams,
                'playback_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
    
    print(f"\n✓ Saved {len(data)} events to {filename}")

def main():
    print("=" * 60)
    print("M3U8 Stream Extractor")
    print("=" * 60)
    
    print("\nFetching events from API...")
    events_data = fetch_events()
    
    if not events_data:
        print("✗ No events data retrieved")
        return
    
    print(f"✓ API data retrieved successfully")
    
    if 'events' in events_data:
        total_dates = len(events_data['events'])
        total_events = sum(len(events) for events in events_data['events'].values())
        print(f"  Found {total_events} events across {total_dates} date(s)")
    
    print("\nExtracting m3u8 links from channels...")
    processed_events = process_events(events_data)
    
    # Calculate statistics
    m3u8_found = 0
    total_channels = 0
    for event in processed_events:
        for stream in event.get('streams', []):
            total_channels += 1
            if stream.get('m3u8_url'):
                m3u8_found += 1
    
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    print(f"Total events processed: {len(processed_events)}")
    print(f"Total channels checked: {total_channels}")
    print(f"M3U8 links found: {m3u8_found}")
    print(f"Success rate: {(m3u8_found/total_channels*100) if total_channels > 0 else 0:.1f}%")
    print("=" * 60)
    
    save_to_json(processed_events)
    print("\n✓ Done!")

if __name__ == "__main__":
    main()
