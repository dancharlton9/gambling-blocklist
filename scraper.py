#!/usr/bin/env python3
"""
Non-GamStop Casino Blocklist Scraper

Scrapes aggregator sites that advertise non-GamStop casinos and extracts
the casino domains they promote. Intended for harm reduction.

This list is designed to complement existing gambling blocklists by
specifically targeting offshore casinos that circumvent GamStop.
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-GB,en;q=0.5',
}

# Aggregator sites that list non-GamStop casinos
# These are the sites we scrape to find casino domains
AGGREGATOR_URLS = [
    'https://www.nongamstopcasinos.net/',
    'https://www.nongamstopcasinos.net/new-casinos-not-on-gamstop/',
    'https://www.nongamstopcasinos.net/crypto-casinos-not-on-gamstop/',
    'https://casinonotongamstop.com/',
    'https://www.casinosnotongamstop.org/',
    'https://www.nonstopcasino.org/',
    'https://nonstopcasino.org/uk/',
    'https://casinosanalyzer.com/non-gamstop-casinos',
    'https://www.casinosanalyzer.com/online-casinos/not-on-gamstop',
]

# Domains to exclude (legitimate sites, support sites, false positives)
EXCLUDE_DOMAINS = {
    # Search engines, social media, etc
    'google.com', 'facebook.com', 'twitter.com', 'youtube.com', 'instagram.com',
    'linkedin.com', 'reddit.com', 'wikipedia.org', 'amazon.com', 't.co', 'x.com',
    # Responsible gambling / support
    'gamstop.co.uk', 'begambleaware.org', 'gamcare.org.uk', 'gamblingcommission.gov.uk',
    'responsiblegambling.org', 'ncpgambling.org', 'gamblersanonymous.org',
    # CDNs and common services
    'cloudflare.com', 'jsdelivr.net', 'googleapis.com', 'gstatic.com',
    'w3.org', 'schema.org', 'trustpilot.com',
    # The aggregator sites themselves (we scrape them, not block them)
    'nongamstopcasinos.net', 'casinonotongamstop.com', 'casinosnotongamstop.org',
    'nonstopcasino.org', 'casinosanalyzer.com',
}

# TLDs commonly used by gambling sites
GAMBLING_TLDS = {'.casino', '.bet', '.games', '.game', '.io', '.ag', '.gg', '.vip', '.win', '.fun'}


class NonGamstopScraper:
    def __init__(self):
        self.domains = set()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
    
    def is_valid_domain(self, domain: str) -> bool:
        """Check if domain is valid and not excluded."""
        domain = domain.lower().strip()
        
        if not domain or len(domain) < 4 or len(domain) > 100:
            return False
        if '.' not in domain:
            return False
        if not re.match(r'^[a-z0-9][-a-z0-9.]*[a-z0-9]$', domain):
            return False
        
        # Check exclusions
        for excluded in EXCLUDE_DOMAINS:
            if domain == excluded or domain.endswith('.' + excluded):
                return False
        
        return True
    
    def looks_like_casino(self, domain: str) -> bool:
        """Check if domain looks like a gambling site."""
        gambling_keywords = [
            'casino', 'bet', 'slots', 'poker', 'spin', 'vegas', 'lucky',
            'jackpot', 'win', 'game', 'play', 'wager', 'stake', 'roulette'
        ]
        
        # Check TLD
        for tld in GAMBLING_TLDS:
            if domain.endswith(tld):
                return True
        
        # Check keywords in domain
        domain_lower = domain.lower()
        for keyword in gambling_keywords:
            if keyword in domain_lower:
                return True
        
        return False
    
    def extract_domains_from_html(self, html: str) -> set:
        """Extract casino domains from HTML content."""
        found = set()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract from all links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            try:
                if href.startswith(('http://', 'https://')):
                    parsed = urlparse(href)
                    domain = parsed.netloc.lower().replace('www.', '')
                    if self.is_valid_domain(domain):
                        found.add(domain)
            except Exception:
                pass
        
        return found
    
    def scrape_aggregator(self, url: str, delay: float = 3.0) -> set:
        """Scrape a single aggregator URL for casino domains."""
        found = set()
        try:
            logger.info(f"Scraping: {url}")
            time.sleep(delay)
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            all_domains = self.extract_domains_from_html(response.text)
            
            # Filter to only likely casino domains
            for domain in all_domains:
                if self.looks_like_casino(domain):
                    found.add(domain)
            
            logger.info(f"  Found {len(found)} casino domains")
            
        except Exception as e:
            logger.warning(f"  Error scraping {url}: {e}")
        
        return found
    
    def load_manual_domains(self) -> set:
        """Load manually added domains from domains/manual.txt"""
        manual_file = Path(__file__).parent / 'domains' / 'manual.txt'
        domains = set()
        
        if manual_file.exists():
            for line in manual_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    if self.is_valid_domain(line):
                        domains.add(line.lower())
            logger.info(f"Loaded {len(domains)} manual domains")
        
        return domains
    
    def generate_variants(self, domains: set) -> set:
        """Generate numbered variants (1-9 only) for discovered domains."""
        variants = set()
        
        for domain in domains:
            parts = domain.split('.')
            if len(parts) >= 2:
                base = parts[0]
                tld = '.'.join(parts[1:])
                
                # Only generate if base doesn't already end in a number
                if not base[-1].isdigit():
                    for i in range(1, 10):  # 1-9 only
                        variants.add(f"{base}{i}.{tld}")
        
        return {d for d in variants if self.is_valid_domain(d)}
    
    def run(self) -> set:
        """Run the scraper."""
        logger.info("Starting non-GamStop casino scraper...")
        
        # Load manual domains first
        self.domains.update(self.load_manual_domains())
        
        # Scrape each aggregator
        for url in AGGREGATOR_URLS:
            found = self.scrape_aggregator(url)
            self.domains.update(found)
        
        logger.info(f"Total unique domains found: {len(self.domains)}")
        
        # Generate limited variants
        variants = self.generate_variants(self.domains)
        self.domains.update(variants)
        logger.info(f"Total after variants (1-9): {len(self.domains)}")
        
        return self.domains


def generate_blocklist_files(domains: set, output_dir: Path):
    """Generate blocklist files in multiple formats."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    sorted_domains = sorted(domains)
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    header = f"""# Non-GamStop Casino Blocklist
#
# Offshore casinos that circumvent GamStop self-exclusion.
# Intended for harm reduction - use alongside standard gambling blocklists.
#
# Repository: https://github.com/YOUR_USERNAME/gambling-blocklist
# Last updated: {timestamp}
# Total domains: {len(sorted_domains)}

"""

    # Pi-hole format (just domains)
    (output_dir / 'non-gamstop-blocklist.txt').write_text(
        header + '\n'.join(sorted_domains)
    )
    
    # Hosts file format
    hosts_lines = [f"0.0.0.0 {d}" for d in sorted_domains]
    (output_dir / 'non-gamstop-blocklist-hosts.txt').write_text(
        header + '\n'.join(hosts_lines)
    )
    
    # AdGuard format
    adguard_lines = [f"||{d}^" for d in sorted_domains]
    (output_dir / 'non-gamstop-blocklist-adguard.txt').write_text(
        header.replace('# ', '! ') + '\n'.join(adguard_lines)
    )
    
    # JSON format
    json_data = {
        'updated': timestamp,
        'count': len(sorted_domains),
        'domains': sorted_domains
    }
    (output_dir / 'non-gamstop-blocklist.json').write_text(
        json.dumps(json_data, indent=2)
    )
    
    logger.info(f"Generated blocklists in {output_dir}")


def main():
    scraper = NonGamstopScraper()
    domains = scraper.run()
    
    output_dir = Path(__file__).parent / 'lists'
    generate_blocklist_files(domains, output_dir)
    
    logger.info(f"Done! {len(domains)} domains in blocklist")


if __name__ == '__main__':
    main()
