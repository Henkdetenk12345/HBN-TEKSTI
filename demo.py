
     ##         ##############  #########
    ##         ##    ##    ##  ##     ##
   #########  ##    ##    ##  ##     ##
  ##     ##  ##    ##    ##  ##     ##
 #########  ##    ##    ##  ##     ##
 
# YLE to Teletext converter
# Demo by Max de Vos for Soyuzrocket, 2025-2026
# Copyright (C) 2025-2026 Max de Vos

# Start by importing all the libraries we need
import feedparser
from bs4 import BeautifulSoup
import lxml
import copy
import newsreel
import weathermap
import veikkausliiga
import hsl_teletext
import tv
import radio
from newsflash import run_newsflash
from weather import main as weather_main
from datetime import datetime
import unicodedata

from textBlock import toTeletextBlock
from page import exportTTI, loadTTI
from legaliser import pageLegaliser

# Finse dag- en maandnamen
FINNISH_DAYS = ["MAANANTAI", "TIISTAI", "KESKIVIIKKO", "TORSTAI", "PERJANTAI", "LAUANTAI", "SUNNUNTAI"]
FINNISH_MONTHS = ["TAMMIKUU", "HELMIKUU", "MAALISKUU", "HUHTIKUU", "TOUKOKUU", "KESÄKUU", 
                  "HEINÄKUU", "ELOKUU", "SYYSKUU", "LOKAKUU", "MARRASKUU", "JOULUKUU"]

def get_finnish_day():
    """Geeft de huidige dag in het Fins terug"""
    now = datetime.now()
    return FINNISH_DAYS[now.weekday()]

def get_finnish_date():
    """Geeft volledige datum in het Fins (bijv. MAANANTAI 16.11.)"""
    now = datetime.now()
    day_name = FINNISH_DAYS[now.weekday()]
    return f"{day_name} {now.day}.{now.month}."

def clean_text_aggressive(text):
    """Verwijdert/normaliseert alle problematische karakters voor teletext"""
    if not text:
        return text
    
    # Normaliseer Unicode (bijv. gecombineerde accenten naar enkele karakters)
    text = unicodedata.normalize('NFKC', text)
    
    # Verwijder alle control characters en invisible characters
    cleaned = []
    for char in text:
        cat = unicodedata.category(char)
        # Cc = Control, Cf = Format, Zs = Space separator
        if cat == 'Cc' or cat == 'Cf':
            # Skip control en format characters
            continue
        elif cat == 'Zs' and char != ' ':
            # Vervang alle niet-standaard spaties met normale spatie
            cleaned.append(' ')
        else:
            cleaned.append(char)
    
    return ''.join(cleaned)

def vervang_datum_in_tti(tti_data):
    """Vervangt DAY en DATE placeholders in TTI data met Finse datum"""
    dag = get_finnish_day()
    datum = get_finnish_date()
    
    # Loop door alle packets en vervang placeholders in de text
    for subpage in tti_data.get("subpages", []):
        for packet in subpage.get("packets", []):
            if "text" in packet:
                packet["text"] = packet["text"].replace("DAY", dag)
                packet["text"] = packet["text"].replace("DATE", datum)
    
    return tti_data

# Load the template page for the header & footer
newsPageTemplate = loadTTI("paauutiset_page.tti")

# How many news pages do we want to create?
maxPages = 10
startPage = 102

# Download and parse an RSS Feed of news from Yle
newsData = feedparser.parse("https://yle.fi/rss/uutiset/paauutiset")

# Initialise a Page Counter
pageNum = 0

# Create a headlines list for P101
headlines = []

