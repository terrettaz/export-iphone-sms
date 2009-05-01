#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
__version__ = "$Revision: 0.1 $"
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
  
  Exit status code:
    EXIT_SUCCESS = 0
    EXIT_ERROR = 1
    EXIT_ERROR_QUIET = 2
    EXIT_ERROR_EXPORTER = 3
    EXIT_ERROR_NOT_FOUND = 4
  
  Example:
    export-iphone-sms txt
    export-iphone-sms -E latin1 txt > sms.txt
    export-iphone-sms -b /path/to/backup/copy csv > sms.csv
"""

import os, sys
import getopt
import sqlite3
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

class Exporter:
    
    def __init__(self, sqlite_db, encoding='utf8'):
        self.sqlite_db = sqlite_db
        self.conn = sqlite3.connect(sqlite_db)
        self.data = None
        self.fields = ('rowid', 'date', 'address', 'text', 'flags')
        self.encoding = encoding
    
    def __open_cursor(self):
        c = self.conn.cursor()
        c.execute(
            'select %s from message order by rowid' % \
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
    def try_db_file(path):
        conn = sqlite3.connect(path)
        c = conn.cursor()
        try:
            c.execute('select rowid, address, text, flags from message')
            ret = True
        except sqlite3.OperationalError:
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

def parse_argv(argv):
    try:
        opts, args = getopt.getopt(argv[1:], 'E:b:qh')
    except getopt.GetoptError:
        usage()
        
    global quiet, encoding, backup_dir
    for o, v in opts:
        if o == '-E':
            encoding = v
        if o == '-q':
            quiet = True
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
            for f in choices:
                i += 1
                log('%(i)d. %(f)s' % locals(), 4)
                
            log('q. quit', 4)
            log('choice: ', 4, False)
            choice = sys.stdin.readline().lower()[:-1] # escape new line
            if choice == 'q':
                return choice
            elif int(choice) >= 0 and int(choice) <= i:
                return choice
        except:
            log('not a number',4)

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
                    if Exporter.try_db_file(filepath):
                        path.append(filepath)
    
    if len(path) == 0:
        log('not found', 3)
        sys.exit(EXIT_ERROR_NOT_FOUND)
    elif len(path) > 1:
        choice = get_menu_choice('%d sms databases found, pick up one :[0, %d] ' % \
            (len(path), (len(path)-1)), path, quiet)
        if choice == 'q': sys.exit(EXIT_SUCCESS)
        path = path[int(choice)]
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