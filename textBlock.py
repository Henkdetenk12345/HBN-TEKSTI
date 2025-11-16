
     #########  ##############  #######
    ##     ##  ##    ##    ##  ##
   ##     ##  ##    ##    ##  #######
  ##     ##  ##    ##    ##       ##
 ##     ##  ##    ##    ##  #######

# Text handling functions for CIMS
# Nathan Dane, 2022

from legaliser import charsub
import re
import logging
from datetime import datetime

def colourCode(colour):
	textColourCode = {
		"black":chr(0),
		"red":chr(1),
		"green":chr(2),
		"yellow":chr(3),
		"blue":chr(4),
		"magenta":chr(5),
		"cyan":chr(6),
		"white":chr(7),
		"test":chr(5) + chr(29) + chr(7),
	}
	
	if colour in textColourCode:
		return textColourCode[colour]
	else:
		return " "

# Table row will create one full-width line given data and a format object
# Example format:
#[
#	{"width":10,"data":"home","colour":"white"},
#	{"width":10,"data":"away","colour":"white"}
#]
# Total widths MUST add up to less than (40 - total_rows)
# Width does not include colour code
def tableRow(format, data):
	output = ""
	
	for cell in format:
		if "colour" in cell:
			output += colourCode(cell["colour"])
		
		if "align" in cell:
			align = cell["align"]
		else:
			align = "left"
		
		if "width" not in cell:
			print("tableRow: cell has no defined width")
			return
		
		if "data" in cell:
			if cell["data"] in data:
				rawInput = data[cell["data"]]
				
				if "round" in cell:
					rawInput = round(rawInput,cell["round"])
				
				if len(str(rawInput)) > cell["width"] and rawInput is int:
					rawInput = round(rawInput)
				
				inputText = str(rawInput)
			else:
				print("tableRow: specified data absent")
				return
		elif "text" in cell:
			inputText = cell["text"]
		else:
			print("tableRow: Cell has no data input or text specified")
			return
		
		inputText = charsub(inputText)
		
		if align == "right":
			cellText = inputText[:cell["width"]].rjust(cell["width"])
		elif align == "centre":
			cellText = inputText[:cell["width"]].center(cell["width"])
		else:
			cellText = inputText[:cell["width"]].ljust(cell["width"])
		
		output += cellText
	
	if len(output) > 40:
		print("tableRow: warning, output was longer than 40, truncated")
		output = output[:40]
	
	return output

#print(tableRow(
#	[
#		{"width":16,"data":"home","colour":"cyan"},
#		{"width":4,"text":"v","colour":"white"},
#		{"width":13,"data":"away","colour":"cyan"},
#	],
#	{"home":"Enniskillen","away":"Liverpool","hscore":4,"ascore":6}
#))

def colourCodeReplace(toggle,input,code="\r"):
	if toggle == False:
		return input
	
	if input[0] == "" and code == "\r":
		return code + input[1:]
	else:
		return code + input