# Loop through each news story to produce pages
for newsArticle in newsData['entries']:
	# Set the first line we write on
	line = 5
	
	# Create a new teletext page
	teletextPage = {"number":(pageNum + startPage),"subpages":[{"packets":copy.deepcopy(newsPageTemplate["subpages"][0]["packets"])}]}
	
	# Vervang DAY/DATE placeholders in de template
	teletextPage = vervang_datum_in_tti(teletextPage)
	
	# Get the title from Yle RSS
	clean_title = newsArticle["title"].strip()
	
	# Create the title
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"yellow","text":clean_title}]}]},
		line = line
	)
	
	# Move on the line pointer
	line += (len(paraBlock) + 1)
	
	# Add the title to the teletext page
	teletextPage["subpages"][0]["packets"] += paraBlock
	
	# Yle gebruikt 'description' voor de samenvatting
	if "description" in newsArticle:
		article_text = newsArticle["description"]
	else:
		article_text = newsArticle["title"]  # fallback

	# fix: verwijder soft hyphen (U+00AD)
	article_text = article_text.replace("\u00AD", "")
    
	# Voor Yle is description plain text, maar we gebruiken BeautifulSoup voor de zekerheid
	soup = BeautifulSoup(article_text, "lxml")
	
	# Maak één paragraaf van de beschrijving
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"white","text":soup.get_text()}]}]},
		line = line
	)
	
	# Is this going to make the page too long?
	if (len(paraBlock) + line) <= 22:
		# Move on the line pointer
		line += (len(paraBlock) + 1)
		
		# Add this paragraph to the teletext page
		teletextPage["subpages"][0]["packets"] += paraBlock
	
	# Export the final page
	# We run it through "legaliser", this fixes the accented characters, but may be wrong for your country!
	exportTTI(pageLegaliser(teletextPage))
	
	# Use the cleaned title for headlines too
	headlines.append({"title":clean_title,"number":str(pageNum + startPage)})
	
	# Iterate the page counter
	pageNum += 1
	
	# Stop when we have enough pages
	if pageNum > maxPages:
		break

# Next we create P101, the headlines
# Start by loading the template
newsIndexTemplate = loadTTI("paauutiset_index.tti")

# Create a page
teletextPage = {"number":101,"subpages":[{"packets":copy.deepcopy(newsIndexTemplate["subpages"][0]["packets"])}]}

# Vervang DAY/DATE placeholders met echte Finse datum
teletextPage = vervang_datum_in_tti(teletextPage)

line = 5

for headline in headlines:
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"white","text":headline["title"]}]},{"align":"right","content":[{"colour":"yellow","text":headline["number"]}]}]},
		line = line
	)
	
	# Is this going to make the page too long?
	if (len(paraBlock) + line) > 22:
		break
	
	# Move on the line pointer
	line += (len(paraBlock) + 1)
	
	# Add this paragraph to the teletext page
	teletextPage["subpages"][0]["packets"] += paraBlock

exportTTI(pageLegaliser(teletextPage))

# Load the template page for the header & footer
newsPageTemplate = loadTTI("tuoreimmat_page.tti")

# How many news pages do we want to create?
maxPages = 10
startPage = 112

# Download and parse an RSS Feed of news from Yle
newsData = feedparser.parse("https://yle.fi/rss/uutiset/tuoreimmat")

# Initialise a Page Counter
pageNum = 0

# Create a headlines list for P101
headlines = []

# Loop through each news story to produce pages
for newsArticle in newsData['entries']:
	# Set the first line we write on
	line = 5
	
	# Create a new teletext page
	teletextPage = {"number":(pageNum + startPage),"subpages":[{"packets":copy.deepcopy(newsPageTemplate["subpages"][0]["packets"])}]}
	
	# Vervang DAY/DATE placeholders in de template
	teletextPage = vervang_datum_in_tti(teletextPage)
	
	# Get the title from Yle RSS
	clean_title = newsArticle["title"].strip()
	
	# Create the title
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"yellow","text":clean_title}]}]},
		line = line
	)
	
	# Move on the line pointer
	line += (len(paraBlock) + 1)
	
	# Add the title to the teletext page
	teletextPage["subpages"][0]["packets"] += paraBlock
	
	# Yle gebruikt 'description' voor de samenvatting
	if "description" in newsArticle:
		article_text = newsArticle["description"]
	else:
		article_text = newsArticle["title"]  # fallback

	# fix: verwijder soft hyphen (U+00AD)
	article_text = article_text.replace("\u00AD", "")
    
	# Voor Yle is description plain text, maar we gebruiken BeautifulSoup voor de zekerheid
	soup = BeautifulSoup(article_text, "lxml")
	
	# Maak één paragraaf van de beschrijving
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"white","text":soup.get_text()}]}]},
		line = line
	)
	
	# Is this going to make the page too long?
	if (len(paraBlock) + line) <= 22:
		# Move on the line pointer
		line += (len(paraBlock) + 1)
		
		# Add this paragraph to the teletext page
		teletextPage["subpages"][0]["packets"] += paraBlock
	
	# Export the final page
	# We run it through "legaliser", this fixes the accented characters, but may be wrong for your country!
	exportTTI(pageLegaliser(teletextPage))
	
	# Use the cleaned title for headlines too
	headlines.append({"title":clean_title,"number":str(pageNum + startPage)})
	
	# Iterate the page counter
	pageNum += 1
	
	# Stop when we have enough pages
	if pageNum > maxPages:
		break

