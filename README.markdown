## Remote Storage Finder

A Graphite plugin for aggregating remote Graphite-web servers under a single metric hierarchy.

### Graphite-web configuration
Example settings below:

local_settings.py
```
STORAGE_FINDERS = (
    'remote_storage_finder.RemoteFinder',
)
REMOTE_STORAGE_FINDERS = [
    {
        'REMOTE_URL' : 'http://prd_graphite.int.shandymora.com',
        'REMOTE_WHITELIST' : [
            '^env\.prd\.applications',
            '^env\.prd\.infrastructure'
        ]
    },
    {
        'REMOTE_URL' : 'http://dev_graphite.int.shandymora.com',
        'REMOTE_WHITELIST' : [
            '^env\.dev\.applications',
            '^env\.dev\.infrastructure'
        ]
    }
]
REMOTE_LOG_LEVEL = 'info'
REMOTE_LOG_FILE = '/opt/graphite/storage/log/webapp/remote_storage_finder.log'
```
### Acknowledgements
Significant inspiration and code examples were used from [KairosdbGraphiteFinder](https://github.com/Lastik/KairosdbGraphiteFinder)
and [graphite-cyanite](https://github.com/brutasse/graphite-cyanite).  
