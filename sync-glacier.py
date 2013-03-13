from boto.utils import parse_ts
from boto.glacier import connect_to_region
from boto.glacier.layer2 import Layer2
from boto.glacier.exceptions import UploadArchiveError
import sys
import os
import json
import time

access_key_id = ""
secret_key = ""

# Outputs the config file
def write():
	with open(config, 'w') as f:
		f.write(vault_name + '|' + region + "\n")
		f.write('|'.join(dirs) + "\n")
		f.write(inventory_job + "\n")
		f.write(ls_present + "\n")
		
		for name, data in ls.iteritems():
			f.write(name + "|" + data['id'] + '|' + str(data['last_modified'])  + '|' + str(data['size']) + "\n")

def terminate(code):
	raw_input("\nPress enter to continue...")
	sys.exit(code)

def format_bytes(bytes):
	for x in ['bytes', 'KB', 'MB', 'GB']:
		if bytes < 1024.0:
			return "%3.1f %s" % (bytes, x)
		bytes /= 1024.0
	return "%3.1f %s" % (bytes, 'TB')
	
def format_time(num):
	times = []
	for x in [(60, 'second'), (60, 'minute'), (1e10, 'hour')]:
		if num % x[0] >= 1:
			times.append('%d %s%s' % (num % x[0], x[1], 's' if num % x[0] != 1 else ''))
		num /= x[0]
	times.reverse()
	return ', '.join(times)
	
# Make sure the user passed in a config file
if len(sys.argv) < 2 or not os.path.exists(sys.argv[1]):
	print "Config file not found. Pass in a file with the vault name and the directory to sync on separate lines."
	terminate(1)

# Read the config file
config = sys.argv[1]
with open(config, 'rU') as f:
	vault_info = f.readline().strip().split('|')
	vault_name = vault_info[0]
	region = vault_info[1]
	
	dirs = f.readline().strip().split('|')
	inventory_job = f.readline().strip()
	ls_present = f.readline().strip()
	
	ls = {}
	for file in f.readlines():
		name, id, last_modified, size = file.strip().split('|')
		ls[name] = {
			'id': id,
			'last_modified': int(last_modified),
			'size': int(size)
		}

# Check some of the values in the config file
if not vault_name:
	print "You need to give a vault name and region in the first line of the config file, e.g. `MyVault|us-west-1`."
	terminate(1)

if not len(dirs):
	print r"You need to give the full path to a folder to sync in the second line of the config file, e.g. `C:\backups`. You can list multiple folders, e.g. `C:\backups|D:\backups`"
	terminate(1)

for dir in dirs:
	if not os.path.exists(dir):
		print "Sync directory not found: " + dir
		terminate(1)

# Cool! Let's set up everything.
connect_to_region(vault_info[1], aws_access_key_id=access_key_id, aws_secret_access_key=secret_key)
glacier = Layer2(aws_access_key_id=access_key_id, aws_secret_access_key=secret_key)
vault = glacier.get_vault(vault_name)
print "Beginning job on " + vault.arn

# Ah, we don't have a vault listing yet. 
if not ls_present:

	# No job yet? Initiate a job.
	if not inventory_job:
		inventory_job = vault.retrieve_inventory()
		write()
		print "Requested an inventory. This usually takes about four hours."
		terminate(0)
	
	# We have a job, but it's not finished.
	job = vault.get_job(inventory_job)
	if not job.completed:
		print "Waiting for an inventory. This usually takes about four hours."
		terminate(0)
	
	# Finished!
	try:
		data = json.loads(job.get_output().read())
	except ValueError:
		print "Something went wrong interpreting the data Amazon sent!"
		terminate(1)
	
	ls = {}
	for archive in data['ArchiveList']:
		ls[archive['ArchiveDescription']] = {
			'id': archive['ArchiveId'],
			'last_modified': int(float(time.mktime(parse_ts(archive['CreationDate']).timetuple()))),
			'size': int(archive['Size']),
			'hash': archive['SHA256TreeHash']
		}
		
	ls_present = '-'
	inventory_job = ''
	write()
	print "Imported a new inventory from Amazon."
	
# Let's upload!
os.stat_float_times(False)
try:
	i = 0
	transferred = 0
	time_begin = time.time()
	for dir in dirs:
		print "Syncing " + dir
		files = os.listdir(dir)
		for file in files:
			path = dir + os.sep + file
			
			# If it's a directory, then ignore it
			if not os.path.isfile(path):
				continue
			
			last_modified = int(os.path.getmtime(path))
			size = os.path.getsize(path)
			updating = False
			if file in ls:
			
				# Has it not been modified since?
				if ls[file]['last_modified'] >= last_modified and ls[file]['size'] == size:
					continue
				
				# It's been changed... we should delete the old one
				else:
					vault.delete_archive(ls[file]['id'])
					del ls[file]
					updating = True
					write()
				
			try:
				print file + ": uploading... ",
				id = vault.concurrent_create_archive_from_file(path, file)
				ls[file] = {
					'id': id,
					'size': size,
					'last_modified': last_modified
				}
				
				write()
				i += 1
				transferred += size
				if updating:
					print "updated."
				else:
					print "done."
			except UploadArchiveError:
				print "FAILED TO UPLOAD."
			
finally:
	elapsed = time.time() - time_begin
	print "\n" + str(i) + " files successfully uploaded."
	print "Transferred " + format_bytes(transferred) + " in " + format_time(elapsed) + " at rate of " + format_bytes(transferred / elapsed) + "/s."
	terminate(0)