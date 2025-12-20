# Non-GamStop Gambling Blocklist

A regularly updated blocklist targeting offshore gambling sites that operate outside of self-exclusion programs like [GamStop](https://www.gamstop.co.uk/).

**This project is intended for harm reduction** — helping people maintain their self-exclusion by blocking access to sites specifically designed to circumvent responsible gambling protections.

## Quick Start

### Pi-hole

Add one of these URLs to your Pi-hole adlists:

```
https://raw.githubusercontent.com/dancharlton9/gambling-blocklist/main/lists/gambling-blocklist.txt
```

Or for hosts file format:
```
https://raw.githubusercontent.com/dancharlton9/gambling-blocklist/main/lists/gambling-blocklist-hosts.txt
```

Then update gravity:
```bash
pihole -g
```

### AdGuard Home

Add this URL to your blocklists:
```
https://raw.githubusercontent.com/dancharlton9/gambling-blocklist/main/lists/gambling-blocklist-adguard.txt
```

### Unbound

Download and include in your Unbound configuration:
```
https://raw.githubusercontent.com/dancharlton9/gambling-blocklist/main/lists/gambling-blocklist-unbound.txt
```

### dnsmasq

Download and include in your dnsmasq configuration:
```
https://raw.githubusercontent.com/dancharlton9/gambling-blocklist/main/lists/gambling-blocklist-dnsmasq.txt
```

## Available Formats

| Format | File | Description |
|--------|------|-------------|
| Plain domains | `gambling-blocklist.txt` | One domain per line, compatible with Pi-hole |
| Hosts file | `gambling-blocklist-hosts.txt` | `0.0.0.0 domain.com` format |
| AdGuard | `gambling-blocklist-adguard.txt` | `\|\|domain.com^` format |
| dnsmasq | `gambling-blocklist-dnsmasq.txt` | `address=/domain.com/` format |
| Unbound | `gambling-blocklist-unbound.txt` | `local-zone: "domain" always_null` format |
| JSON | `gambling-blocklist.json` | Programmatic access with metadata |

## What's Blocked

This list focuses on:

- **Non-GamStop casinos** — Offshore sites (typically Curaçao licensed) that don't participate in UK self-exclusion
- **Crypto casinos** — Bitcoin/cryptocurrency gambling sites with minimal verification
- **Offshore sportsbooks** — Betting sites operating outside UKGC regulation
- **Casino aggregators** — Sites that promote non-GamStop gambling

## What's NOT Blocked

- Legitimate UK-licensed gambling sites (these participate in GamStop)
- Responsible gambling support sites (GamStop, GamCare, BeGambleAware, etc.)
- General gaming sites that aren't gambling-related

## Update Schedule

Lists are automatically updated daily at 06:00 UTC via GitHub Actions.

## Adding Domains

Found a site that should be blocked? You can:

1. **Open an issue** with the domain name
2. **Submit a PR** adding the domain to `domains/manual.txt`
3. **Fork the repo** and maintain your own additions

### Manual Domain List

Create a `domains/manual.txt` file with one domain per line to add your own entries:

```
example-casino.com
another-betting-site.io
```

## Regex Patterns for Pi-hole

For more aggressive blocking, add these regex patterns to Pi-hole:

```regex
# Catch numbered domain variants (gambiva8.com, etc)
^[a-z]+[0-9]+\.(com|net|io|casino|bet)$

# Common gambling keywords with numbers
^(.+[-.])?bet[0-9]{2,}\.
^(.+[-.])?casino[0-9]+\.
^(.+[-.])?slots?[0-9]+\.

# Crypto casino patterns
^(.+[-.])?crypto[-]?casino[0-9]*\.
^(.+[-.])?btc[-]?casino[0-9]*\.
^(.+[-.])?bitcoin[-]?casino[0-9]*\.
```

## Local Development

```bash
# Clone the repo
git clone https://github.com/dancharlton9/gambling-blocklist.git
cd gambling-blocklist

# Install dependencies
pip install -r requirements.txt

# Run the scraper
python scraper.py

# Lists are generated in ./lists/
```

## Combining with Other Lists

For comprehensive coverage, combine this list with:

- [The Block List Project - Gambling](https://blocklistproject.github.io/Lists/gambling.txt)
- [StevenBlack hosts - Gambling](https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/gambling/hosts)
- [Sefinek Blocklists - Gambling](https://blocklist.sefinek.net/generated/v1/0.0.0.0/block/gambling.txt)

## Support Resources

If you or someone you know is struggling with gambling:

- 🇬🇧 **GamStop** (UK self-exclusion): [gamstop.co.uk](https://www.gamstop.co.uk/)
- 🇬🇧 **GamCare**: [gamcare.org.uk](https://www.gamcare.org.uk/) — 0808 8020 133
- 🇬🇧 **BeGambleAware**: [begambleaware.org](https://www.begambleaware.org/)
- 🇺🇸 **National Council on Problem Gambling**: [ncpgambling.org](https://www.ncpgambling.org/) — 1-800-522-4700
- 🌍 **Gamblers Anonymous**: [gamblersanonymous.org](https://www.gamblersanonymous.org/)

## License

MIT License — See [LICENSE](LICENSE) for details.

## Disclaimer

This blocklist is provided as-is for harm reduction purposes. It may not catch all gambling sites, and some sites may be incorrectly included. Always verify domains before reporting false positives.

The maintainers are not affiliated with any gambling sites, regulators, or support organisations.
