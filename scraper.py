#!/usr/bin/env python3
"""
Non-GamStop Casino Blocklist Scraper

Uses Playwright to scrape aggregator sites, clicking through "Play Now" 
redirect links to discover the actual casino domains.
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

# Button text patterns to look for (case insensitive)
BUTTON_PATTERNS = [
    'play now', 'play here', 'visit', 'visit casino', 'visit site',
    'claim bonus', 'claim now', 'get bonus', 'grab bonus',
    'sign up', 'register', 'join now', 'start playing',
    'go to casino', 'go to site', 'open casino',
]

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
    
    def extract_domain_from_url(self, url: str) -> str:
        """Extract and clean domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace('www.', '')
            return domain
        except Exception:
            return ''
    
    def find_redirect_links(self, page) -> list:
        """Find all links that look like casino redirect links."""
        redirect_links = []
        
        try:
            # Get all links on the page
            links = page.query_selector_all('a[href]')
            
            for link in links:
                try:
                    href = link.get_attribute('href') or ''
                    text = (link.inner_text() or '').lower().strip()
                    
                    # Check if button text matches our patterns
                    is_button = any(pattern in text for pattern in BUTTON_PATTERNS)
                    
                    # Check if href looks like a redirect link (contains /visit/, /go/, /out/, etc.)
                    is_redirect_url = any(x in href.lower() for x in ['/visit/', '/go/', '/out/', '/redirect/', '/link/', '/click/', '/track/'])
                    
                    if is_button or is_redirect_url:
                        # Get absolute URL
                        if href.startswith('/'):
                            base_url = page.url
                            parsed = urlparse(base_url)
                            href = f"{parsed.scheme}://{parsed.netloc}{href}"
                        
                        if href.startswith('http'):
                            redirect_links.append(href)
                            
                except Exception:
                    continue
                    
        except Exception as e:
            logger.warning(f"Error finding redirect links: {e}")
        
        return list(set(redirect_links))  # Dedupe
    
    def follow_redirect(self, context, url: str, timeout: int = 15000) -> str:
        """Follow a redirect link and return the final destination domain."""
        page = None
        try:
            page = context.new_page()
            
            # Navigate and wait for redirects to complete
            response = page.goto(url, timeout=timeout, wait_until='domcontentloaded')
            
            # Give it a moment for JS redirects
            time.sleep(1)
            
            # Get final URL after all redirects
            final_url = page.url
            domain = self.extract_domain_from_url(final_url)
            
            return domain
            
        except PlaywrightTimeout:
            # Timeout might mean we hit the casino site (which might block us)
            # Try to get whatever URL we landed on
            if page:
                try:
                    domain = self.extract_domain_from_url(page.url)
                    return domain
                except Exception:
                    pass
            return ''
        except Exception as e:
            logger.debug(f"Error following redirect {url}: {e}")
            return ''
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass
    
    def scrape_aggregator(self, context, page, url: str) -> set:
        """Scrape a single aggregator URL."""
        found = set()
        
        try:
            logger.info(f"Scraping: {url}")
            
            # Navigate to the page
            page.goto(url, timeout=60000, wait_until='domcontentloaded')
            time.sleep(random.uniform(2, 4))
            
            # Scroll to load lazy content
            page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
            time.sleep(1)
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(1)
            
            # Find redirect links
            redirect_links = self.find_redirect_links(page)
            logger.info(f"  Found {len(redirect_links)} redirect links to follow")
            
            # Follow each redirect link (limit to avoid taking too long)
            max_links = 50  # Reasonable limit per page
            for i, link in enumerate(redirect_links[:max_links]):
                domain = self.follow_redirect(context, link)
                
                if domain and self.is_valid_domain(domain):
                    if self.looks_like_casino(domain):
                        found.add(domain)
                        logger.info(f"    Discovered: {domain}")
                    else:
                        # Still might be a casino even without keywords
                        # Add it if it's not obviously something else
                        if not any(x in domain for x in ['google', 'facebook', 'twitter', 'amazon']):
                            found.add(domain)
                            logger.info(f"    Discovered (no keyword match): {domain}")
                
                # Small delay between redirects
                time.sleep(random.uniform(0.5, 1.5))
            
            logger.info(f"  Total domains from this page: {len(found)}")
            
        except PlaywrightTimeout:
            logger.warning(f"  Timeout loading {url}")
        except Exception as e:
            logger.warning(f"  Error scraping {url}: {e}")
        
        return found
    
    def scrape_with_browser(self) -> set:
        """Scrape all aggregator URLs using Playwright."""
        all_found = set()
        
        with sync_playwright() as p:
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
            
            # Main page for navigation
            page = context.new_page()
            
            for url in AGGREGATOR_URLS:
                # Random delay between sites
                time.sleep(random.uniform(3, 6))
                
                found = self.scrape_aggregator(context, page, url)
                all_found.update(found)
            
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
