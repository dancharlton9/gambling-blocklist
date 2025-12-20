#!/usr/bin/env python3
"""
Non-GamStop Casino Blocklist Scraper

Uses Playwright (headless browser) to scrape aggregator sites that advertise
non-GamStop casinos. This bypasses Cloudflare and similar bot protection.
"""

import re
import random
import time
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
import json
import logging

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Aggregator sites that list non-GamStop casinos
AGGREGATOR_URLS = [
    'https://www.pieria.co.uk/',
    'https://www.vso.org.uk/',
    'https://egamersworld.com/blog/reputable-casinos-not-on-gamstop-uk-in-2024-update-McFPNE3aV',
    'https://esportsinsider.com/uk/gambling/non-gamstop-casinos',
    'https://www.thebigfixup.us.org/',
    'https://www.wizardexploratorium.uk.com/',
    'https://peopletree.eu/',
    'https://www.yorkshire-bridge.gr.com/',
    'https://inlandhome.us.org/',
    'https://www.onlinecasinosnotongamstop.uk.net/',
]

# Domains to exclude
EXCLUDE_DOMAINS = {
    # Common sites
    'google.com', 'facebook.com', 'twitter.com', 'youtube.com', 'instagram.com',
    'linkedin.com', 'reddit.com', 'wikipedia.org', 'amazon.com', 't.co', 'x.com',
    'pinterest.com', 'tiktok.com', 'whatsapp.com', 'telegram.org',
    # Responsible gambling
    'gamstop.co.uk', 'begambleaware.org', 'gamcare.org.uk', 'gamblingcommission.gov.uk',
    'responsiblegambling.org', 'ncpgambling.org', 'gamblersanonymous.org',
    # Tech/CDN
    'cloudflare.com', 'jsdelivr.net', 'googleapis.com', 'gstatic.com',
    'w3.org', 'schema.org', 'trustpilot.com', 'cloudflare-dns.com',
    'jquery.com', 'bootstrapcdn.com', 'fontawesome.com', 'fonts.google.com',
    # Aggregators (we scrape them, don't block)
    'pieria.co.uk', 'vso.org.uk', 'egamersworld.com', 'esportsinsider.com',
    'thebigfixup.us.org', 'wizardexploratorium.uk.com', 'peopletree.eu',
    'yorkshire-bridge.gr.com', 'inlandhome.us.org', 'onlinecasinosnotongamstop.uk.net',
    'nongamstopcasinos.net', 'casinonotongamstop.com', 'casinosnotongamstop.org',
}

# Gambling TLDs and keywords
GAMBLING_TLDS = {'.casino', '.bet', '.games', '.game', '.io', '.ag', '.gg', '.vip', '.win', '.fun'}
GAMBLING_KEYWORDS = ['casino', 'bet', 'slots', 'poker', 'spin', 'vegas', 'lucky', 'jackpot', 'win', 'game', 'play', 'wager', 'stake', 'roulette', 'bingo']


