####
# 02/2006 Will Holcomb <wholcomb@gmail.com>
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
"""
Enables the use of multipart/form-data for posting forms
"""

import sys

'''
Inspirations:
  Upload files in python:
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/146306
  urllib2_file:
    Fabien Seisen: <fabien@seisen.org>

Example:
  import MultipartPostHandler, urllib2, cookielib

  cookies = cookielib.CookieJar()
  opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookies),
                                MultipartPostHandler.MultipartPostHandler)
  params = { "username" : "bob", "password" : "riviera",
             "file" : open("filename", "rb") }
  opener.open("http://wwww.bobsite.com/upload/", params)

Further Example:
  The main function of this file is a sample which downloads a page and
  then uploads it to the W3C validator.
'''

import urllib
import urllib2
import mimetools, mimetypes
import os, stat, hashlib
from core.data.fuzzer.fuzzer import string_file

class Callable:
    def __init__(self, anycallable):
        self.__call__ = anycallable

# Controls how sequences are uncoded. If true, elements may be given multiple values by
#  assigning a sequence.
doseq = 1

class MultipartPostHandler(urllib2.BaseHandler):
    handler_order = urllib2.HTTPHandler.handler_order - 10 # needs to run first

    def http_request(self, request):
        data = request.get_data()
        
        to_str = lambda _str: _str.encode('utf-8') if type(_str) \
                                is unicode else _str
        
        if data and not isinstance(data, basestring):
            v_files = []
            v_vars = []
            
            try:
                for pname in data:
                    # Added to support repeated parameter names
                    enc_pname = to_str(pname)
                    for elem in data[pname]:
                        if type(elem) == file:
                            if not elem.closed:
                                v_files.append((enc_pname, elem))
                            else:
                                v_vars.append((enc_pname, ''))
                        elif hasattr(elem, 'isFile'):
                            v_files.append((enc_pname, elem))
                        else:
                            # Ensuring we actually send a string
                            elem = to_str(elem)
                            v_vars.append((enc_pname, elem))
            except TypeError:
                try:
                    tb = sys.exc_info()[2]
                    raise (TypeError, "not a valid non-string sequence or "
                           "mapping object", tb)
                finally:
                    del tb
                

            if not v_files:
                data = urllib.urlencode(v_vars, doseq)
            else:
                boundary, data = self.multipart_encode(v_vars, v_files)
                contenttype = 'multipart/form-data; boundary=%s' % boundary
                if(request.has_header('Content-Type') and request.get_header('Content-Type').find('multipart/form-data') != 0):
                    print "Replacing %s with %s" % (request.get_header('content-type'), 'multipart/form-data')
                request.add_unredirected_header('Content-Type', contenttype)

            request.add_data(data)
        return request
    
    # I also want this to work with HTTPS!
    https_request = http_request
    
    def multipart_encode(vars, files, boundary = None, buffer = None):
        if boundary is None:
            # Before :
            # boundary = mimetools.choose_boundary()
            # '127.0.0.1.1000.6267.1173556103.828.1'
            # This contains my IP address, I dont like that...
            # Now:
            m = hashlib.md5()
            m.update(mimetools.choose_boundary())
            boundary = m.hexdigest()
        if buffer is None:
            buffer = ''
        
        for(key, value) in vars:
            buffer += '--%s\r\n' % boundary
            buffer += 'Content-Disposition: form-data; name="%s"' % key
            buffer += '\r\n\r\n' + value + '\r\n'
        
        for(key, fd) in files:
            filename = fd.name.split( os.path.sep )[-1]
            contenttype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
            buffer += '--%s\r\n' % boundary
            buffer += 'Content-Disposition: form-data; name="%s"; filename="%s"\r\n' % (key, filename)
            buffer += 'Content-Type: %s\r\n' % contenttype
            # buffer += 'Content-Length: %s\r\n' % getFileSize(fd)
            fd.seek(0)
            buffer += '\r\n' + fd.read() + '\r\n'
        buffer += '--%s--\r\n\r\n' % boundary
        return boundary, buffer
    multipart_encode = Callable(multipart_encode)

    https_request = http_request

def getFileSize( file ):
    '''
    Aux function to get the file size. Needed if I want to use my modified string to fuzz file content.
    '''
    if type( file ) == string_file:
        return len( file )
    else:
        return os.fstat(file.fileno())[stat.ST_SIZE]
    
def main():
    import tempfile, sys

    validatorURL = "http://validator.w3.org/check"
    opener = urllib2.build_opener(MultipartPostHandler)

    def validateFile(url):
        temp = tempfile.mkstemp(suffix=".html")
        os.write(temp[0], opener.open(url).read())
        params = { "ss" : "0",          # show source
                   "doctype" : "Inline",
                   "uploaded_file" : open(temp[1], "rb") }
        print opener.open(validatorURL, params).read()
        os.remove(temp[1])
    
    def uploadFile( file ):
        params = { "MAX_FILE_SIZE" : "10000",
                   "uploadedfile" : open( file , "rb") }
        print opener.open( 'http://localhost/w3af/fileUpload/uploader.php', params).read()
        
    if len(sys.argv[1:]) > 0:
        for arg in sys.argv[1:]:
            uploadFile(arg)
    else:
        validateFile("http://www.google.com")

if __name__=="__main__":
    main()