# Next we create P111, the headlines
# Start by loading the template
newsIndexTemplate = loadTTI("tuoreimmat_index.tti")

# Create a page
teletextPage = {"number":111,"subpages":[{"packets":copy.deepcopy(newsIndexTemplate["subpages"][0]["packets"])}]}

# Vervang DAY/DATE placeholders met echte Finse datum
teletextPage = vervang_datum_in_tti(teletextPage)

line = 5

for headline in headlines:
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"white","text":headline["title"]}]},{"align":"right","content":[{"colour":"yellow","text":headline["number"]}]}]},
		line = line
	)
	
	# Is this going to make the page too long?
	if (len(paraBlock) + line) > 22:
		break
	
	# Move on the line pointer
	line += (len(paraBlock) + 1)
	
	# Add this paragraph to the teletext page
	teletextPage["subpages"][0]["packets"] += paraBlock

exportTTI(pageLegaliser(teletextPage))

# Load the template page for the header & footer
newsPageTemplate = loadTTI("sportgeneral_page.tti")

# How many news pages do we want to create?
maxPages = 4
startPage = 302

# Download and parse an RSS Feed of news from Yle
newsData = feedparser.parse("https://yle.fi/rss/urheilu")

# Initialise a Page Counter
pageNum = 0

# Create a headlines list for P101
headlines = []

# Loop through each news story to produce pages
for newsArticle in newsData['entries']:
	# Set the first line we write on
	line = 5
	
	# Create a new teletext page
	teletextPage = {"number":(pageNum + startPage),"subpages":[{"packets":copy.deepcopy(newsPageTemplate["subpages"][0]["packets"])}]}
	
	# Vervang DAY/DATE placeholders in de template
	teletextPage = vervang_datum_in_tti(teletextPage)
	
	# Get the title from Yle RSS
	clean_title = newsArticle["title"].strip()
	
	# Create the title
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"yellow","text":clean_title}]}]},
		line = line
	)
	
	# Move on the line pointer
	line += (len(paraBlock) + 1)
	
	# Add the title to the teletext page
	teletextPage["subpages"][0]["packets"] += paraBlock
	
	# Yle gebruikt 'description' voor de samenvatting
	if "description" in newsArticle:
		article_text = newsArticle["description"]
	else:
		article_text = newsArticle["title"]  # fallback

	# fix: verwijder soft hyphen (U+00AD)
	article_text = article_text.replace("\u00AD", "")
    
	# Voor Yle is description plain text, maar we gebruiken BeautifulSoup voor de zekerheid
	soup = BeautifulSoup(article_text, "lxml")
	
	# Maak één paragraaf van de beschrijving
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"white","text":soup.get_text()}]}]},
		line = line
	)
	
	# Is this going to make the page too long?
	if (len(paraBlock) + line) <= 22:
		# Move on the line pointer
		line += (len(paraBlock) + 1)
		
		# Add this paragraph to the teletext page
		teletextPage["subpages"][0]["packets"] += paraBlock
	
	# Export the final page
	# We run it through "legaliser", this fixes the accented characters, but may be wrong for your country!
	exportTTI(pageLegaliser(teletextPage))
	
	# Use the cleaned title for headlines too
	headlines.append({"title":clean_title,"number":str(pageNum + startPage)})
	
	# Iterate the page counter
	pageNum += 1
	
	# Stop when we have enough pages
	if pageNum > maxPages:
		break

