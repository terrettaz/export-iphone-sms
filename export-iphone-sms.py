#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

version = '0.2'

__version__ = "$Revision: %s $" % version
__author__ = "Pierrick Terrettaz"
__date__ = "2009-04-27"

desc = """SMS Exporter from iPhone backup

  * Locate SMS SQLite database in iphone backup dir recursively:
    ~/Library/Application Support/MobileSync
  * Read file and export the file in a readable format.
    format supported : 
      - txt : Text plain format
      - csv : Exchangable format as text plain
      - xml : not yet implemented

  Usage: export-iphone-sms [options] format
      format: txt, csv
      options
        -h              : print this help
        -E <encoding>   : encoding (default utf8)
        -q              : quiet    (default false)
        -b <backup_dir> : backup_dir (default see upper)
        -v              : print version
        -c              : check last version
  
  Exit status code:
    EXIT_SUCCESS = 0
    EXIT_ERROR = 1
    EXIT_ERROR_QUIET = 2
    EXIT_ERROR_EXPORTER = 3
    EXIT_ERROR_NOT_FOUND = 4
    EXIT_ERROR_VERSION_CHECK = 5
  
  Example:
    export-iphone-sms txt
    export-iphone-sms -E latin1 txt > sms.txt
    export-iphone-sms -b /path/to/backup/copy csv > sms.csv
"""

import os, sys
import getopt
import sqlite3 as db # abstraction of database
import csv
from datetime import datetime

# global variables
quiet = False
encoding = 'utf8'
backup_dir = '%s/Library/Application Support/MobileSync' % os.path.expanduser('~')

EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_ERROR_QUIET = 2
EXIT_ERROR_EXPORTER = 3
EXIT_ERROR_NOT_FOUND = 4
EXIT_ERROR_VERSION_CHECK = 5

class Exporter:
    
    def __init__(self, sqlite_db, encoding='utf8'):
        self.sqlite_db = sqlite_db
        self.conn = db.connect(sqlite_db)
        self.data = None
        self.fields = ('rowid', 'date', 'address', 'text', 'flags')
        self.encoding = encoding
    
    def __open_cursor(self):
        c = self.conn.cursor()
        c.execute(
            'select %s from message where text is not null order by rowid' % \
            reduce(lambda x, y: '%s, %s' % (x,y), self.fields))
        return c

    def __fetch_message(self, row):
        data = {}
        i = 0
        for field in self.fields:
            if field == 'text':
                data[field] = row[i].encode(self.encoding)
            else:
                data[field] = row[i]
            i += 1
        return data
            
    def preload(self):
        self.data = []
        c = self.__open_cursor()
        for row in c:
            self.data.append(self.__fetch_message(row))
        c.close()
        log('database preloaded')
    
    def __loop_messages(self, callback):
        count = 0
        if self.data == None:
            c = self.__open_cursor()
            for row in c:
                callback(self.__fetch_message(row))
                count += 1
            c.close()
        else:
            count = len(self.data)
            for row in self.data:
                callback(row)
        return count
    
    def export_txt(self, message):
        if message['flags'] == 2:
            pre = 'form'
        else:
            pre = 'to'
        date = datetime.fromtimestamp(message['date'])
        
        self.needle.write('\n')
        self.needle.write('message %d %s %s \n' % \
            (message['rowid'], pre, message['address']))
        self.needle.write('   %s\n' % date)
        self.needle.write('   %s\n' % message['text'])
        self.needle.write('---------\n')
    
    def export_csv(self, message):
        writer = csv.writer(self.needle, delimiter=';', quoting=csv.QUOTE_ALL)
        writer.writerow(message.values())
    
    def export(self, type='txt', exporter=None):
        if exporter == None:
            try: 
                exporter = getattr(self, "export_%s" % type )
            except AttributeError:
                log('Error: no exporter for "%s"' % type)
                sys.exit(EXIT_ERROR_EXPORTER)
            
        self.needle = sys.stdout
        count = self.__loop_messages(exporter)
        log('export finished, %(count)d sms' % locals())
    
    def close(self):
        self.conn.close()
    
    @staticmethod
    def get_last_sms(path):
        conn = db.connect(path)
        c = conn.cursor()
        try:                # v count(*) is not standard in all databases
            c.execute('select count(*), rowid, date, address, text, flags from message where text is not null order by date desc')
            row = c.fetchone()
            if row != None and row[0] != None and row[0] > 0:
                ret = (row[0], row[2])
            else:
                ret = False
        except db.OperationalError:
            ret = False
        c.close()
        conn.close()
        return ret

