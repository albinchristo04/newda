#!/usr/bin/env python3
"""
M3U8 URL and Events Extractor
Extracts M3U8 URLs and event information from playlist
"""

import requests
import re
import json
import datetime
import os
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

class M3U8Extractor:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_playlist(self, url: str) -> Optional[str]:
        """Fetch M3U8 playlist content"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching playlist: {e}")
            return None
    
    def parse_m3u8(self, content: str, base_url: str) -> Dict:
        """Parse M3U8 content and extract URLs and metadata"""
        lines = content.strip().split('\n')
        
        result = {
            'timestamp': datetime.datetime.now().isoformat(),
            'base_url': base_url,
            'streams': [],
            'segments': [],
            'events': [],
            'metadata': {}
        }
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('#EXT-X-VERSION'):
                result['metadata']['version'] = line.split(':')[1]
            
            elif line.startswith('#EXT-X-TARGETDURATION'):
                result['metadata']['target_duration'] = int(line.split(':')[1])
            
            elif line.startswith('#EXT-X-MEDIA-SEQUENCE'):
                result['metadata']['media_sequence'] = int(line.split(':')[1])
            
            elif line.startswith('#EXT-X-STREAM-INF'):
                # Master playlist with multiple streams
                stream_info = self.parse_stream_inf(line)
                if i + 1 < len(lines):
                    stream_url = lines[i + 1].strip()
                    if not stream_url.startswith('http'):
                        stream_url = urljoin(base_url, stream_url)
                    stream_info['url'] = stream_url
                    result['streams'].append(stream_info)
                i += 1
            
            elif line.startswith('#EXTINF'):
                # Media segment
                segment_info = self.parse_extinf(line)
                if i + 1 < len(lines):
                    segment_url = lines[i + 1].strip()
                    if not segment_url.startswith('http'):
                        segment_url = urljoin(base_url, segment_url)
                    segment_info['url'] = segment_url
                    result['segments'].append(segment_info)
                i += 1
            
            elif line.startswith('#EXT-X-PROGRAM-DATE-TIME'):
                # Program date time (event timing)
                pdt = line.split(':', 1)[1]
                result['events'].append({
                    'type': 'program_date_time',
                    'timestamp': pdt,
                    'line_number': i
                })
            
            elif line.startswith('#EXT-X-DATERANGE'):
                # Date range (event information)
                event_info = self.parse_daterange(line)
                result['events'].append(event_info)
            
            elif line.startswith('#EXT-X-CUE-OUT'):
                # Ad break start
                result['events'].append({
                    'type': 'cue_out',
                    'duration': line.split(':', 1)[1] if ':' in line else None,
                    'line_number': i
                })
            
            elif line.startswith('#EXT-X-CUE-IN'):
                # Ad break end
                result['events'].append({
                    'type': 'cue_in',
                    'line_number': i
                })
            
            i += 1
        
        return result
    
    def parse_stream_inf(self, line: str) -> Dict:
        """Parse EXT-X-STREAM-INF line"""
        info = {'type': 'stream'}
        
        # Extract bandwidth
        bandwidth_match = re.search(r'BANDWIDTH=(\d+)', line)
        if bandwidth_match:
            info['bandwidth'] = int(bandwidth_match.group(1))
        
        # Extract resolution
        resolution_match = re.search(r'RESOLUTION=(\d+x\d+)', line)
        if resolution_match:
            info['resolution'] = resolution_match.group(1)
        
        # Extract codecs
        codecs_match = re.search(r'CODECS="([^"]+)"', line)
        if codecs_match:
            info['codecs'] = codecs_match.group(1)
        
        return info
    
    def parse_extinf(self, line: str) -> Dict:
        """Parse EXTINF line"""
        info = {'type': 'segment'}
        
        # Extract duration
        duration_match = re.search(r'#EXTINF:([\d.]+)', line)
        if duration_match:
            info['duration'] = float(duration_match.group(1))
        
        # Extract title if present
        if ',' in line:
            title = line.split(',', 1)[1].strip()
            if title:
                info['title'] = title
        
        return info
    
    def parse_daterange(self, line: str) -> Dict:
        """Parse EXT-X-DATERANGE line"""
        event = {'type': 'daterange'}
        
        # Extract ID
        id_match = re.search(r'ID="([^"]+)"', line)
        if id_match:
            event['id'] = id_match.group(1)
        
        # Extract start date
        start_match = re.search(r'START-DATE="([^"]+)"', line)
        if start_match:
            event['start_date'] = start_match.group(1)
        
        # Extract end date
        end_match = re.search(r'END-DATE="([^"]+)"', line)
        if end_match:
            event['end_date'] = end_match.group(1)
        
        # Extract duration
        duration_match = re.search(r'DURATION=([\d.]+)', line)
        if duration_match:
            event['duration'] = float(duration_match.group(1))
        
        return event
    
    def extract_all(self, url: str) -> Dict:
        """Main extraction method"""
        print(f"Fetching playlist from: {url}")
        
        content = self.fetch_playlist(url)
        if not content:
            return {'error': 'Failed to fetch playlist'}
        
        result = self.parse_m3u8(content, url)
        
        # If this is a master playlist, also fetch individual streams
        if result['streams']:
            print(f"Found {len(result['streams'])} streams")
            for stream in result['streams']:
                stream_content = self.fetch_playlist(stream['url'])
                if stream_content:
                    stream_data = self.parse_m3u8(stream_content, stream['url'])
                    stream['segments'] = stream_data['segments']
                    stream['events'] = stream_data['events']
                    stream['metadata'] = stream_data['metadata']
        
        return result

def save_results(data: Dict, output_dir: str = 'output'):
    """Save extraction results to files"""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save full data as JSON
    json_file = os.path.join(output_dir, f'playlist_{timestamp}.json')
    with open(json_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    # Save URLs only
    urls_file = os.path.join(output_dir, f'urls_{timestamp}.txt')
    with open(urls_file, 'w') as f:
        f.write(f"Extracted at: {data.get('timestamp', 'Unknown')}\n")
        f.write(f"Base URL: {data.get('base_url', 'Unknown')}\n\n")
        
        if data.get('streams'):
            f.write("STREAM URLs:\n")
            for i, stream in enumerate(data['streams']):
                f.write(f"{i+1}. {stream.get('url', 'N/A')}\n")
                f.write(f"   Bandwidth: {stream.get('bandwidth', 'N/A')}\n")
                f.write(f"   Resolution: {stream.get('resolution', 'N/A')}\n\n")
        
        if data.get('segments'):
            f.write("SEGMENT URLs (first 10):\n")
            for i, segment in enumerate(data['segments'][:10]):
                f.write(f"{i+1}. {segment.get('url', 'N/A')}\n")
    
    # Save events
    if data.get('events'):
        events_file = os.path.join(output_dir, f'events_{timestamp}.json')
        with open(events_file, 'w') as f:
            json.dump(data['events'], f, indent=2, default=str)
    
    print(f"Results saved to {output_dir}/")
    return json_file, urls_file

def main():
    url = "https://world-proxifier.xyz/rbtv/playlist.m3u8?timezone=pht"
    
    extractor = M3U8Extractor(url)
    results = extractor.extract_all(url)
    
    if 'error' in results:
        print(f"Error: {results['error']}")
        return
    
    # Print summary
    print(f"\nExtraction Summary:")
    print(f"- Streams found: {len(results.get('streams', []))}")
    print(f"- Segments found: {len(results.get('segments', []))}")
    print(f"- Events found: {len(results.get('events', []))}")
    
    # Save results
    save_results(results)
    
    # Print some sample data
    if results.get('streams'):
        print(f"\nSample stream URLs:")
        for stream in results['streams'][:3]:
            print(f"- {stream.get('url', 'N/A')} (Bandwidth: {stream.get('bandwidth', 'N/A')})")
    
    if results.get('events'):
        print(f"\nSample events:")
        for event in results['events'][:3]:
            print(f"- {event.get('type', 'Unknown')}: {event}")

if __name__ == "__main__":
    main()