# Next we create P111, the headlines
# Start by loading the template
newsIndexTemplate = loadTTI("sportgeneral_index.tti")

# Create a page
teletextPage = {"number":301,"subpages":[{"packets":copy.deepcopy(newsIndexTemplate["subpages"][0]["packets"])}]}

# Vervang DAY/DATE placeholders met echte Finse datum
teletextPage = vervang_datum_in_tti(teletextPage)

line = 5

for headline in headlines:
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"white","text":headline["title"]}]},{"align":"right","content":[{"colour":"yellow","text":headline["number"]}]}]},
		line = line
	)
	
	# Is this going to make the page too long?
	if (len(paraBlock) + line) > 22:
		break
	
	# Move on the line pointer
	line += (len(paraBlock) + 1)
	
	# Add this paragraph to the teletext page
	teletextPage["subpages"][0]["packets"] += paraBlock

exportTTI(pageLegaliser(teletextPage))

# Load the template page for the header & footer
newsPageTemplate = loadTTI("jalkapallo_page.tti")

# How many news pages do we want to create?
maxPages = 4
startPage = 309

# Download and parse an RSS Feed of news from Yle
newsData = feedparser.parse("https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_URHEILU&concepts=18-205598")

# Initialise a Page Counter
pageNum = 0

# Create a headlines list for P101
headlines = []

# Loop through each news story to produce pages
for newsArticle in newsData['entries']:
	# Set the first line we write on
	line = 5
	
	# Create a new teletext page
	teletextPage = {"number":(pageNum + startPage),"subpages":[{"packets":copy.deepcopy(newsPageTemplate["subpages"][0]["packets"])}]}
	
	# Vervang DAY/DATE placeholders in de template
	teletextPage = vervang_datum_in_tti(teletextPage)
	
	# Get the title from Yle RSS - CLEAN IT FOR JALKAPALLO!
	clean_title = clean_text_aggressive(newsArticle["title"].strip())
	
	# Create the title
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"yellow","text":clean_title}]}]},
		line = line
	)
	
	# Move on the line pointer
	line += (len(paraBlock) + 1)
	
	# Add the title to the teletext page
	teletextPage["subpages"][0]["packets"] += paraBlock
	
	# Yle gebruikt 'description' voor de samenvatting
	if "description" in newsArticle:
		article_text = newsArticle["description"]
	else:
		article_text = newsArticle["title"]  # fallback

	# CLEAN THE TEXT AGGRESSIVELY FOR JALKAPALLO!
	article_text = clean_text_aggressive(article_text)
    
	# Voor Yle is description plain text, maar we gebruiken BeautifulSoup voor de zekerheid
	soup = BeautifulSoup(article_text, "lxml")
	
	# Maak één paragraaf van de beschrijving
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"white","text":soup.get_text()}]}]},
		line = line
	)
	
	# Is this going to make the page too long?
	if (len(paraBlock) + line) <= 22:
		# Move on the line pointer
		line += (len(paraBlock) + 1)
		
		# Add this paragraph to the teletext page
		teletextPage["subpages"][0]["packets"] += paraBlock
	
	# Export the final page
	# We run it through "legaliser", this fixes the accented characters, but may be wrong for your country!
	exportTTI(pageLegaliser(teletextPage))
	
	# Use the cleaned title for headlines too
	headlines.append({"title":clean_title,"number":str(pageNum + startPage)})
	
	# Iterate the page counter
	pageNum += 1
	
	# Stop when we have enough pages
	if pageNum > maxPages:
		break

# Next we create P308, the headlines
# Start by loading the template
newsIndexTemplate = loadTTI("jalkapallo_index.tti")

# Create a page
teletextPage = {"number":308,"subpages":[{"packets":copy.deepcopy(newsIndexTemplate["subpages"][0]["packets"])}]}

# Vervang DAY/DATE placeholders met echte Finse datum
teletextPage = vervang_datum_in_tti(teletextPage)

line = 5

