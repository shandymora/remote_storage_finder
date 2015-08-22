Example settings below:

local_settings.py
```
STORAGE_FINDERS = (
    'remote_storage_finder_v2.RemoteFinder',
)
REMOTE_STORAGE_FINDERS = [
    {
        'REMOTE_URL' : 'http://graphite01.shandymora.com',
        'REMOTE_WHITELIST' : [
            '^collectdvm-host',
            '^servers\.'
        ]
    },
    {
        'REMOTE_URL' : 'http://graphite02.shandymora.com',
        'REMOTE_WHITELIST' : [
            '^carbon'
        ]
    }
]
REMOTE_LOG_LEVEL = 'info'
REMOTE_LOG_FILE = '/opt/graphite/storage/log/webapp/remote_storage_finder.log'
```
