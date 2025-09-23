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
            'grouped_events': {},
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
                # Media segment or event entry
                extinf_info = self.parse_extinf(line)
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    
                    # Check if this is an event/channel entry (has title with time and description)
                    if extinf_info.get('title') and self.is_event_entry(extinf_info['title']):
                        event_info = self.parse_event_title(extinf_info['title'])
                        if not next_line.startswith('http'):
                            next_line = urljoin(base_url, next_line)
                        
                        event_info.update({
                            'url': next_line,
                            'duration': extinf_info.get('duration'),
                            'logo': extinf_info.get('logo'),
                            'group_title': extinf_info.get('group_title')
                        })
                        
                        # Group events by title
                        event_title = event_info.get('event_title', 'Unknown Event')
                        if event_title not in result['grouped_events']:
                            result['grouped_events'][event_title] = {
                                'event_title': event_title,
                                'event_time': event_info.get('event_time'),
                                'event_date': event_info.get('event_date'),
                                'category': event_info.get('category'),
                                'channels': []
                            }
                        
                        result['grouped_events'][event_title]['channels'].append({
                            'channel_name': event_info.get('channel_name'),
                            'url': event_info.get('url'),
                            'logo': event_info.get('logo'),
                            'duration': event_info.get('duration')
                        })
                        
                        result['events'].append(event_info)
                    else:
                        # Regular media segment
                        if not next_line.startswith('http'):
                            next_line = urljoin(base_url, next_line)
                        extinf_info['url'] = next_line
                        result['segments'].append(extinf_info)
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
        duration_match = re.search(r'#EXTINF:([\d.-]+)', line)
        if duration_match:
            duration_val = duration_match.group(1)
            if duration_val != '-1':
                info['duration'] = float(duration_val)
        
        # Extract tvg-logo
        logo_match = re.search(r'tvg-logo="([^"]+)"', line)
        if logo_match:
            info['logo'] = logo_match.group(1)
        
        # Extract group-title
        group_match = re.search(r'group-title="([^"]+)"', line)
        if group_match:
            info['group_title'] = group_match.group(1)
        
        # Extract title (everything after the comma)
        if ',' in line:
            title = line.split(',', 1)[1].strip()
            if title:
                info['title'] = title
        
        return info
    
    def is_event_entry(self, title: str) -> bool:
        """Check if this is an event entry based on title format"""
        # Look for time patterns like "01:00AM|", "12:30PM|", etc.
        time_pattern = r'\d{1,2}:\d{2}(AM|PM)\s*\|'
        return bool(re.search(time_pattern, title, re.IGNORECASE))
    
    def parse_event_title(self, title: str) -> Dict:
        """Parse event title to extract time, event name, and channel info"""
        event_info = {}
        
        # Extract time (e.g., "01:00AM")
        time_match = re.search(r'(\d{1,2}:\d{2}(?:AM|PM))', title, re.IGNORECASE)
        if time_match:
            event_info['event_time'] = time_match.group(1)
        
        # Extract date if present (e.g., "(09/23/25)")
        date_match = re.search(r'\((\d{1,2}/\d{1,2}/\d{2,4})\)', title)
        if date_match:
            event_info['event_date'] = date_match.group(1)
        
        # Split by pipe to separate time from event description
        if '|' in title:
            parts = title.split('|', 1)
            if len(parts) > 1:
                event_description = parts[1].strip()
                
                # Check for channel indicator at the end [VDO], [HDD A], etc.
                channel_match = re.search(r'\[([^\]]+)\]$', event_description)
                if channel_match:
                    event_info['channel_name'] = channel_match.group(1).strip()
                    # Remove channel indicator from event description
                    event_description = re.sub(r'\s*\[[^\]]+\]$', '', event_description).strip()
                
                # The remaining is the event title
                event_info['event_title'] = event_description
        
        # If no pipe, use the whole title
        if 'event_title' not in event_info:
            # Remove time and channel parts
            clean_title = title
            clean_title = re.sub(r'\d{1,2}:\d{2}(?:AM|PM)\s*\|?', '', clean_title, flags=re.IGNORECASE)
            clean_title = re.sub(r'\s*\[[^\]]+\]$', '', clean_title)
            event_info['event_title'] = clean_title.strip()
        
        return event_info
    
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
    
    # Save full data as JSON with fixed filename
    json_file = os.path.join(output_dir, 'rbtv.json')
    with open(json_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    # Save grouped events as separate JSON with fixed filename
    if data.get('grouped_events'):
        grouped_file = os.path.join(output_dir, 'rbtv_grouped_events.json')
        with open(grouped_file, 'w') as f:
            json.dump(data['grouped_events'], f, indent=2, default=str)
    
    # Save URLs with grouping with fixed filename
    urls_file = os.path.join(output_dir, 'rbtv_urls.txt')
    with open(urls_file, 'w') as f:
        f.write(f"Extracted at: {data.get('timestamp', 'Unknown')}\n")
        f.write(f"Base URL: {data.get('base_url', 'Unknown')}\n\n")
        
        # Write grouped events
        if data.get('grouped_events'):
            f.write("=== GROUPED EVENTS BY TITLE ===\n\n")
            for event_title, event_data in data['grouped_events'].items():
                f.write(f"EVENT: {event_title}\n")
                f.write(f"Time: {event_data.get('event_time', 'N/A')}\n")
                f.write(f"Date: {event_data.get('event_date', 'N/A')}\n")
                f.write(f"Category: {event_data.get('category', 'N/A')}\n")
                f.write(f"Available Channels ({len(event_data.get('channels', []))}):\n")
                
                for i, channel in enumerate(event_data.get('channels', []), 1):
                    f.write(f"  {i}. {channel.get('channel_name', 'Unknown Channel')}\n")
                    f.write(f"     URL: {channel.get('url', 'N/A')}\n")
                    if channel.get('logo'):
                        f.write(f"     Logo: {channel.get('logo')}\n")
                f.write("\n" + "="*80 + "\n\n")
        
        # Write individual streams if any
        if data.get('streams'):
            f.write("=== INDIVIDUAL STREAMS ===\n\n")
            for i, stream in enumerate(data['streams']):
                f.write(f"{i+1}. {stream.get('url', 'N/A')}\n")
                f.write(f"   Bandwidth: {stream.get('bandwidth', 'N/A')}\n")
                f.write(f"   Resolution: {stream.get('resolution', 'N/A')}\n\n")
        
        # Write segments (first 10) if any
        if data.get('segments'):
            f.write("=== MEDIA SEGMENTS (First 10) ===\n\n")
            for i, segment in enumerate(data['segments'][:10]):
                f.write(f"{i+1}. {segment.get('url', 'N/A')}\n")
    
    # Save a summary file with fixed filename
    summary_file = os.path.join(output_dir, 'rbtv_summary.txt')
    with open(summary_file, 'w') as f:
        f.write("M3U8 EXTRACTION SUMMARY\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Extraction Time: {data.get('timestamp', 'Unknown')}\n")
        f.write(f"Source URL: {data.get('base_url', 'Unknown')}\n\n")
        
        # Statistics
        grouped_events = data.get('grouped_events', {})
        total_channels = sum(len(event['channels']) for event in grouped_events.values())
        
        f.write("STATISTICS:\n")
        f.write(f"- Unique Events: {len(grouped_events)}\n")
        f.write(f"- Total Channels: {total_channels}\n")
        f.write(f"- Individual Streams: {len(data.get('streams', []))}\n")
        f.write(f"- Media Segments: {len(data.get('segments', []))}\n")
        f.write(f"- Other Events: {len(data.get('events', [])) - total_channels}\n\n")
        
        # Event breakdown
        if grouped_events:
            f.write("EVENT BREAKDOWN:\n")
            for event_title, event_data in grouped_events.items():
                channel_count = len(event_data.get('channels', []))
                f.write(f"- {event_title[:60]}{'...' if len(event_title) > 60 else ''}\n")
                f.write(f"  Time: {event_data.get('event_time', 'N/A')}, Channels: {channel_count}\n")
    
    print(f"Results saved to {output_dir}/ (files updated)")
    return json_file, urls_file, summary_file

def main():
    url = "https://world-proxifier.xyz/rbtv/playlist.m3u8?timezone=pht"
    
    extractor = M3U8Extractor(url)
    results = extractor.extract_all(url)
    
    if 'error' in results:
        print(f"Error: {results['error']}")
        return
    
    # Print summary
    print(f"\nExtraction Summary:")
    print(f"- Grouped Events: {len(results.get('grouped_events', {}))}")
    print(f"- Total Channels: {sum(len(event['channels']) for event in results.get('grouped_events', {}).values())}")
    print(f"- Individual Streams: {len(results.get('streams', []))}")
    print(f"- Media Segments: {len(results.get('segments', []))}")
    print(f"- Other Events: {len(results.get('events', []))}")
    
    # Save results
    save_results(results)
    
    # Print grouped events preview
    grouped_events = results.get('grouped_events', {})
    if grouped_events:
        print(f"\nGrouped Events Preview:")
        for i, (event_title, event_data) in enumerate(list(grouped_events.items())[:3]):
            print(f"{i+1}. {event_title}")
            print(f"   Time: {event_data.get('event_time', 'N/A')}")
            print(f"   Channels: {len(event_data.get('channels', []))}")
            for j, channel in enumerate(event_data.get('channels', [])[:2]):
                print(f"     - {channel.get('channel_name', 'Unknown')}: {channel.get('url', 'N/A')}")
        
        if len(grouped_events) > 3:
            print(f"   ... and {len(grouped_events) - 3} more events")
    
    # Print sample individual streams if any
    if results.get('streams'):
        print(f"\nSample individual streams:")
        for stream in results['streams'][:2]:
            print(f"- {stream.get('url', 'N/A')} (Bandwidth: {stream.get('bandwidth', 'N/A')})")

if __name__ == "__main__":
    main()