for headline in headlines:
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"white","text":headline["title"]}]},{"align":"right","content":[{"colour":"yellow","text":headline["number"]}]}]},
		line = line
	)
	
	# Is this going to make the page too long?
	if (len(paraBlock) + line) > 22:
		break
	
	# Move on the line pointer
	line += (len(paraBlock) + 1)
	
	# Add this paragraph to the teletext page
	teletextPage["subpages"][0]["packets"] += paraBlock

exportTTI(pageLegaliser(teletextPage))

# Load the template page for the header & footer
newsPageTemplate = loadTTI("matkailu_page.tti")

# How many news pages do we want to create?
maxPages = 4
startPage = 402

# Download and parse an RSS Feed of news from Yle
newsData = feedparser.parse("https://yle.fi/rss/t/18-206851/fi")

# Initialise a Page Counter
pageNum = 0

# Create a headlines list for P101
headlines = []

# Loop through each news story to produce pages
for newsArticle in newsData['entries']:
	# Set the first line we write on
	line = 5
	
	# Create a new teletext page
	teletextPage = {"number":(pageNum + startPage),"subpages":[{"packets":copy.deepcopy(newsPageTemplate["subpages"][0]["packets"])}]}
	
	# Vervang DAY/DATE placeholders in de template
	teletextPage = vervang_datum_in_tti(teletextPage)
	
	# Get the title from Yle RSS
	clean_title = newsArticle["title"].strip()
	
	# Create the title
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"yellow","text":clean_title}]}]},
		line = line
	)
	
	# Move on the line pointer
	line += (len(paraBlock) + 1)
	
	# Add the title to the teletext page
	teletextPage["subpages"][0]["packets"] += paraBlock
	
	# Yle gebruikt 'description' voor de samenvatting
	if "description" in newsArticle:
		article_text = newsArticle["description"]
	else:
		article_text = newsArticle["title"]  # fallback

	# fix: verwijder soft hyphen (U+00AD)
	article_text = article_text.replace("\u00AD", "")
    
	# Voor Yle is description plain text, maar we gebruiken BeautifulSoup voor de zekerheid
	soup = BeautifulSoup(article_text, "lxml")
	
	# Maak één paragraaf van de beschrijving
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"white","text":soup.get_text()}]}]},
		line = line
	)
	
	# Is this going to make the page too long?
	if (len(paraBlock) + line) <= 22:
		# Move on the line pointer
		line += (len(paraBlock) + 1)
		
		# Add this paragraph to the teletext page
		teletextPage["subpages"][0]["packets"] += paraBlock
	
	# Export the final page
	# We run it through "legaliser", this fixes the accented characters, but may be wrong for your country!
	exportTTI(pageLegaliser(teletextPage))
	
	# Use the cleaned title for headlines too
	headlines.append({"title":clean_title,"number":str(pageNum + startPage)})
	
	# Iterate the page counter
	pageNum += 1
	
	# Stop when we have enough pages
	if pageNum > maxPages:
		break

# Next we create P111, the headlines
# Start by loading the template
newsIndexTemplate = loadTTI("matkailu_index.tti")

# Create a page
teletextPage = {"number":401,"subpages":[{"packets":copy.deepcopy(newsIndexTemplate["subpages"][0]["packets"])}]}

# Vervang DAY/DATE placeholders met echte Finse datum
teletextPage = vervang_datum_in_tti(teletextPage)

line = 5

for headline in headlines:
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"white","text":headline["title"]}]},{"align":"right","content":[{"colour":"yellow","text":headline["number"]}]}]},
		line = line
	)
	
	# Is this going to make the page too long?
	if (len(paraBlock) + line) > 22:
		break
	
	# Move on the line pointer
	line += (len(paraBlock) + 1)
	
	# Add this paragraph to the teletext page
	teletextPage["subpages"][0]["packets"] += paraBlock

exportTTI(pageLegaliser(teletextPage))

# Load the template page for the header & footer
newsPageTemplate = loadTTI("politics_page.tti")

# How many news pages do we want to create?
maxPages = 10
startPage = 124

# Download and parse an RSS Feed of news from Yle
newsData = feedparser.parse("https://yle.fi/rss/t/18-220306/fi")

