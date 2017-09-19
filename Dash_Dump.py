#!/usr/bin/env python2
# -*- coding: utf-8 -*-
__author__ = 'tao'

import os
import sys
from bs4 import BeautifulSoup
from urllib2 import urlopen, URLError, HTTPError
from urlparse import urlparse, urljoin
import isodate
import re

def dlfile(local_path, url):
    if os.path.isfile(local_path):
        print "Exist " + url
        return
    try:
        tmp_path = local_path + '.tmp'
        f = urlopen(url)
        with open(tmp_path, "wb") as local_file:
            local_file.write(f.read())

        local_file.close()
        os.rename(tmp_path, local_path)
        print "OK " + url
    except HTTPError, e:
        print "HTTP Error:", e.code, url
    except URLError, e:
        print "URL Error:", e.reason, url

def dlsegment(url, baseurl):
    #print "URL " + url
    #print "BaseURL " + baseurl
    parts1 = urlparse(url)
    parts2 = urlparse(baseurl)
    if parts1[1] != parts2[1]:
        local_path = parts1[1] + parts1[2]
    else:
        local_path = os.path.relpath(parts1[2], parts2[2])  #fixme
    dirname = os.getcwd() + '/' + os.path.dirname(local_path)
    if not os.path.exists(dirname) and dirname != '':
        os.makedirs(dirname)
    dlfile(local_path, url)

def replace_var(str1, name, val, fmt = '%s'):
    exp = re.compile("\$%s([^\$]*)\$" % name)
    while True:
        matched = exp.search(str1)
        if matched:
            if matched.group(1):
                fmt2 = matched.group(1)
            else:
                fmt2 = fmt
            if 'd' in fmt2:
                str1 = str1.replace(matched.group(0), fmt2 % int(val))
            elif 's' in fmt2:
                str1 = str1.replace(matched.group(0), fmt2 % str(val))
        else:
            break
    return str1

def read_attr(node, name, func = int, default = 1):
    if name in node.attrs:
        return func(node.attrs[name])
    else:
        return func(default)

def read_isoduration(node, name, default = 0.0):
    if name in node.attrs:
        return isodate.parse_duration(node.attrs[name]).total_seconds()
    else:
        return default

def read_baseurl(node, default):
    BaseURL = node.find('BaseURL', recursive=False)
    if BaseURL:
        return urljoin(default, BaseURL.text)
    else:
        return default

if len(sys.argv) < 2:
    print "%s url" % sys.argv[0]
    quit()
else:
    ManifestURL = sys.argv[1]
ManifestBase = urljoin(ManifestURL, '.')
print ManifestBase
manifest = os.path.basename(ManifestURL)
dlfile(manifest, ManifestURL)
xml = BeautifulSoup(open(manifest).read(), features="xml")
MPD = xml.find('MPD')
mediaPresentationDuration = read_isoduration(MPD, 'mediaPresentationDuration')
print "Duration %fs" % mediaPresentationDuration
MPDBaseURL = read_baseurl(MPD, ManifestURL)
print "MPDBase " + MPDBaseURL
for Period in MPD.findAll('Period'):
    PeriodDuration = read_isoduration(Period, 'duration', mediaPresentationDuration)
    PeriodBaseURL = read_baseurl(Period, MPDBaseURL)
    for AdaptationSet in Period.findAll('AdaptationSet'):
        AdaptationSetBaseURL = read_baseurl(AdaptationSet, PeriodBaseURL)
        SegmentTemplate = AdaptationSet.find('SegmentTemplate')
        if SegmentTemplate:
            startNumber = read_attr(SegmentTemplate, 'startNumber')
            duration = read_attr(SegmentTemplate, 'duration')
            timescale = read_attr(SegmentTemplate, 'timescale')
            media = urljoin(AdaptationSetBaseURL, SegmentTemplate.attrs['initialization'])
            for Representation in AdaptationSet.findAll('Representation'):
                bandwidth = read_attr(Representation, 'bandwidth')
                representationId = read_attr(Representation, 'id', str)
                media_path = replace_var(media, 'Bandwidth', bandwidth)
                media_path = replace_var(media_path, 'RepresentationID', representationId)
                dlsegment(media_path, ManifestBase)
            media = urljoin(AdaptationSetBaseURL, SegmentTemplate.attrs['media'])
            SegmentTimeline = AdaptationSet.find('SegmentTimeline')
            if SegmentTimeline:
                time = 0
                for s in SegmentTimeline.findAll('S'):
                    r = read_attr(s, 'r', default = 0)
                    d = read_attr(s, 'd', default = duration)
                    while r >= 0:
                        for Representation in AdaptationSet.findAll('Representation'):
                            bandwidth = read_attr(Representation, 'bandwidth')
                            representationId = read_attr(Representation, 'id', str)
                            media_path = replace_var(media, 'Bandwidth', bandwidth)
                            media_path = replace_var(media_path, 'RepresentationID', representationId)
                            media_path = replace_var(media_path, 'Time', time)
                            dlsegment(media_path, ManifestBase)
                        time += d
                        r -= 1
            else:
                time = 0
                number = startNumber
                while time < PeriodDuration * timescale:
                    for Representation in AdaptationSet.findAll('Representation'):
                        bandwidth = read_attr(Representation, 'bandwidth')
                        representationId = read_attr(Representation, 'id', str)
                        media_path = replace_var(media, 'Bandwidth', bandwidth)
                        media_path = replace_var(media_path, 'RepresentationID', representationId)
                        media_path = replace_var(media_path, 'Number', number)
                        dlsegment(media_path, ManifestBase)
                    time += duration
                    number += 1
        else:
            for Representation in AdaptationSet.findAll('Representation'):
                RepresentationBaseURL = read_baseurl(Representation, AdaptationSetBaseURL)
                media = RepresentationBaseURL
                if media != '':
                    dlsegment(media, ManifestBase)

BaseURLs = MPD.findAll('BaseURL')
for BaseURL in BaseURLs:
    parts1 = urlparse(BaseURL.text)
    if parts1[0] != '':
        parts2 = urlparse(ManifestBase)
        if parts1[1] != parts2[1]:
            BaseURL.string = parts1[1] + parts1[2]
        else:
            BaseURL.string = os.path.relpath(parts1[2], parts2[2]) + '/'
with open("dump_" + manifest, "wb") as file:
    file.write(xml.prettify("utf-8"))