class NonGamstopScraper:
    def __init__(self):
        self.domains = set()
    
    def is_valid_domain(self, domain: str) -> bool:
        domain = domain.lower().strip()
        if not domain or len(domain) < 4 or len(domain) > 100:
            return False
        if '.' not in domain:
            return False
        if not re.match(r'^[a-z0-9][-a-z0-9.]*[a-z0-9]$', domain):
            return False
        for excluded in EXCLUDE_DOMAINS:
            if domain == excluded or domain.endswith('.' + excluded):
                return False
        return True
    
    def looks_like_casino(self, domain: str) -> bool:
        domain_lower = domain.lower()
        for tld in GAMBLING_TLDS:
            if domain_lower.endswith(tld):
                return True
        for keyword in GAMBLING_KEYWORDS:
            if keyword in domain_lower:
                return True
        return False
    
    def extract_domains_from_page(self, page) -> set:
        """Extract domains from all links on the page."""
        found = set()
        try:
            links = page.query_selector_all('a[href]')
            for link in links:
                href = link.get_attribute('href')
                if href and href.startswith(('http://', 'https://')):
                    try:
                        parsed = urlparse(href)
                        domain = parsed.netloc.lower().replace('www.', '')
                        if self.is_valid_domain(domain) and self.looks_like_casino(domain):
                            found.add(domain)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Error extracting links: {e}")
        return found
    
    def scrape_with_browser(self) -> set:
        """Scrape all aggregator URLs using Playwright."""
        all_found = set()
        
        with sync_playwright() as p:
            # Launch browser with realistic settings
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-GB',
                timezone_id='Europe/London',
            )
            
            page = context.new_page()
            
            for url in AGGREGATOR_URLS:
                try:
                    logger.info(f"Scraping: {url}")
                    
                    # Random delay to seem more human
                    time.sleep(random.uniform(2, 5))
                    
                    # Navigate with longer timeout for slow sites
                    page.goto(url, timeout=60000, wait_until='domcontentloaded')
                    
                    # Wait a bit for JS to render
                    time.sleep(random.uniform(1, 3))
                    
                    # Scroll down to trigger lazy loading
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
                    time.sleep(1)
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    time.sleep(1)
                    
                    # Extract domains
                    found = self.extract_domains_from_page(page)
                    all_found.update(found)
                    logger.info(f"  Found {len(found)} casino domains")
                    
                except PlaywrightTimeout:
                    logger.warning(f"  Timeout loading {url}")
                except Exception as e:
                    logger.warning(f"  Error scraping {url}: {e}")
            
            browser.close()
        
        return all_found
    
    def load_manual_domains(self) -> set:
        """Load manually added domains."""
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
        """Generate numbered variants (1-9) for discovered domains."""
        variants = set()
        for domain in domains:
            parts = domain.split('.')
            if len(parts) >= 2:
                base = parts[0]
                tld = '.'.join(parts[1:])
                if not base[-1].isdigit():
                    for i in range(1, 10):
                        variants.add(f"{base}{i}.{tld}")
        return {d for d in variants if self.is_valid_domain(d)}
    
    def run(self) -> set:
        """Run the scraper."""
        logger.info("Starting non-GamStop casino scraper...")
        
        # Load manual domains
        self.domains.update(self.load_manual_domains())
        
        # Scrape aggregators with browser
        scraped = self.scrape_with_browser()
        self.domains.update(scraped)
        logger.info(f"Total unique domains: {len(self.domains)}")
        
        # Generate variants
        variants = self.generate_variants(self.domains)
        self.domains.update(variants)
        logger.info(f"Total after variants (1-9): {len(self.domains)}")
        
        return self.domains


def generate_blocklist_files(domains: set, output_dir: Path):
    """Generate blocklist files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    sorted_domains = sorted(domains)
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    header = f"""# Non-GamStop Casino Blocklist
#
# Offshore casinos that circumvent GamStop self-exclusion.
# Use alongside standard gambling blocklists for comprehensive coverage.
#
# Last updated: {timestamp}
# Total domains: {len(sorted_domains)}

"""

    # Pi-hole format
    (output_dir / 'non-gamstop-blocklist.txt').write_text(
        header + '\n'.join(sorted_domains)
    )
    
    # Hosts format
    hosts_lines = [f"0.0.0.0 {d}" for d in sorted_domains]
    (output_dir / 'non-gamstop-blocklist-hosts.txt').write_text(
        header + '\n'.join(hosts_lines)
    )
    
    # AdGuard format
    adguard_lines = [f"||{d}^" for d in sorted_domains]
    (output_dir / 'non-gamstop-blocklist-adguard.txt').write_text(
        header.replace('# ', '! ') + '\n'.join(adguard_lines)
    )
    
    # JSON
    (output_dir / 'non-gamstop-blocklist.json').write_text(
        json.dumps({'updated': timestamp, 'count': len(sorted_domains), 'domains': sorted_domains}, indent=2)
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