# Initialise a Page Counter
pageNum = 0

# Create a headlines list for P123
headlines = []

# Loop through each news story to produce pages
for newsArticle in newsData['entries']:
	# Set the first line we write on
	line = 5
	
	# Create a new teletext page
	teletextPage = {"number":(pageNum + startPage),"subpages":[{"packets":copy.deepcopy(newsPageTemplate["subpages"][0]["packets"])}]}
	
	# Vervang DAY/DATE placeholders in de template
	teletextPage = vervang_datum_in_tti(teletextPage)
	
	# Get the title from Yle RSS
	clean_title = newsArticle["title"].strip()
	
	# Create the title
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"yellow","text":clean_title}]}]},
		line = line
	)
	
	# Move on the line pointer
	line += (len(paraBlock) + 1)
	
	# Add the title to the teletext page
	teletextPage["subpages"][0]["packets"] += paraBlock
	
	# Yle gebruikt 'description' voor de samenvatting
	if "description" in newsArticle:
		article_text = newsArticle["description"]
	else:
		article_text = newsArticle["title"]  # fallback

	# fix: verwijder soft hyphen (U+00AD)
	article_text = article_text.replace("\u00AD", "")
    
	# Voor Yle is description plain text, maar we gebruiken BeautifulSoup voor de zekerheid
	soup = BeautifulSoup(article_text, "lxml")
	
	# Maak één paragraaf van de beschrijving
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"white","text":soup.get_text()}]}]},
		line = line
	)
	
	# Is this going to make the page too long?
	if (len(paraBlock) + line) <= 22:
		# Move on the line pointer
		line += (len(paraBlock) + 1)
		
		# Add this paragraph to the teletext page
		teletextPage["subpages"][0]["packets"] += paraBlock
	
	# Export the final page
	# We run it through "legaliser", this fixes the accented characters, but may be wrong for your country!
	exportTTI(pageLegaliser(teletextPage))
	
	# Use the cleaned title for headlines too
	headlines.append({"title":clean_title,"number":str(pageNum + startPage)})
	
	# Iterate the page counter
	pageNum += 1
	
	# Stop when we have enough pages
	if pageNum > maxPages:
		break

# Next we create P101, the headlines
# Start by loading the template
newsIndexTemplate = loadTTI("politics_index.tti")

# Create a page
teletextPage = {"number":123,"subpages":[{"packets":copy.deepcopy(newsIndexTemplate["subpages"][0]["packets"])}]}

# Vervang DAY/DATE placeholders met echte Finse datum
teletextPage = vervang_datum_in_tti(teletextPage)

line = 5

for headline in headlines:
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"white","text":headline["title"]}]},{"align":"right","content":[{"colour":"yellow","text":headline["number"]}]}]},
		line = line
	)
	
	# Is this going to make the page too long?
	if (len(paraBlock) + line) > 22:
		break
	
	# Move on the line pointer
	line += (len(paraBlock) + 1)
	
	# Add this paragraph to the teletext page
	teletextPage["subpages"][0]["packets"] += paraBlock

exportTTI(pageLegaliser(teletextPage))

# Load the template page for the header & footer
newsPageTemplate = loadTTI("talous_page.tti")

# How many news pages do we want to create?
maxPages = 3
startPage = 202

# Download and parse an RSS Feed of news from Yle
newsData = feedparser.parse("https://yle.fi/rss/t/18-204933/fi")

# Initialise a Page Counter
pageNum = 0

# Create a headlines list for P123
headlines = []

