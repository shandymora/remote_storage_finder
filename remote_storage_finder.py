import sys, os
    
import re
import requests
import time
import math

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

class RemoteNode(object):
    def __init__(self):
        self.child_nodes = []
    
    #Node is leaf, if it has no child nodes.
    def isLeaf(self):
        return len(self.child_nodes) == 0
    
    #Add child node to node.
    def addChildNode(self, node):
        self.child_nodes.append(node)
    
    #Get child node with specified name
    def getChild(self, name):
        for node in self.child_nodes:
            if node.name == name:
                return node
        return None
    
    def getChildren(self):
        return self.child_nodes

    
class RemoteTree(RemoteNode):
    pass
            

class RemoteRegularNode(RemoteNode):
    def __init__(self, name):
        RemoteNode.__init__(self)
        self.name = name
    
    def getName(self):
        return self.name
 
                
class Utils(object):

    def get_remote_url(self, remote_uri, url):
        full_url = "%s/%s" % (remote_uri, url)
#        return requests.get(full_url).json()
        return requests.get(full_url)

    def post_remote_url(self, remote_uri, url, data):
        full_url = "%s/%s" % (remote_uri, url)
#        return requests.post(full_url, data).json()
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
            
#            for i in range( len(datapoints)):
#                message = '%s:%s' % (i, datapoints[i])
                
#            logger.info("message: %s", message)
            
            key_string, start_string, end_string, step = meta_data.split(",")
            step = int(step)
            
#            logger.info("key_string:%s", key_string)
#            logger.info("startTime:%s", startTime)
#            logger.info("endTime:%s", endTime)
#            logger.info("step:%s", step)
            
            datapoints_length = len(datapoints)
 #           logger.info("datapoints_length:%s", datapoints_length)
            
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
    def __init__(self, remote_uri=None, whitelist=[], prefix=''):
        self.remote_uri = settings.REMOTE_URL.rstrip('/')
        self._setup_logger(settings.REMOTE_LOG_LEVEL, settings.REMOTE_LOG_FILE)
        self.whitelist = settings.REMOTE_WHITELIST
        self.prefix = settings.REMOTE_PREFIX
    
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
            logger.info("Logging setup successfully")
    # Fills tree of metrics out from flat list
    # of metrics names, separated by dot value
    def _fill_remote_tree(self, metric_names):
        tree = RemoteTree()
        
        for metric_name in metric_names:
            name_parts = metric_name.split('.')
            
            cur_parent_node = tree
            cur_node = None
            
            for name_part in name_parts:
                cur_node = cur_parent_node.getChild(name_part)
                if cur_node == None:
                    cur_node = RemoteRegularNode(name_part)
                    cur_parent_node.addChildNode(cur_node)
                cur_parent_node = cur_node
        
        return tree
    
    
    def _find_nodes_from_pattern(self, remote_uri, pattern):
        query_parts = []
        for part in pattern.split('.'):
            part = part.replace('*', '.*')
            part = re.sub(
                r'{([^{]*)}',
                lambda x: "(%s)" % x.groups()[0].replace(',', '|'),
                part,
            )
            query_parts.append(part)
        utils = Utils()
        
        
        #Request for metrics
        metric_names = []
        get_metric_names_response = utils.get_remote_url(remote_uri, "metrics/index.json").json()
        
        # Parse metric names against any whitelists/blacklists
        for check_pattern in self.whitelist:
            for metric_name in get_metric_names_response:
                if ( re.match(check_pattern, metric_name) != None ):
#                    if ( self.prefix != '' ):
#                        metric_names.append(self.prefix + metric_name)
#                    else:
                    metric_names.append(metric_name)
        
        #Form tree out of them
        metrics_tree = self._fill_remote_tree(metric_names)    
        
        for node in self._find_remote_nodes(remote_uri, query_parts, metrics_tree):
            yield node
    
    def _find_remote_nodes(self, remote_uri, query_parts, current_branch, path=''):
        query_regex = re.compile(query_parts[0]+'$')
        for node, node_data, node_name, node_path in self._get_branch_nodes(remote_uri, current_branch, path):
            dot_count = node_name.count('.')
    
            if dot_count:
                node_query_regex = re.compile(r'\.'.join(query_parts[:dot_count+1]))
            else:
                node_query_regex = query_regex
    
            if node_query_regex.match(node_name):
                if len(query_parts) == 1:
                    yield node
                elif not node.is_leaf:
                    for inner_node in self._find_remote_nodes(
                        remote_uri,
                        query_parts[dot_count+1:],
                        node_data,
                        node_path,
                    ):
                        yield inner_node
    
    
    def _get_branch_nodes(self, remote_uri, input_branch, path):
        results = input_branch.getChildren()
        if results:
            if path:
                path += '.'
                
            branches = [];
            leaves = [];
            
            for item in results:
                if item.isLeaf():
                    leaves.append(item)
                else:
                    branches.append(item)
            
            if (len(branches) != 0):
                for branch in branches:
                    node_name = branch.getName()
                    node_path = path + node_name
                    yield BranchNode(node_path), branch, node_name, node_path
            if (len(leaves) != 0):
                for leaf in leaves:
                    node_name = leaf.getName()
                    node_path = path + node_name
                    reader = RemoteReader(remote_uri, node_path)
                    yield LeafNode(node_path, reader), leaf, node_name, node_path

    def find_nodes(self, query):
        logger.info("query %s", query.pattern)
        
        for node in self._find_nodes_from_pattern(self.remote_uri, query.pattern):
            yield node