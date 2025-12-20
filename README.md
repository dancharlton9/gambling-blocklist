# Non-GamStop Casino Blocklist

A focused blocklist of offshore casinos that circumvent [GamStop](https://www.gamstop.co.uk/) self-exclusion. Designed to complement existing gambling blocklists.

## Usage

### Pi-hole
```
https://raw.githubusercontent.com/dancharlton9/gamblng-blocklist/main/lists/gamblng-blocklist.txt
```

### AdGuard Home
```
https://raw.githubusercontent.com/dancharlton9/gamblng-blocklist/main/lists/gamblng-blocklist-adguard.txt
```

### Hosts file
```
https://raw.githubusercontent.com/dancharlton9/gamblng-blocklist/main/lists/gamblng-blocklist-hosts.txt
```

## How It Works

The scraper visits aggregator sites that advertise non-GamStop casinos and extracts the casino domains they promote. It then generates numbered variants (1-9) to catch common domain patterns like `gambiva8.com`.

Updates run daily via GitHub Actions.

## Adding Domains

Add domains to `domains/manual.txt` (one per line) and they'll be included in the next update.

## Combine With

For comprehensive gambling blocking, use alongside:
- [BlockListProject Gambling](https://blocklistproject.github.io/Lists/gambling.txt)
- [StevenBlack Gambling](https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/gambling/hosts)
- [Sefinek Gambling](https://blocklist.sefinek.net/generated/v1/0.0.0.0/block/gambling.txt)

## Support

- 🇬🇧 [GamStop](https://www.gamstop.co.uk/) — UK self-exclusion
- 🇬🇧 [GamCare](https://www.gamcare.org.uk/) — 0808 8020 133
- 🇬🇧 [BeGambleAware](https://www.begambleaware.org/)

## License

MIT
