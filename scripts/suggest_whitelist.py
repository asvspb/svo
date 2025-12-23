#!/usr/bin/env python3
"""
Script to analyze capture manifest and suggest improved whitelist settings.
"""
import json
import sys
from urllib.parse import urlparse
from collections import Counter


def analyze_manifest(manifest_path: str) -> dict:
    """
    Analyze capture manifest and suggest whitelist improvements.
    """
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    # Find all URLs with json_like = true
    json_urls = [entry for entry in manifest if entry.get('json_like', False)]
    
    print(f"Found {len(json_urls)} JSON-like URLs in manifest")
    print("\nJSON-like URLs:")
    for entry in json_urls:
        print(f"  {entry['url']} (allowed: {entry['allowed']})")
    
    # Extract path segments and common patterns
    path_segments = []
    domains = []
    
    for entry in json_urls:
        url = entry['url']
        parsed = urlparse(url)
        domains.append(parsed.netloc)
        
        # Split path into segments and filter out common non-data segments
        path_parts = [p for p in parsed.path.split('/') if p and p not in ['api', 'v1', 'v2', 'json']]
        path_segments.extend(path_parts)
    
    domain_counts = Counter(domains)
    path_counts = Counter(path_segments)
    
    print(f"\nTop domains:")
    for domain, count in domain_counts.most_common():
        print(f"  {domain}: {count}")
    
    print(f"\nTop path segments:")
    for segment, count in path_counts.most_common():
        print(f"  {segment}: {count}")
    
    # Suggest whitelist based on findings
    suggested_whitelist = []
    
    # Add domain-based patterns
    for domain in domain_counts.keys():
        if domain != 'deepstatemap.live':  # Main domain is always included
            suggested_whitelist.append(domain)
    
    # Add path-based patterns from JSON URLs
    for entry in json_urls:
        parsed = urlparse(entry['url'])
        path = parsed.path
        if path.endswith('.json'):
            # Add the directory name or the full path pattern
            dir_name = path.rsplit('/', 1)[0] if '/' in path else path
            if dir_name and dir_name not in ['/api', '/images', '/css', '/js']:
                suggested_whitelist.append(dir_name.lstrip('/'))
        
        # Add API endpoints
        if '/api/' in path:
            api_part = path.split('/api/', 1)[1].split('/')[0]
            if api_part:
                suggested_whitelist.append(f"api/{api_part}")
    
    # Remove duplicates while preserving order
    unique_suggestions = list(dict.fromkeys(suggested_whitelist))
    
    print(f"\nSuggested ENDPOINT_WHITELIST entries:")
    for suggestion in unique_suggestions:
        print(f"  {suggestion}")
    
    return {
        'json_urls': json_urls,
        'domain_counts': domain_counts,
        'path_counts': path_counts,
        'suggested_whitelist': unique_suggestions
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: python suggest_whitelist.py <manifest_path>")
        sys.exit(1)
    
    manifest_path = sys.argv[1]
    analysis = analyze_manifest(manifest_path)
    
    print(f"\n" + "="*50)
    print("SUMMARY FOR .ENV FILE:")
    print("="*50)
    whitelist_str = ','.join(analysis['suggested_whitelist'])
    print(f"ENDPOINT_WHITELIST={whitelist_str}")
    print("\nThis configuration will help capture the most relevant JSON data")
    print("while filtering out unnecessary resources like images, CSS, etc.")


if __name__ == "__main__":
    main()