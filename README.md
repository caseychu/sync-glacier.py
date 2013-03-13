sync-glacier.py
===============

A Python script to easily sync a directory with a vault on Amazon Glacier. This makes it easy to upload a directory of backups, for example, into a vault. This script requires [`boto`](https://github.com/boto/boto) (see their instructions on how to install it).

To use `sync-glacier.py`, first edit `sync-glacier.py` and put in your [Amazon Web Services credentials](https://portal.aws.amazon.com/gp/aws/securityCredentials):
```
access_key_id = ""
secret_key = ""
```

Then, create a configuration file (see `sample.job`) with the vault name, region, and directories you want to sync, separated with `|`.

Run the script and pass in the config file with the command:
```
sync-glacier.py job_file.job
```

On the first run, it will download an inventory of the vault. This takes about four hours, after which you'll need to run the script again. The script will upload the files in the given directory that don't already appear in the vault (or that have been updated since your last upload). Once that's done, every time you want to sync changes to your vault, simply run the script again. It'll detect what's been updated and only upload those files.