def toTeletextBlock(input,maxWidth=40,line=1,variable={}):
	output = []
	previousFinal = ""
	previousAlign = ""
	previousLastLineLen = 0
	
	## BLOCK SETTINGS
	
	if "colour" in input:
		defaultColour = colourCode(input["colour"])
	else:
		defaultColour = colourCode('white')
	
	if "padding" in input:
		padFill = input["padding"]
	else:
		padFill = " "
	
	if "padCol" in input:
		padCol = colourCode(input["padCol"])
	else:
		padCol = " "
	
	if "doubleHeight" in input:
		doubleHeight = input["doubleHeight"]
	else:
		doubleHeight = False
	
	if doubleHeight == True:
		spacing = 2
	else:
		spacing = 1
	
	if "boxed" in input:
		boxed = input["boxed"]
	else:
		boxed = False
	
	if boxed == True:
		maxWidth -= 2
	
	padLen = len(padFill)
	
	if "content" not in input:
		return []
	
	for pos,group in enumerate(input["content"]):
		#### GROUP SETTINGS ####
		
		if (len(input["content"]) - 1) == pos:	# Is this the last group in the block?
			lastGroup = True
		else:
			lastGroup = False
		
		if "align" in group:
			align = group["align"]
		else:
			align = "left"
		
		if "indent" in group:
			indent = group["indent"]
		else:
			indent = 0
		
		if "forceNewLine" in group:
			newLine = group["forceNewLine"]
		else:
			newLine = False
		
		#### FORMATTING SECTION ####
		
		if previousAlign == "left":
			formattedText = textColour(input=group["content"], maxWidth=maxWidth, cursor=previousLastLineLen, indent=indent, forceNewLine=newLine, variable=variable, defaultColour=defaultColour,doubleHeight=doubleHeight)
		else:
			formattedText = textColour(input=group["content"], maxWidth=maxWidth, indent=indent, forceNewLine=newLine, variable=variable, defaultColour=defaultColour,doubleHeight=doubleHeight)
		
		if "postWrapLimit" in group:
			if len(formattedText) >= group["postWrapLimit"]["maxLines"]:
				formattedText = formattedText[:group["postWrapLimit"]["maxLines"]]
				if len(formattedText[group["postWrapLimit"]["maxLines"]-1]) > group["postWrapLimit"]["cutoff"]:
					formattedText[group["postWrapLimit"]["maxLines"]-1] = formattedText[group["postWrapLimit"]["maxLines"]-1][:group["postWrapLimit"]["cutoff"]]
		
		newContent = []
		
		firstContentLine = False
		
		for rowNum,row in enumerate(formattedText):
			#### PADDING SECTION ####
			# Get the line lengths before any padding or additional codes are added
			if rowNum == 0:
				firstLineLen = len(row)
				lastLineLen = firstLineLen	# If there's only one line, first line len == last line len
			else:
				lastLineLen = len(row)	# If there's more than one line, replace it
			
			if len(row) > 0 and firstContentLine == False:	# Is this the first row with content?
				firstContentLine = rowNum
			
			# To pad or not to pad? That is the question:
			# If this is the FIRST LINE of text that's RIGHT or CENTRE ALIGNED (NOT LEFT)
			# OR if this is the LAST LINE of text that's LEFT or CENTRE ALIGNED (NOT RIGHT)
			# If we're in the middle of a line, just pad with spaces (don't want to break up lines)
			if ((rowNum == (len(formattedText) - 1) and align != "right") or (firstContentLine == rowNum and align != "left")) and (maxWidth - len(row)) > 1:
				if align != "right":
					row += padCol
				
				pad = padFill
			else:
				pad = " "
			
			if doubleHeight:
				padLengthSub = len(padCol) + 1
			else:
				padLengthSub = len(padCol)
			
			if align == "left":
				newContent.append(row.ljust(maxWidth - padLengthSub,pad))
			elif align == "centre":
				newContent.append(row.center(maxWidth - padLengthSub,pad))
			elif align == "right":
				newContent.append(padCol + row.rjust(maxWidth - padLengthSub,pad))
		
		groupLines = len(newContent)
		
		for formattedLineNum,formattedLine in enumerate(newContent):
		#### MERGING SECTION ####
			if ((groupLines - 1) == formattedLineNum) and not lastGroup:
				previousAlign = align
				
				# BugFix 2023-06-25: indents break across multiple lines
				# 
				
				if previousLastLineLen == 0:
					previousFinal = (indent * " ") + formattedLine
					previousLastLineLen = indent + lastLineLen
				else:
					previousFinal = previousFinal[:previousLastLineLen] + formattedLine
					previousLastLineLen = previousLastLineLen + lastLineLen
				
				break
			
			if (previousFinal != "") and (formattedLineNum == 0) and (previousAlign == "left") and (align != "centre"):
				spaceFreeLastLen = previousLastLineLen
				currentLen = firstLineLen
				
				if align == "right":
					#lastLen = (len(previousFinal) - firstLineLen) + 1
					
					# BugFix 2023-07-14: Prevent right-aligned text going off the end of the page
					lastLen = (maxWidth - len(formattedLine.strip(padFill+padCol)))
					
				elif align == "left":
					lastLen = previousLastLineLen
				
				if (firstLineLen + spaceFreeLastLen) <= maxWidth:
					output.append({"number":line,"text":colourCodeReplace(boxed,colourCodeReplace(doubleHeight,previousFinal[:lastLen] + formattedLine.strip(padFill+padCol)),'')})
					line += spacing
				else:
					output.append({"number":line,"text":colourCodeReplace(boxed,colourCodeReplace(doubleHeight,previousFinal),'')})
					line += spacing
					output.append({"number":line,"text":colourCodeReplace(boxed,colourCodeReplace(doubleHeight,(indent * " ") + formattedLine),'')})
					line += spacing
			else:
				output.append({"number":line,"text":colourCodeReplace(boxed,colourCodeReplace(doubleHeight,(indent * " ") + formattedLine),'')})
				line += spacing
			
			previousFinal = ""
			previousAlign = ""
			previousLastLineLen = 0
	
	#print(output)
	#print("")
	return output

