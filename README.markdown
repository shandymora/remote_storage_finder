local_settings.py
```
STORAGE_FINDERS = (
    'remote_storage_finder.RemoteFinder',
)
REMOTE_URL = 'http://graphite.shandymora.com'
REMOTE_LOG_LEVEL = 'info'
REMOTE_LOG_FILE = '/opt/graphite/storage/log/webapp/remote_finder.log'
REMOTE_WHITELIST = [
	'^collectdvm-host'
]
REMOTE_PREFIX = ''
```
