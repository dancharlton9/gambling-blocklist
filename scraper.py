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
    'briangriff.com',
}

# Button text patterns
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
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace('www.', '')
            return domain
        except Exception:
            return ''
    
    def scrape_aggregator(self, browser, url: str) -> set:
        """Scrape a single aggregator URL - creates fresh context each time."""
        found = set()
        context = None
        
        try:
            logger.info(f"Scraping: {url}")
            
            # Create fresh context for each aggregator
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-GB',
                timezone_id='Europe/London',
            )
            
            page = context.new_page()
            
            # Navigate to the page
            page.goto(url, timeout=60000, wait_until='domcontentloaded')
            time.sleep(random.uniform(2, 4))
            
            # Log where we ended up
            final_url = page.url
            if final_url != url:
                logger.info(f"  Redirected to: {final_url}")
            
            # Scroll to load lazy content
            for scroll_pos in [0.33, 0.66, 1.0, 0]:
                try:
                    page.evaluate(f'window.scrollTo(0, document.body.scrollHeight * {scroll_pos})')
                    time.sleep(0.5)
                except Exception:
                    pass
            
            # Find all clickable elements with matching text
            elements_info = page.evaluate('''() => {
                const patterns = ['play now', 'play here', 'visit', 'visit casino', 'visit site',
                    'claim bonus', 'claim now', 'get bonus', 'grab bonus', 'sign up', 
                    'register', 'join now', 'start playing', 'go to casino', 'play'];
                
                const results = [];
                const selectors = ['a', 'button', '[role="button"]', '[onclick]'];
                
                selectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach((el, index) => {
                        const text = (el.innerText || '').toLowerCase().trim();
                        const matches = patterns.some(p => text.includes(p));
                        if (matches && el.offsetParent !== null) {  // visible check
                            results.push({
                                selector: selector,
                                index: index,
                                text: text.substring(0, 50),
                                href: el.href || el.getAttribute('href') || ''
                            });
                        }
                    });
                });
                
                return results;
            }''')
            
            logger.info(f"  Found {len(elements_info)} clickable buttons")
            
            # Click each element
            clicked = 0
            max_clicks = 30
            
            for info in elements_info[:max_clicks]:
                try:
                    # Get current page count
                    pages_before = len(context.pages)
                    original_url = page.url
                    original_domain = self.extract_domain_from_url(original_url)
                    
                    # Find and click the element
                    selector = f"{info['selector']}:has-text(\"{info['text'][:20]}\")"
                    try:
                        element = page.query_selector(selector)
                        if element and element.is_visible():
                            element.click(timeout=3000)
                        else:
                            continue
                    except Exception:
                        continue
                    
                    # Wait for navigation/popup
                    time.sleep(2)
                    
                    # Check for new tabs
                    pages_after = context.pages
                    if len(pages_after) > pages_before:
                        # New tab opened
                        new_page = pages_after[-1]
                        try:
                            new_page.wait_for_load_state('domcontentloaded', timeout=5000)
                            domain = self.extract_domain_from_url(new_page.url)
                            new_page.close()
                        except Exception:
                            domain = self.extract_domain_from_url(new_page.url)
                            try:
                                new_page.close()
                            except Exception:
                                pass
                    else:
                        # Check if current page navigated
                        current_domain = self.extract_domain_from_url(page.url)
                        if current_domain != original_domain:
                            domain = current_domain
                            # Navigate back
                            try:
                                page.goto(final_url, timeout=30000, wait_until='domcontentloaded')
                                time.sleep(1)
                            except Exception:
                                pass
                        else:
                            domain = ''
                    
                    if domain and self.is_valid_domain(domain):
                        found.add(domain)
                        logger.info(f"    Discovered: {domain}")
                        clicked += 1
                    
                    time.sleep(random.uniform(0.3, 1.0))
                    
                except Exception as e:
                    logger.debug(f"  Error clicking: {e}")
                    continue
            
            logger.info(f"  Total domains from this page: {len(found)}")
            
        except PlaywrightTimeout:
            logger.warning(f"  Timeout loading {url}")
        except Exception as e:
            logger.warning(f"  Error scraping {url}: {e}")
        finally:
            # Always close context
            if context:
                try:
                    context.close()
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
            
            for url in AGGREGATOR_URLS:
                time.sleep(random.uniform(2, 4))
                
                try:
                    found = self.scrape_aggregator(browser, url)
                    all_found.update(found)
                except Exception as e:
                    logger.warning(f"Failed to scrape {url}: {e}")
                    continue
            
            browser.close()
        
        return all_found
    
    def load_manual_domains(self) -> set:
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
        logger.info("Starting non-GamStop casino scraper...")
        
        self.domains.update(self.load_manual_domains())
        
        scraped = self.scrape_with_browser()
        self.domains.update(scraped)
        logger.info(f"Total unique domains: {len(self.domains)}")
        
        variants = self.generate_variants(self.domains)
        self.domains.update(variants)
        logger.info(f"Total after variants (1-9): {len(self.domains)}")
        
        return self.domains


def generate_blocklist_files(domains: set, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    sorted_domains = sorted(domains)
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    header = f"""# Non-GamStop Gambling Blocklist
#
# Offshore casinos that circumvent GamStop self-exclusion.
# Use alongside standard gambling blocklists for comprehensive coverage.
#
# Repository: https://github.com/dancharlton9/gambling-blocklist
# Last updated: {timestamp}
# Total domains: {len(sorted_domains)}

"""

    (output_dir / 'blocklist.txt').write_text(header + '\n'.join(sorted_domains))
    
    hosts_lines = [f"0.0.0.0 {d}" for d in sorted_domains]
    (output_dir / 'blocklist-hosts.txt').write_text(header + '\n'.join(hosts_lines))
    
    adguard_lines = [f"||{d}^" for d in sorted_domains]
    (output_dir / 'blocklist-adguard.txt').write_text(header.replace('# ', '! ') + '\n'.join(adguard_lines))
    
    (output_dir / 'blocklist.json').write_text(
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
