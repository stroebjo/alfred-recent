from subprocess import Popen, PIPE
from os.path import expanduser, dirname, basename, isfile, splitext
import json
import sys
import re

application_bundle_id = sys.argv[1]
file_search_regex     = False

if len(sys.argv) == 3:
	file_search_regex = sys.argv[2]

LSSfile = expanduser('~') + '/Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.ApplicationRecentDocuments/'
LSSfile += application_bundle_id + '.sfl'


# Inline AppleScipt JavaScript (JXA) to fetch the LSSharedFileList.
#
# See for JXA code https://ryanmo.co/2015/10/31/list-server-favorites-in-os-x-1011-el-capitan/
# See for analysys of .sfl files http://michaellynn.github.io/2015/10/24/apples-bookmarkdata-exposed/
#
scpt = """
items = $.NSKeyedUnarchiver.unarchiveObjectWithFile('%s')

items = items.objectForKey('items')
itemsCount = items.count
var to_ret = []

while (itemsCount--){
	var item = items.objectAtIndex(itemsCount)

	var bm = {}

	bm.order = item.order
	bm.url  = $.CFStringGetCStringPtr(item.URL.absoluteString, 0)
	bm.url = decodeURI(bm.url)

	// Convert reference into actual string
	// http://stackoverflow.com/q/33314614/723769
	//
	// This method seems to fail some times (with an filename like `.htaccess`), so wrap
	// it in an try-catch block
	try {
		bm.name = $.CFStringGetCStringPtr(item.name, 0)
	} catch(err) {
		bm.name = null
	}

	to_ret.push(bm)
}
//to_ret
JSON.stringify(to_ret)
""" % LSSfile

# Run JXA and parse returned JSON into `items`
args = ['-l', 'JavaScript']
p = Popen(['osascript'] + args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
stdout, stderr = p.communicate(scpt)
items = json.loads(stdout)
items_ordered = sorted(items, key=lambda k: k['order'])

# Start JSON
# https://www.alfredapp.com/help/workflows/inputs/script-filter/json/
json_return = {'items': []}

# if we have no recent files, put in a shortcut to open app
if len(items) == 0:
	scpt = """
	tell application "Finder"
		POSIX path of (application file id "%s" as alias)
	end tell""" % application_bundle_id

	p2 = Popen(['osascript'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
	stdout, stderr = p2.communicate(scpt)
	app_path = stdout.strip()

	if app_path:
		json_item = {
			'type': 'file',
			'arg': app_path,
			'title': 'Sorry, no recent files found.',
			'subtitle': 'Create a new file?',

			'icon': {
				'type': 'fileicon',
				'path': app_path
			}
		}

		json_return['items'].append(json_item)

for item in items_ordered:
	file_path  = item['url'].replace("file://", "").rstrip('/')
	clean_path = dirname(file_path).replace(expanduser("~"), "~")
	file_name  = basename(file_path)

	# if name could not be determined from .sfl use actual filename
	if not item['name']:
		item['name'] = file_name

	# check if file exists
	#if not isfile(file_path):
	#	continue

	# do we have a search query and does it match?
	if file_search_regex and not re.search(file_search_regex, file_path, re.IGNORECASE):
		continue

	json_item = {
		'type': 'file',
		'arg': file_path,
		'title': item['name'],
		'subtitle': clean_path,

		'icon': {
			'type': 'fileicon',
			'path': file_path
		}
	}

	json_return['items'].append(json_item)


print json.dumps(json_return)

