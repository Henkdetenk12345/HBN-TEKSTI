# HBN-Teksti-TV

A Python-based teletext news generator that fetches RSS feeds from Yle (Finnish Broadcasting Company) and converts them into teletext format pages. This system creates a complete teletext news service with multiple categories, weather information, and an automated newsreel.

## Features

- **Automated News Conversion**: Fetches and converts RSS feeds from Yle into teletext pages
- **Multiple News Categories**:
  - Main News (Pääuutiset) - Pages 101-112
  - Latest News (Tuoreimmat) - Pages 111-122
  - Sports (Urheilu) - Pages 301-306
  - Football (Jalkapallo) - Pages 308-313
- **Weather Map**: Live weather data for Finnish cities (Page 166)
- **Newsreel**: Comprehensive rotating newsreel combining all categories (Page 185)
- **Finnish Localization**: Full support for Finnish date/time formatting and special characters

## Requirements

```
feedparser
beautifulsoup4
lxml
requests
selenium
```

## Installation

1. Clone this repository
2. Install dependencies:
```bash
pip install feedparser beautifulsoup4 lxml requests selenium
```

## Usage

Run the main script to generate all teletext pages:

```bash
python demo.py
```

This will:
1. Fetch news from multiple Yle RSS feeds
2. Generate individual article pages with headlines
3. Create index pages for each category
4. Generate a weather map with live data
5. Create a comprehensive newsreel combining all content

## File Structure

- **demo.py**: Main script that generates all teletext pages
- **newsreel.py**: Creates the rotating newsreel page (P185)
- **weathermap.py**: Generates weather forecast pages with live OpenWeatherMap data
- **textBlock.py**: Handles text formatting for teletext
- **page.py**: TTI file import/export functions
- **legaliser.py**: Fixes accented characters for teletext compatibility

## Template Files

The system uses TTI template files for page layouts:
- `paauutiset_page.tti` / `paauutiset_index.tti` - Main news
- `tuoreimmat_page.tti` / `tuoreimmat_index.tti` - Latest news
- `sportgeneral_page.tti` / `sportgeneral_index.tti` - Sports
- `jalkapallo_page.tti` / `jalkapallo_index.tti` - Football
- `weathermap.tti` - Weather map template
- `newsreel_intro.tti` - Newsreel introduction
- `front_page.tti` - Main service index (P100)

## Output

Generated pages are exported to the `teletext/` directory as TTI files, which can be used by [vbit2](https://github.com/peterkvt80/vbit2).

## Configuration

### Weather API
The weather system uses OpenWeatherMap API. The API key is currently hardcoded in `weathermap.py`. To use your own key:

```python
api_key = "your_api_key_here"
```

### Page Numbers
You can customize which page numbers are used by modifying the `startPage` variables in `demo.py`.

### Number of Articles
Adjust `maxPages` in each section to control how many articles are fetched per category.

## Credits

NOS Demo by Nathan Dane changed by Max de Vos for YLE RSS feeds, 2025  
Copyright free - do what you like & have fun with it :)

## License

This project is copyright free. Feel free to use, modify, and distribute as you wish.
