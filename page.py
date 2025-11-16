
     #########  ##############  #######
    ##     ##  ##    ##    ##  ##
   ##     ##  ##    ##    ##  #######
  ##     ##  ##    ##    ##       ##
 ##     ##  ##    ##    ##  #######

# Page handling functions for CIMS
# Nathan Dane, 2022

import json, time, sys, copy

def access_bit(data, num):
	base = int(num // 8)
	shift = int(num % 8)
	return (data[base] >> shift) & 0x1

def set_bit(value, bit):
	return value | (1<<bit)

def clear_bit(value, bit):
	return value & ~(1<<bit)

# De-Minify a teletext page object
# Basically this takes care of all the inheritance stuff and returns fully-formed subpages
def teletextDeMinify(page):
	if "packets" in page:	# If there aren't any global packets, we're wasting our time
		#print("nothing to expand")
		#return page	# Return unchanged
		globalPackets = page["packets"]	# Get the global packets
	else:
		globalPackets = []
	
	if "subpages" not in page:	# Create a subpage list
		page["subpages"] = [{"packets":[]}]
	
	if len(page["subpages"]) < 1:
		page["subpages"] = [{"packets":[]}]
	
	for subcode,subpage in enumerate(page["subpages"]):	# For every subpage...
		if "inherit" in subpage:	# Don't add global packets when we've been asked not to
			if not subpage["inherit"]:
				continue
		
		if "control" not in subpage:
			if "control" in page:
				page["subpages"][subcode]["control"] = page["control"]
		
		for globalPacket in globalPackets:
			if not any(globalPacket["number"] == packet["number"] for packet in subpage["packets"]):	# If there's no overriding local packet
				page["subpages"][subcode]["packets"].append(copy.deepcopy(globalPacket))	# Add in the global packet
	
	if "packets" in page:
		del page["packets"]
	
	return(page)

# Minify a teletext page object
# Takes fully formed subpages, and makes common packets global
def teletextMinify(page):
	if "subpages" not in page:	# Don't bother if there are no subpages
		print("nothing to contract")
		return page	# Return unchanged

# Reads a .tti file into a standard teletext JSON object.
# Note that this is not a "minified" object (no inheritance, etc)
def loadTTI(filename):
	# Read in the file
	tti = open(filename, "r")
	ttiContent = tti.readlines()
	tti.close()
	
	# initialise variables for later
	output = {"subpages":[]}
	current = {}
	newPage = True
	subpageCounter = 0	# We only use this to check if the subcode makes sense
	
	for line in ttiContent:
		line = line.strip() # Remove any trailing whitespace
		
		# If an "attribute" comes through after an OL or FL, we assume this is a new page
		if line[:line.index(",")] in ["PN","SC","PS","CT"] and newPage:
			if current:
				if "packets" in current:
					current["packets"] = sorted(current["packets"],key = lambda d: d['number'])
					output["subpages"].append(current)	# If the current subpage isn't empty, write it to the output
					subpageCounter += 1
			
			newPage = False	# Reset 
			current = {}	# Create a fresh new subpage
		
		# Get the page number
		if line[:line.index(",")] == "PN":
			page_number = line[line.index(",") + 1:line.index(",") + 4]	# Find the "," and cut out the number bit
			if "number" in output:	# What if we already have a number for this page?
				if output["number"] != str(page_number):	# Is this the same as what we have?
					print("More than one page in this tti " + str(filename))	# Oh no, a weird page has appeared
					exit()	# This will be a return later
			else:
				output["number"] = str(page_number)	# Otherwise, this is our page number now
		
		# Get the page subcode
		elif line[:line.index(",")] == "SC":
			subcode = line[line.index(",") + 1:]
			# Subcode should only be defined if it's not what we would logically expect
			if (subpageCounter + 1) != int(subcode):
				current["subcode"] = str(subcode)
				#print(subpageCounter + 1)
				#print(int(subcode))
		
		# Get the page options
		elif line[:line.index(",")] == "PS":
			raw_page_status = bytearray.fromhex(line[line.index(",") + 1:])
			
			# Language is composed from three bits. Pretty sure this isn't the right order, either...
			language = (access_bit(raw_page_status,15) << 2) + (access_bit(raw_page_status,0) << 1) + access_bit(raw_page_status,1)
			
			if "control" not in current:
				current["control"] = {}
				
			if access_bit(raw_page_status,6) == 1:
				current["control"]["erasePage"] = True
			if access_bit(raw_page_status,8) == 1:
				current["control"]["newsFlash"] = True
			if access_bit(raw_page_status,9) == 1:
				current["control"]["subtitle"] = True
			if access_bit(raw_page_status,10) == 1:
				current["control"]["suppressHeader"] = True
			if access_bit(raw_page_status,11) == 1:
				current["control"]["update"] = True
			if access_bit(raw_page_status,13) == 1:
				current["control"]["suppressPage"] = True
			if access_bit(raw_page_status,12) == 1: # ?
				current["control"]["interruptedSequence"] = True
			
			# Only output the language bit if it's not zero
			if language != 0:
				current["control"]["language"] = language
		
		# Page cycle time. We ignore this for the time being 
		elif line[:line.index(",")] == "CT":
			if "control" not in current:
				current["control"] = {}
			current["control"]["cycleTime"] = line[line.index(",") + 1:]
		#	print("Cycle Time: " + line[line.index(",") + 1:])
		
		# Fasttext! A lot of the exciting stuff can be ignored here
		# as it's not implemented in .tti
		elif line[:line.index(",")] == "FL":
			fasttext = line[line.index(",") + 1:].split(',')
			
			if "packets" in current:
				current["packets"].append({"number":27, "dc":0, "linking":{"pages":fasttext}})
			else:
				current["packets"] = [{"number":27, "dc":0, "linking":{"pages":fasttext}}]
		
		# Output Lines (packets)
		# For the moment we only care about packets 0-25 - no level 2.5 here :(
		elif line[:line.index(",")] == "OL":
			newPage = True
			packet_number = int(line[line.index(",") + 1:line.index(",",3)])
			packet_content = line[line.index(",",3) + 1:]
			
			if (packet_number < 26) and (packet_number != 0):
				esc = False
				unescapedPacket = ""
				for position, character in enumerate(packet_content): # Un-escape the lines
					if esc:
						esc = False
						try:
							unescapedPacket += chr(ord(character) - 0x40)	# Get the escaped character and subtract 0x40 to make it normal
						except:
							print("loadTTI: error on page " + str(output["number"]) + " " + str(position) + " " + character)
							continue
						
						continue	# Skip straight on to the next character
					if character == "":	# Tell us that the next character is escaped
						esc = True
					else:
						unescapedPacket += character	# Pass other characters on through
				
				if "packets" in current:
					current["packets"].append({"number":packet_number, "text":unescapedPacket})
				else:
					current["packets"] = [{"number":packet_number, "text":unescapedPacket}]
		
		# Meta isn't in the spec yet, officially
		#elif line[:line.index(",")] == "DE":	# This isn't important, and has no bearing on the page
		#	if "meta" in output:
		#		output["meta"]["title"] = line[line.index(",") + 1:]
		#	else:
		#		output["meta"] = {"title":line[line.index(",") + 1:]}
	
	# Write out final subpage
	if current:
		if "packets" in current:
			current["packets"]=sorted(current["packets"],key=lambda d: d['number'])
			output["subpages"].append(current)	# If the current subpage isn't empty, write it to the output
	
	# This is a form of minification, which I've now decided will be taken care of elsewhere
	#if len(output["subpages"]) == 1:	# If there's only one subpage
	#	output = dict(**output, **output["subpages"][0])
	#	del output["subpages"]
	#	del output["subcode"]

	return(output)

# Export a standard teletext object to a .tti file
def exportTTI(page):
	page_number = page["number"]
	output = []
	
	page = teletextDeMinify(page)
	
	if len(page["subpages"]) > 1:
		subcodeOffset = 1
	else:
		subcodeOffset = 0
	
	for guessed_subcode, subpage in enumerate(page["subpages"]):
		if "subcode" in subpage:
			subcode = subpage["subcode"]
		else:
			subcode = str(guessed_subcode + subcodeOffset).zfill(4)
		
		if int(subcode) > 99:
			print("This page has more than 99 subpages. For our purposes, .tti doesn't support that")
			return False;
		
		output.append("PN," + str(page_number) + subcode[2:])
		output.append("SC," + str(subcode))
		
		if "control" not in subpage:
			if "control" in page:
				subpage["control"] = page["control"]
		
		page_status = 0
		page_status = set_bit(page_status,15) # Transmit page
		
		if "control" in subpage:
			if "erasePage" in subpage["control"] and subpage["control"]["erasePage"] == True:
				page_status = set_bit(page_status,14)
			if "newsFlash" in subpage["control"] and subpage["control"]["newsFlash"] == True:
				page_status = set_bit(page_status,0)
			if "subtitle" in subpage["control"] and subpage["control"]["subtitle"] == True:
				page_status = set_bit(page_status,1)
			if "suppressHeader" in subpage["control"] and subpage["control"]["suppressHeader"] == True:
				page_status = set_bit(page_status,2)
			if "update" in subpage["control"] and subpage["control"]["update"] == True:
				page_status = set_bit(page_status,3)
			if "suppressPage" in subpage["control"] and subpage["control"]["suppressPage"] == True:
				page_status = set_bit(page_status,5)
			if "interruptedSequence" in subpage["control"] and subpage["control"]["interruptedSequence"] == True:
				page_status = set_bit(page_status,4)
			if "cycleTime" in subpage["control"]:
				output.append("CT," + subpage["control"]["cycleTime"])
			if "transmitPage" in subpage["control"]:
				page_status = clear_bit(page_status,15)
		
		#page_status = set_bit(page_status,3)
		
		output.append("PS," + hex(page_status)[2:])
		
		output.append("OL,0,        " + chr(27) + "ECIMS" + chr(27) + "B" + chr(27) + "F" + str(page_number) + chr(27) + "A" + str(int(time.time())))
		
		for packet in subpage["packets"]:
			if "text" in packet:
				if packet["number"] > 0 and packet["number"] < 27:
					escapedPacket = ""
					if len(packet["text"]) > 40:
						print("P" + page_number + " Packet longer than 40 bytes - " + packet["text"])
					for character in packet["text"]:
						if ord(character) < 0x20:
							escapedPacket = escapedPacket + chr(27) + chr(ord(character) + 0x40)
						else:
							escapedPacket = escapedPacket + character
						
						if ord(character) >=128:
							print("Unsafe Character on P" + str(page_number) + " S" + str(subcode))
						
					output.append("OL," + str(packet["number"]) + "," + escapedPacket)
			
			if "linking" in packet:
				if packet["number"] != 27:
					print("Unexpected linking packet")
					return False
					
				fasttext = "FL"
				
				if "pages" in packet["linking"]:
					for link in packet["linking"]["pages"]:
						#if link in navigationLinks:
						#	link = navigationLinks[link]
						
						fasttext += "," + link
					
					output.append(fasttext)
	
	filename = "teletext/P" + str(page_number) + ".tti"
	
	with open(filename, 'w') as f:
		for line in output:
			f.write("%s\r\n" % line)

#	How about an out-of-band flag, like a meta tag or something, to signal when this should be done!?
def numberSubpage(page, row=20, offset=1, prefix=chr(7), align="right"):
	if "subpages" not in page:
		return page
	
	totalSubpages = len(page["subpages"])
	
	if totalSubpages < 2:
		return page
	
	output = {"subpages":[]}
	
	# Now this is an Assumption. Assumptions are BAD, but I think we can get away with it here.
	# For now, at least.
	# We are going to number the subpages in the exact order they are presented, and ignore the specified subcode.
	# Why? Well, almost no subpages will have a strict subcode defined - and those that do probably will be numbered by order anyway.
	
	for guessed_subcode, subpage in enumerate(page["subpages"]):
		# Let's go ahead and generate the actual count now, since it will almost always be needed no matter what happens below.
		counter = prefix + str((guessed_subcode + 1)) + "/" + str(totalSubpages)
		counterLen = len(counter)
		
		if totalSubpages > 9 and offset > 0 and align == "right":
			offset -= 1
		
		positionInList = next((i for i, packet in enumerate(subpage["packets"]) if packet["number"] == row), None)
		
		if positionInList is not None:
			# This should be impossible:
			if subpage["packets"][positionInList]["number"] != row:
				print("desolate screaming noises")	# hence
				return page
			
			# OK, we have a row. Now to figure out how to splice the bits together.
			if align == "right":
				# First, pad the string to 40 chars. There's nothing in the spec to say this will be done for us
				# Cut the string to length and add the counter onto the end
				# ToDo: if the offset is large enough, add the end of the string back on again?
				subpage["packets"][positionInList]["text"] = subpage["packets"][positionInList]["text"].ljust(40)[:(40 - (counterLen + offset))] + counter
			elif align == "left":
				# Here the offset is added to the left as spaces.
				# ToDo: again, we should just add the left part of the packet if there's too much offset
				subpage["packets"][positionInList]["text"] = (" " * offset) + counter + subpage["packets"][positionInList]["text"].ljust(40)[((counterLen + offset)):]
		
		else:
			if align == "right":
				subpage["packets"].append({"number":row, "text":(" " * (40 - (counterLen + offset))) + counter})
			elif align == "left":
				subpage["packets"].append({"number":row, "text":(" " * offset) + counter})
		
		output["subpages"].append(subpage)
		
	
	return page

def comparison(pageA,pageB,debug=False):
	pageA = teletextDeMinify(pageA)
	pageB = teletextDeMinify(pageB)
	
	if len(pageA["subpages"]) != len(pageB["subpages"]):
		return False
	
	for A, B in zip(pageA["subpages"],pageB["subpages"]):
		A = sorted(A["packets"], key=lambda d: d['number'])
		B = sorted(B["packets"], key=lambda d: d['number'])
		
		if A != B:
			if debug:
				print("Change detected!")
				with open('debugA.json', 'w', encoding='utf-8') as f:
					json.dump(A, f, ensure_ascii=False, indent=4)
				with open('debugB.json', 'w', encoding='utf-8') as f:
					json.dump(B, f, ensure_ascii=False, indent=4)
			return False
	
	return True

def blockOverlay(rawSource,overlay,startx,starty,endx,endy,align="centre"):
	source = copy.deepcopy(rawSource)
	
	if startx > endx or starty > endy:
		print("blockOverlay: Grid input fault")
		return source
	
	for itNum,rowNum in enumerate(range(starty,endy+1)):
		positionInSourceList = next((i for i, packet in enumerate(source) if packet["number"] == rowNum), None)
		positionInOverlayList = next((i for i, packet in enumerate(overlay) if packet["number"] == itNum+1), None)
		
		if positionInSourceList == None:
			source.append({"number":rowNum,"text":"                                        "})
			positionInSourceList = next((i for i, packet in enumerate(source) if packet["number"] == rowNum), None)
		
		if positionInOverlayList == None:
			overlay.append({"number":itNum+1,"text":"                                        "})
			positionInOverlayList = next((i for i, packet in enumerate(overlay) if packet["number"] == itNum+1), None)
		
		source[positionInSourceList]["text"] = (source[positionInSourceList]["text"].ljust(40," ")[:startx] + overlay[positionInOverlayList]["text"].ljust(40," ")[:(endx-startx)] + source[positionInSourceList]["text"][endx:])
	
	return source

#print(blockOverlay(testPacketList,overlayBlock,8,5,39,5))

#tti = loadTTI("340.tti")

#f = open("ttiTest.json", "w")
#f.write(json.dumps(tti))
#f.close()

#exportTTI(tti, "test.tti")

#if __name__ == '__main__':
#	name = sys.argv[1]
#	
#	tti = loadTTI(name + ".tti")
#
#	f = open(name + ".json", "w")
#	f.write(json.dumps(tti))
#	f.close()