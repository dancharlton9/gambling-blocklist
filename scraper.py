#!/usr/bin/env python3
"""
Non-GamStop Casino Blocklist Scraper

Uses Playwright to scrape aggregator sites, clicking "Play Now" buttons
and capturing the destination URLs to discover casino domains.
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
    'briangriff.com',  # Another aggregator
}

# Button text patterns to look for (case insensitive)
BUTTON_PATTERNS = [
    'play now', 'play here', 'visit', 'visit casino', 'visit site',
    'claim bonus', 'claim now', 'get bonus', 'grab bonus',
    'sign up', 'register', 'join now', 'start playing',
    'go to casino', 'go to site', 'open casino', 'play',
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
    
    def is_aggregator_domain(self, domain: str) -> bool:
        """Check if domain belongs to an aggregator site."""
        aggregator_domains = set()
        for url in AGGREGATOR_URLS:
            d = self.extract_domain_from_url(url)
            if d:
                aggregator_domains.add(d)
        
        # Also add known aggregator redirects
        aggregator_domains.add('briangriff.com')
        
        return domain in aggregator_domains or any(domain.endswith('.' + d) for d in aggregator_domains)
    
    def find_clickable_elements(self, page) -> list:
        """Find all clickable elements that look like casino links."""
        elements = []
        
        # CSS selectors for clickable elements
        selectors = [
            'a',                          # Regular links
            'button',                     # Buttons
            '[role="button"]',            # Elements with button role
            '[onclick]',                  # Elements with onclick handlers
            '.btn', '.button',            # Common button classes
            '[class*="play"]',            # Classes containing "play"
            '[class*="visit"]',           # Classes containing "visit"
            '[class*="bonus"]',           # Classes containing "bonus"
        ]
        
        for selector in selectors:
            try:
                found = page.query_selector_all(selector)
                for el in found:
                    try:
                        text = (el.inner_text() or '').lower().strip()
                        
                        # Check if text matches our button patterns
                        if any(pattern in text for pattern in BUTTON_PATTERNS):
                            # Check if element is visible
                            if el.is_visible():
                                elements.append(el)
                    except Exception:
                        continue
            except Exception:
                continue
        
        return elements
    
    def click_and_capture(self, context, page, element) -> str:
        """Click an element and capture the destination URL."""
        try:
            # Store current page URL
            original_url = page.url
            original_domain = self.extract_domain_from_url(original_url)
            
            # Set up listener for new pages (popups/new tabs)
            new_page_url = None
            
            def handle_popup(popup):
                nonlocal new_page_url
                try:
                    popup.wait_for_load_state('domcontentloaded', timeout=10000)
                    new_page_url = popup.url
                    popup.close()
                except Exception:
                    pass
            
            context.on('page', handle_popup)
            
            # Click the element
            try:
                element.click(timeout=5000)
            except Exception:
                # Try JavaScript click as fallback
                try:
                    element.evaluate('el => el.click()')
                except Exception:
                    return ''
            
            # Wait a moment for navigation
            time.sleep(2)
            
            # Check if we got a new page (popup)
            if new_page_url:
                domain = self.extract_domain_from_url(new_page_url)
                # Navigate back to original page
                try:
                    page.goto(original_url, timeout=30000, wait_until='domcontentloaded')
                except Exception:
                    pass
                return domain
            
            # Check if current page navigated
            current_url = page.url
            current_domain = self.extract_domain_from_url(current_url)
            
            if current_domain != original_domain and not self.is_aggregator_domain(current_domain):
                # We navigated to a new domain
                domain = current_domain
                # Navigate back
                try:
                    page.goto(original_url, timeout=30000, wait_until='domcontentloaded')
                    time.sleep(1)
                except Exception:
                    pass
                return domain
            
            return ''
            
        except Exception as e:
            logger.debug(f"Error clicking element: {e}")
            return ''
    
    def scrape_aggregator(self, context, url: str) -> set:
        """Scrape a single aggregator URL by clicking buttons."""
        found = set()
        page = None
        
        try:
            logger.info(f"Scraping: {url}")
            
            page = context.new_page()
            
            # Navigate to the page (handle redirects)
            page.goto(url, timeout=60000, wait_until='domcontentloaded')
            time.sleep(random.uniform(2, 4))
            
            # Log where we ended up (in case of redirect)
            final_url = page.url
            if final_url != url:
                logger.info(f"  Redirected to: {final_url}")
            
            # Scroll to load lazy content
            page.evaluate('window.scrollTo(0, document.body.scrollHeight / 3)')
            time.sleep(1)
            page.evaluate('window.scrollTo(0, document.body.scrollHeight * 2 / 3)')
            time.sleep(1)
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(1)
            page.evaluate('window.scrollTo(0, 0)')  # Back to top
            time.sleep(1)
            
            # Find clickable elements
            elements = self.find_clickable_elements(page)
            logger.info(f"  Found {len(elements)} clickable 'Play Now' type buttons")
            
            # Click each element and capture destination
            clicked = 0
            max_clicks = 30  # Limit to avoid taking too long
            
            for element in elements:
                if clicked >= max_clicks:
                    break
                
                try:
                    domain = self.click_and_capture(context, page, element)
                    
                    if domain and self.is_valid_domain(domain):
                        found.add(domain)
                        logger.info(f"    Discovered: {domain}")
                        clicked += 1
                    
                    time.sleep(random.uniform(0.5, 1.5))
                    
                except Exception as e:
                    logger.debug(f"  Error with element: {e}")
                    continue
                
                # Re-find elements as page state may have changed
                try:
                    elements = self.find_clickable_elements(page)
                except Exception:
                    break
            
            logger.info(f"  Total domains from this page: {len(found)}")
            
        except PlaywrightTimeout:
            logger.warning(f"  Timeout loading {url}")
        except Exception as e:
            logger.warning(f"  Error scraping {url}: {e}")
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass
        
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
            
            for url in AGGREGATOR_URLS:
                # Random delay between sites
                time.sleep(random.uniform(3, 6))
                
                found = self.scrape_aggregator(context, url)
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