# Loop through each news story to produce pages
for newsArticle in newsData['entries']:
	# Set the first line we write on
	line = 5
	
	# Create a new teletext page
	teletextPage = {"number":(pageNum + startPage),"subpages":[{"packets":copy.deepcopy(newsPageTemplate["subpages"][0]["packets"])}]}
	
	# Vervang DAY/DATE placeholders in de template
	teletextPage = vervang_datum_in_tti(teletextPage)
	
	# Get the title from Yle RSS
	clean_title = newsArticle["title"].strip()
	
	# Create the title
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"yellow","text":clean_title}]}]},
		line = line
	)
	
	# Move on the line pointer
	line += (len(paraBlock) + 1)
	
	# Add the title to the teletext page
	teletextPage["subpages"][0]["packets"] += paraBlock
	
	# Yle gebruikt 'description' voor de samenvatting
	if "description" in newsArticle:
		article_text = newsArticle["description"]
	else:
		article_text = newsArticle["title"]  # fallback

	# fix: verwijder soft hyphen (U+00AD)
	article_text = article_text.replace("\u00AD", "")
    
	# Voor Yle is description plain text, maar we gebruiken BeautifulSoup voor de zekerheid
	soup = BeautifulSoup(article_text, "lxml")
	
	# Maak één paragraaf van de beschrijving
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"white","text":soup.get_text()}]}]},
		line = line
	)
	
	# Is this going to make the page too long?
	if (len(paraBlock) + line) <= 22:
		# Move on the line pointer
		line += (len(paraBlock) + 1)
		
		# Add this paragraph to the teletext page
		teletextPage["subpages"][0]["packets"] += paraBlock
	
	# Export the final page
	# We run it through "legaliser", this fixes the accented characters, but may be wrong for your country!
	exportTTI(pageLegaliser(teletextPage))
	
	# Use the cleaned title for headlines too
	headlines.append({"title":clean_title,"number":str(pageNum + startPage)})
	
	# Iterate the page counter
	pageNum += 1
	
	# Stop when we have enough pages
	if pageNum > maxPages:
		break

# Next we create P101, the headlines
# Start by loading the template
newsIndexTemplate = loadTTI("talous_index.tti")

# Create a page
teletextPage = {"number":201,"subpages":[{"packets":copy.deepcopy(newsIndexTemplate["subpages"][0]["packets"])}]}

# Vervang DAY/DATE placeholders met echte Finse datum
teletextPage = vervang_datum_in_tti(teletextPage)

line = 5

for headline in headlines:
	paraBlock = toTeletextBlock(
		input = {"content":[{"align":"left","content":[{"colour":"white","text":headline["title"]}]},{"align":"right","content":[{"colour":"yellow","text":headline["number"]}]}]},
		line = line
	)
	
	# Is this going to make the page too long?
	if (len(paraBlock) + line) > 22:
		break
	
	# Move on the line pointer
	line += (len(paraBlock) + 1)
	
	# Add this paragraph to the teletext page
	teletextPage["subpages"][0]["packets"] += paraBlock

exportTTI(pageLegaliser(teletextPage))

# Reset headlines naar paauutiset voor P100
newsData = feedparser.parse("https://yle.fi/rss/uutiset/paauutiset")
headlines = []

pageNum = 0
for newsArticle in newsData['entries']:
    clean_title = newsArticle["title"].strip()
    headlines.append({"title":clean_title,"number":str(102 + pageNum)})
    pageNum += 1
    if pageNum >= 9:  # 102 t/m 110 = 9 pagina's
        break

# Finally, let's make P100, the main service index.
frontPageTemplate = loadTTI("front_page.tti")

# Create a page
teletextPage = {"number":100,"control":{"cycleTime":"5,T"},"subpages":[]}

for headline in headlines:
	paraBlock = toTeletextBlock(
		input = {
			"content":[
				{"align":"left","postWrapLimit":{"maxLines":2,"cutoff":36},"content":[{"colour":"white","text":headline["title"]}]},
				{"align":"right","content":[{"colour":"yellow","text":headline["number"]}]}
			]},
		line = 18
	)
	
	newSubpage = {"packets":copy.deepcopy(frontPageTemplate["subpages"][0]["packets"]) + paraBlock}
	
	teletextPage["subpages"].append(newSubpage)

exportTTI(pageLegaliser(teletextPage))
newsreel.run_newsreel()
weather_main()
tv_scraper = tv.TelsuScraper()
tv_data = tv_scraper.scrape_all_channels()
tv_scraper.create_all_teletext_pages(tv_data)
radio_scraper = radio.YleRadioScraper()
radio_data = radio_scraper.scrape_radio_guide()
radio_scraper.create_all_teletext_pages(radio_data)
run_newsflash()
