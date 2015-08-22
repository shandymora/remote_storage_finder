import requests
import time
import re

from multiprocessing.pool import ThreadPool
from django.conf import settings

from graphite.intervals import Interval, IntervalSet
from graphite.node import LeafNode, BranchNode
from graphite.readers import FetchInProgress

import json

import logging
from logging.handlers import TimedRotatingFileHandler
logger = logging.getLogger('graphite_remote')

REMOTE_MAX_REQUESTS = 10
REMOTE_REQUEST_POOL = ThreadPool(REMOTE_MAX_REQUESTS)

class Utils(object):

    def get_remote_url(self, remote_uri, url):
        full_url = "%s/%s" % (remote_uri, url)
        return requests.get(full_url)

    def post_remote_url(self, remote_uri, url, data):
        full_url = "%s/%s" % (remote_uri, url)
        return requests.post(full_url, data)
    
class RemoteReader(object):
    __slots__ = ('remote_uri', 'metric_name')
    supported = True

    def __init__(self, remote_uri, metric_name):
        self.remote_uri = remote_uri
        self.metric_name = metric_name

    def get_intervals(self):
        return IntervalSet([Interval(0, time.time())])

    def fetch(self, startTime, endTime):
        def get_data():
            
            utils = Utils()
            
            post_data_string = "target=%s&from=%s&until=%s&format=raw" % (self.metric_name, startTime, endTime)
            
            post_response = utils.post_remote_url(self.remote_uri, 'render', data=post_data_string)
            
            meta_data, datapoints_string = post_response.text.rstrip().split("|")
            
            
            datapoints = []
            datapoints_string = datapoints_string.split(",")
            for point in datapoints_string:
                if point != 'None':
                    datapoints.append( float(point) )
                else:
                    datapoints.append( None )
                        
            key_string, start_string, end_string, step = meta_data.split(",")
            step = int(step)
                        
            datapoints_length = len(datapoints)
            
            if datapoints_length == 0:
                time_info = (startTime, endTime, 1)
                datapoints = []
                return (time_info, datapoints)
            else:
                if datapoints_length == 1:
                    time_info = (startTime, endTime, 1)
                    return (time_info, datapoints)
                else:
                    
                    # 2. Fill time info table    
                    time_info = (startTime, endTime, step)
                       
                    return (time_info, datapoints)

        job = REMOTE_REQUEST_POOL.apply_async(get_data)

        return FetchInProgress(job.get)
    

class RemoteFinder(object):
    def __init__(self, remotes=[]):
        self.remotes = settings.REMOTE_STORAGE_FINDERS
        self._setup_logger(settings.REMOTE_LOG_LEVEL, settings.REMOTE_LOG_FILE)
    
    def _setup_logger(self, level, log_file):
        """ Setup log level and logfile if unset"""
        level = getattr(logging, level.upper())
        logger.setLevel(level)
        formatter = logging.Formatter(
            '[%(levelname)s] %(asctime)s - %(module)s.%(funcName)s() - %(message)s')
        handler = logging.StreamHandler()
        logger.addHandler(handler)
        handler.setFormatter(formatter)
        if not log_file:
            return
        try:
            handler = TimedRotatingFileHandler(log_file)
        except IOError:
            logger.error("Could not write to %s, falling back to stdout", log_file)
        else:
            logger.addHandler(handler)
            handler.setFormatter(formatter)
    
    def _strip_prefix(self, prefix, pattern):
        if pattern.startswith(prefix):
            return pattern[len(prefix):]
        else:
            return pattern
            
    def find_nodes(self, query):
        # find some paths matching the query, then yield them
        utils = Utils()
       
        for remote in self.remotes:
            # Validate settings
            if 'REMOTE_URL' not in remote:
                logger.error("Missing REMOTE_URL, ensure key exists in dict REMOTE_STORAGE_FINDERS")
                return
            else:
                url = remote["REMOTE_URL"]
                
            if ('REMOTE_WHITELIST' not in remote):
                whitelist = [ '.*' ]
            else:
                whitelist = remote["REMOTE_WHITELIST"]
                
            prefix_parts = []
            if ('REMOTE_PREFIX' in remote):
                prefix_parts = remote["REMOTE_PREFIX"].split('.')
                
                logger.info("prefix_parts: %s", prefix_parts)
                
                if len(prefix_parts) > 0:
                    prefix_string = ''
                    for part in prefix_parts:
                        if part != '':
                            prefix_string = prefix_string + part + '.'
                            
                            logger.info("prefix_string: %s, pattern: %s", prefix_string, query.pattern)
                            
                            if ( re.match('^'+prefix_string.rstrip('.'), query.pattern) == None):
                                logger.info("Yielding PREFIX BranchNode")
                                yield BranchNode(prefix_string.rstrip('.'))
                                return                        
                    
            if len(prefix_parts) > 0:
                pattern = self._strip_prefix(remote["REMOTE_PREFIX"], query.pattern)
            else:
                pattern = query.pattern
            
            metrics = utils.get_remote_url(url, "metrics/find?query="+pattern).json()
            
            # Parse metric names against any whitelists/blacklists
            for check_pattern in whitelist:
                for metric_name in metrics:            
                   if ( re.match(check_pattern, metric_name["id"]) != None ):
                        path = ''
                        
                        
                        
                        
                        if metric_name["expandable"] == 1:
                            if remote["REMOTE_PREFIX"] != '':
                                path = remote["REMOTE_PREFIX"] + metric_name["id"]
                                logger.info("BranchNode: %s", path)
                                logger.info("Name: %s", path.split('.')[-1])
                                yield BranchNode(path)
                            else:
                                yield BranchNode(metric_name["id"])
                        else:
                            if remote["REMOTE_PREFIX"] != '':
                                path = remote["REMOTE_PREFIX"] + metric_name["id"]
                                logger.info("LeafNode: %s", path)
                                yield LeafNode(path, RemoteReader(url, metric_name["id"]))
                            else:
                                yield LeafNode(metric_name["id"], RemoteReader(url, metric_name["id"]))
                                