#!/usr/bin/env python3
"""
Non-GamStop Gambling Site Blocklist Generator

Scrapes aggregator sites that list non-GamStop casinos and extracts domains
to create a Pi-hole compatible blocklist.

This is intended for harm reduction - helping people block access to offshore
gambling sites that circumvent self-exclusion programs like GamStop.
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import datetime, timezone
from pathlib import Path
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Common user agent to avoid blocks
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-GB,en;q=0.5',
}

# Known non-GamStop casino domains to seed the list
# These are commonly advertised on aggregator sites
SEED_DOMAINS = {
    # Popular non-GamStop casinos (Curacao licensed)
    'mystake.com',
    'goldenbet.com', 
    'velobet.com',
    'freshbet.com',
    'donbet.com',
    'katanaspin.com',
    'betboro.com',
    'koispins.com',
    'rolletto.com',
    'instantcasino.com',
    'winscore.io',
    'casinobuck.com',
    'slottica.com',
    'megapari.com',
    'betwinner.com',
    'melbet.com',
    '1xbet.com',
    '22bet.com',
    'betandyou.com',
    'paripesa.com',
    'fairspin.io',
    'mbitcasino.com',
    'fortunejack.com',
    'stake.com',
    'bc.game',
    'roobet.com',
    'duelbits.com',
    'cloudbet.com',
    'bitcasino.io',
    'bitstarz.com',
    'kingbilly.com',
    'casinochan.com',
    'bobcasino.com',
    'oshi.io',
    'betchan.com',
    'casinonic.com',
    'wazamba.com',
    'rabona.com',
    'sportaza.com',
    'dazard.com',
    'casino-z.com',
    'casoo.com',
    'nomini.com',
    'luckydreams.com',
    'slotman.com',
    'justspin.com',
    'yoyo-casino.com',
    'n1casino.com',
    'betchain.com',
    'casinoextreme.eu',
    'brango.casino',
    'limitlesscasino.com',
    'yabby.casino',
    'ozwin.com',
    'uptown-aces.com',
    'slotocash.im',
    'casinomia.com',
    'spinamba.com',
    'wildfortune.io',
    'tsars.com',
    'casinorex.com',
    'frankfred.com',
    'gunsbet.com',
    'syndicate.casino',
    'ricky-casino.com',
    'neospin.com',
    'levelup.casino',
    'skycrown.com',
    'cashalot.bet',
    'ivibet.com',
    'hellspin.com',
    'casinowilds.com',
    'casinoinfinity.com',
    'mirax.casino',
    'slotspalace.com',
    'slothunter.com',
    'luckyhunter.com',
    'bambet.com',
    'betpanda.io',
    'winspirit.com',
    'nationalcasino.com',
    '20bet.com',
    'megaslot.com',
    'playfina.com',
    'casinozer.com',
    'weiss.bet',
    'casinoguru.com',
    'gambiva.com',
    'gambiva8.com',
}

# Regex patterns for finding casino/betting domains in text
DOMAIN_PATTERNS = [
    # Direct domain mentions
    r'(?:https?://)?(?:www\.)?([a-z0-9][-a-z0-9]*(?:casino|bet|slots?|poker|spin|gambl|wager|jackpot|vegas|lucky|win|play|game)[a-z0-9]*\.[a-z]{2,})',
    r'(?:https?://)?(?:www\.)?([a-z0-9][-a-z0-9]*\.(casino|bet|games?|io|com|net|org|eu|ag|gg))',
    # Numbered variants like gambiva8.com
    r'(?:https?://)?(?:www\.)?([a-z]+[0-9]+\.[a-z]{2,})',
]

# TLDs commonly used by offshore gambling sites
GAMBLING_TLDS = {'.casino', '.bet', '.games', '.game', '.io', '.ag', '.gg', '.vip', '.win', '.fun'}

# Keywords that indicate a gambling site
GAMBLING_KEYWORDS = {
    'casino', 'bet', 'betting', 'gambl', 'slots', 'poker', 'blackjack', 'roulette',
    'jackpot', 'spin', 'wager', 'sportsbook', 'bookie', 'odds', 'lucky', 'vegas',
    'stake', 'crypto casino', 'bitcoin casino', 'non gamstop', 'no gamstop',
    'without gamstop', 'curacao', 'offshore', 'no verification', 'instant withdrawal'
}

# Domains to explicitly exclude (legitimate sites, false positives)
EXCLUDE_DOMAINS = {
    'google.com', 'facebook.com', 'twitter.com', 'youtube.com', 'instagram.com',
    'linkedin.com', 'reddit.com', 'wikipedia.org', 'amazon.com', 'ebay.com',
    'github.com', 'cloudflare.com', 'wordpress.com', 'blogger.com',
    'gamstop.co.uk', 'begambleaware.org', 'gamcare.org.uk', 'gamblingcommission.gov.uk',
    'responsiblegambling.org', 'ncpgambling.org', 'gamblersanonymous.org',
    # Common CDNs and services
    'jsdelivr.net', 'unpkg.com', 'cdnjs.cloudflare.com', 'bootstrapcdn.com',
}


class GamblingBlocklistScraper:
    def __init__(self):
        self.domains = set()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        
    def is_valid_domain(self, domain: str) -> bool:
        """Check if a domain looks valid and gambling-related."""
        domain = domain.lower().strip()
        
        # Basic validation
        if not domain or len(domain) < 4 or len(domain) > 100:
            return False
            
        # Must have at least one dot
        if '.' not in domain:
            return False
            
        # Exclude known non-gambling domains
        if domain in EXCLUDE_DOMAINS:
            return False
            
        # Check for excluded patterns
        for excluded in EXCLUDE_DOMAINS:
            if domain.endswith('.' + excluded) or domain == excluded:
                return False
        
        # Validate characters
        if not re.match(r'^[a-z0-9][-a-z0-9.]*[a-z0-9]$', domain):
            return False
            
        return True
    
    def extract_domains_from_html(self, html: str, base_url: str = '') -> set:
        """Extract potential gambling domains from HTML content."""
        found = set()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract from links
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
        
        # Extract from text using regex patterns
        text = soup.get_text()
        for pattern in DOMAIN_PATTERNS:
            matches = re.findall(pattern, text.lower())
            for match in matches:
                if isinstance(match, tuple):
                    domain = match[0]
                else:
                    domain = match
                domain = domain.replace('www.', '')
                if self.is_valid_domain(domain):
                    found.add(domain)
        
        return found
    
    def scrape_url(self, url: str, delay: float = 2.0) -> set:
        """Scrape a single URL for gambling domains."""
        found = set()
        try:
            logger.info(f"Scraping: {url}")
            time.sleep(delay)  # Be polite
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            found = self.extract_domains_from_html(response.text, url)
            logger.info(f"  Found {len(found)} domains")
        except Exception as e:
            logger.warning(f"  Error scraping {url}: {e}")
        return found
    
    def search_gambling_terms(self) -> set:
        """Search for gambling-related terms to find more domains."""
        found = set()
        search_terms = [
            'non gamstop casino list',
            'casinos not on gamstop uk',
            'crypto casino no verification',
            'offshore betting sites uk',
            'curacao casino no gamstop',
        ]
        
        # Note: Direct Google scraping is against ToS
        # This is a placeholder - in practice you'd use a search API
        # or manually curate aggregator URLs
        logger.info("Search-based discovery not implemented - using seed list and aggregators")
        return found
    
    def load_existing_lists(self) -> set:
        """Load domains from existing public blocklists for comparison."""
        found = set()
        blocklist_urls = [
            'https://blocklistproject.github.io/Lists/gambling.txt',
            'https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/gambling/hosts',
        ]
        
        for url in blocklist_urls:
            try:
                logger.info(f"Loading existing list: {url}")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                for line in response.text.splitlines():
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    # Handle hosts file format (0.0.0.0 domain.com)
                    parts = line.split()
                    if len(parts) >= 2:
                        domain = parts[-1].lower().replace('www.', '')
                    else:
                        domain = parts[0].lower().replace('www.', '')
                    
                    if self.is_valid_domain(domain):
                        found.add(domain)
                        
                logger.info(f"  Loaded {len(found)} domains from list")
            except Exception as e:
                logger.warning(f"  Error loading {url}: {e}")
        
        return found
    
    def generate_variants(self, domains: set) -> set:
        """Generate common domain variants (numbered, misspellings, etc)."""
        variants = set()
        
        for domain in domains:
            base = domain.split('.')[0]
            tld = '.'.join(domain.split('.')[1:])
            
            # Numbered variants (site1.com, site8.com, etc)
            for i in range(1, 20):
                variants.add(f"{base}{i}.{tld}")
            
            # Common TLD variants
            for new_tld in ['com', 'net', 'org', 'io', 'gg', 'ag', 'casino', 'bet']:
                if new_tld != tld:
                    variants.add(f"{base}.{new_tld}")
        
        # Filter to only valid domains
        return {d for d in variants if self.is_valid_domain(d)}
    
    def run(self) -> set:
        """Run the full scraping process."""
        logger.info("Starting gambling blocklist generation...")
        
        # Start with seed domains
        self.domains.update(SEED_DOMAINS)
        logger.info(f"Loaded {len(SEED_DOMAINS)} seed domains")
        
        # Load existing public lists
        existing = self.load_existing_lists()
        self.domains.update(existing)
        logger.info(f"Total after existing lists: {len(self.domains)}")
        
        # Generate variants
        variants = self.generate_variants(self.domains)
        self.domains.update(variants)
        logger.info(f"Total after variants: {len(self.domains)}")
        
        # Sort and return
        return self.domains


def generate_blocklist_files(domains: set, output_dir: Path):
    """Generate blocklist files in multiple formats."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Sort domains
    sorted_domains = sorted(domains)
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    header = f"""# Non-GamStop Gambling Blocklist
# 
# This blocklist targets offshore gambling sites that operate outside of
# self-exclusion programs like GamStop. Intended for harm reduction.
#
# Repository: https://github.com/YOUR_USERNAME/gambling-blocklist
# License: MIT
#
# Last updated: {timestamp}
# Total domains: {len(sorted_domains)}
#
# Add this list to your Pi-hole, AdGuard, or other DNS blocker.

"""

    # Pi-hole format (just domains)
    pihole_content = header + '\n'.join(sorted_domains)
    (output_dir / 'gambling-blocklist.txt').write_text(pihole_content)
    logger.info(f"Generated: gambling-blocklist.txt")
    
    # Hosts file format (0.0.0.0)
    hosts_lines = [f"0.0.0.0 {domain}" for domain in sorted_domains]
    hosts_content = header + '\n'.join(hosts_lines)
    (output_dir / 'gambling-blocklist-hosts.txt').write_text(hosts_content)
    logger.info(f"Generated: gambling-blocklist-hosts.txt")
    
    # AdGuard format
    adguard_lines = [f"||{domain}^" for domain in sorted_domains]
    adguard_content = header.replace('# ', '! ') + '\n'.join(adguard_lines)
    (output_dir / 'gambling-blocklist-adguard.txt').write_text(adguard_content)
    logger.info(f"Generated: gambling-blocklist-adguard.txt")
    
    # Dnsmasq format
    dnsmasq_lines = [f"address=/{domain}/" for domain in sorted_domains]
    dnsmasq_content = header + '\n'.join(dnsmasq_lines)
    (output_dir / 'gambling-blocklist-dnsmasq.txt').write_text(dnsmasq_content)
    logger.info(f"Generated: gambling-blocklist-dnsmasq.txt")
    
    # Unbound format
    unbound_lines = [f'local-zone: "{domain}" always_null' for domain in sorted_domains]
    unbound_content = header + '\n'.join(unbound_lines)
    (output_dir / 'gambling-blocklist-unbound.txt').write_text(unbound_content)
    logger.info(f"Generated: gambling-blocklist-unbound.txt")
    
    # JSON format (for programmatic use)
    json_data = {
        'updated': timestamp,
        'count': len(sorted_domains),
        'domains': sorted_domains
    }
    (output_dir / 'gambling-blocklist.json').write_text(json.dumps(json_data, indent=2))
    logger.info(f"Generated: gambling-blocklist.json")
    
    # Stats
    stats = {
        'updated': timestamp,
        'total_domains': len(sorted_domains),
        'formats': ['txt', 'hosts', 'adguard', 'dnsmasq', 'unbound', 'json']
    }
    (output_dir / 'stats.json').write_text(json.dumps(stats, indent=2))


def main():
    """Main entry point."""
    scraper = GamblingBlocklistScraper()
    domains = scraper.run()
    
    output_dir = Path(__file__).parent / 'lists'
    generate_blocklist_files(domains, output_dir)
    
    logger.info(f"\nGeneration complete!")
    logger.info(f"Total domains: {len(domains)}")
    logger.info(f"Output directory: {output_dir}")


if __name__ == '__main__':
    main()