def usage(status=EXIT_ERROR):
    global desc
    sys.stderr.write(desc)
    sys.exit(status)

def log(string, indent=2, newline=True):
    global quiet
    if quiet:
        return
    if indent > 0:
        sys.stderr.write('-')
        indent -= 1
        log(string, indent, newline)
    else:
        sys.stderr.write('> %(string)s' % locals())
        if newline:
            sys.stderr.write('\n')

def get_last_version():
    url = 'http://wiki.github.com/terrettaz/export-iphone-sms/version'
    try:
        import urllib
        import re
        page = urllib.urlopen(url).read()
        groups = re.findall('<p>current version: ([0-9\.]+)</p>', page)
        if len(groups) == 1:
            return groups[0]
        else:
            raise Exception()
        
    except:
        log('unable to check last version on "%(url)s"' % locals())
        sys.exit(EXIT_ERROR_VERSION_CHECK)

def parse_argv(argv):
    try:
        opts, args = getopt.getopt(argv[1:], 'E:b:qhvc')
    except getopt.GetoptError:
        usage()
        
    global quiet, encoding, backup_dir, version
    for o, v in opts:
        if o == '-E':
            encoding = v
        if o == '-q':
            quiet = True
        if o == '-v':
            log('version: %s' % version)
            sys.exit(EXIT_SUCCESS)
        if o == '-c':
            log('your version: %s' % version)
            log('last available version: %s' % get_last_version())
            sys.exit(EXIT_SUCCESS)
        if o == '-b':
            backup_dir = v
        if o == '-h':
            usage(EXIT_SUCCESS)
    
    if len(args) < 1:
        usage()

    format = args[0]
    return (format, encoding, backup_dir, quiet)

def get_menu_choice(text, choices, quiet):
    if quiet:
        sys.stderr.write(
            'Error: cannot export in quiet mode, more than one sms database found\n')
        sys.exit(EXIT_ERROR_QUIET)
    
    log(text,3)
    while True:
        try:
            i = -1
            for f, sms in choices:
                count = sms[0]
                date = datetime.fromtimestamp(sms[1])
                i += 1
                log('%(i)d. %(count)d messages, latest at %(date)s' % locals(), 4)
            
            log('q. quit', 4)
            log('choice: ', 4, False)
            choice = sys.stdin.readline().lower()[:-1] # escape new line
            if choice == 'q':
                return choice
            elif int(choice) >= 0 and int(choice) <= i:
                return choice
        except Exception, e:
            log(e)
            log('not a number',4)
            break

def main(argv):
    format, encoding, backup_dir, quiet = parse_argv(argv)
    
    path = []
    log('locating sms database..')
    
    for root, dirs, files in os.walk(backup_dir):
        for f in files:
            if f.endswith('.mddata'):
                filepath = os.path.join(root, f)
                db_file = open(filepath)
                content = db_file.read(15)
                if content == 'SQLite format 3':
                    last_sms = Exporter.get_last_sms(filepath)
                    if last_sms:
                        path.append((filepath, last_sms))
    
    if len(path) == 0:
        log('not found', 3)
        sys.exit(EXIT_ERROR_NOT_FOUND)
    elif len(path) > 1:
        choice = get_menu_choice('%d sms databases found, pick up one :[0, %d] ' % \
            (len(path), (len(path)-1)), path, quiet)
        if choice == 'q': sys.exit(EXIT_SUCCESS)
        path = path[int(choice)][0]
    else:
        path = path[0]
        log('found in "%s"' % path, 3)
    
    exporter = Exporter(path, encoding)
    exporter.preload()
    exporter.export(type=format)
    exporter.close()
    
    return EXIT_SUCCESS
    
if __name__ == "__main__":
    sys.exit(main(sys.argv))