def textColour(input,maxWidth=20,cursor=0,indent=0,forceNewLine=False,variable={},defaultColour=" ",doubleHeight=False):
	line = 0
	output = [""]
	
	width = maxWidth	# We redefine this here in case we want to do nth line offsets later
	
	if forceNewLine:
		line += 1	# Increment the line counter (ToDo: Double Height needs incremented twice)
		cursor = 0	# Carriage return
		output.append("")	# Create the next row
		width = maxWidth-indent	# Reset the width
	
	for chunk in input:
		colourChanged = True
		
		#### SUBSTITUTION SECTION ####
		# Added 2023-07-14
		
		if "text" not in chunk and "variable" in chunk:
			variable_part = variable
			for path in chunk["variable"]:
				try:
					variable_part=variable_part[path]
				except:
					logging.debug("textColour: Could not find '" + str(path) + "' in listed variable")
					
					variable_part = ""
					continue
			
			focusText = str(variable_part)
		elif "text" not in chunk and "variable" not in chunk:
			print("textColour: Major fault, no usable text in chunk")
			return output
		elif "text" in chunk:
			focusText = str(chunk["text"])
		
		if "colour" in chunk:
			colour = colourCode(chunk["colour"])	# Set the colour code for this bit
		else:
			colour = defaultColour
		
		if "datetimeFormat" in chunk:
			timestamp = float(focusText)
			
			if timestamp > 9999999999:
				timestamp = timestamp/1000
			
			focusText = datetime.utcfromtimestamp(timestamp).strftime(chunk["datetimeFormat"])
		
		if "forceCaps" in chunk:
			focusText = focusText.upper()
		
		focusText = charsub(focusText) # Re-map characters
		
		if "pad" in chunk:
			if chunk["pad"]["align"] == "right":
				focusText = focusText.rjust(chunk["pad"]["width"],chunk["pad"]["fill"])
			elif chunk["pad"]["align"] == "left":
				focusText = focusText.ljust(chunk["pad"]["width"],chunk["pad"]["fill"])
		
		if "limit" in chunk:
			focusText = focusText[:chunk["limit"]]
		
		if "lineOffset" in chunk:
			line += chunk["lineOffset"]	# Increment the line counter (ToDo: Double Height needs incremented twice)
			cursor = 0	# Carriage return
			
			for i in range(chunk["lineOffset"]):
				output.append("")	# Create the next row
			
			colourChanged = True	# Reset the colour
			width = maxWidth-indent	# Reset the width
		
		if "preferNewline" in chunk:
			chunkElement = [focusText]
		else:
			chunkElement = re.split('(.+?(?:\s|\/|\-|$))', focusText)	# Split chunk into words, retaining the delimiter
			# ToDo - make sure the delimiter stays with the word, rather than floating on it's own
		
		for word in chunkElement:
			wordLen = len(word)	# How long is that word?
			
			if wordLen < 1:
				continue
			
			if(wordLen+cursor) >= width+1:	# Is it gonna be too long for this line?
				if wordLen > width:	# Wait, is it longer than the entire line?
					print("textColour: Caught word \"" + word + "\" which is too long to fit in " + str(maxWidth) + " characters")	# "uncaught exception"
					word = word[:width]
					#exit()	# This shouldn't ever happen, but just in case - ToDo: Split up words that are too long to force them to fit
				
				if word == " ":
					continue	# Don't put spaces at the start of new lines
				
				line += 1	# Increment the line counter (ToDo: Double Height needs incremented twice)
				cursor = 0	# Carriage return
				output.append("")	# Create the next row
				colourChanged = True	# Reset the colour
				width = maxWidth-indent	# Reset the width
			
			if colourChanged and "noSpacing" not in chunk:	# Add the colour code again if we need to
				colourChanged = False
				output[line] = output[line] + colour
				
				if doubleHeight == True:
					cursor = cursor + 1	# Need to increment the cursor for colour codes
				else:
					cursor = cursor + 1	# Need to increment the cursor for colour codes
			#else:
			#	output[line] = output[line] + " "	# Otherwise pad with a space
			
			output[line] = output[line] + word	# Add the word to the line
			cursor = cursor + wordLen	# And increment the cursor
	
	return(output)

#print(toTeletextBlock(textBlock6))

#test = filter(None,re.split('(.+?(?:\s|\/|\-|$))', "this is BBC One with language/violence/humiliation/sex/drugs and scott-thomas."))

#print(list(test))