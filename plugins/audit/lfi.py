'''
lfi.py

Copyright 2006 Andres Riancho

This file is part of w3af, w3af.sourceforge.net .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

'''
from __future__ import with_statement

import re

import core.controllers.output_manager as om
import core.data.kb.knowledge_base as kb
import core.data.kb.vuln as vuln
import core.data.kb.info as info
import core.data.constants.severity as severity
import core.data.kb.config as cf

from core.controllers.plugins.audit_plugin import AuditPlugin
from core.controllers.misc.is_source_file import is_source_file
from core.data.fuzzer.fuzzer import create_mutants
from core.data.esmre.multi_in import multi_in
from core.data.constants.file_patterns import FILE_PATTERNS


class lfi(AuditPlugin):
    '''
    Find local file inclusion vulnerabilities.
    @author: Andres Riancho (andres.riancho@gmail.com)
    '''

    FILE_PATTERNS = FILE_PATTERNS
    _multi_in = multi_in(FILE_PATTERNS)

    def __init__(self):
        AuditPlugin.__init__(self)

        # Internal variables
        self._file_compiled_regex = []
        self._error_compiled_regex = []
        self._open_basedir = False

    def audit(self, freq):
        '''
        Tests an URL for local file inclusion vulnerabilities.

        @param freq: A FuzzableRequest
        '''
        orig_resp = self._uri_opener.send_mutant(freq)

        # Which payloads do I want to send to the remote end?
        local_files = []
        local_files.append(freq.get_url().get_fileName())
        if not self._open_basedir:
            local_files.extend(self._get_local_file_list(freq.get_url()))

        mutants = create_mutants(freq, local_files, orig_resp=orig_resp)

        self._send_mutants_in_threads(self._uri_opener.send_mutant,
                                      mutants,
                                      self._analyze_result,
                                      grep=False)

    def _get_local_file_list(self, origUrl):
        '''
        This method returns a list of local files to try to include.

        @return: A string list, see above.
        '''
        local_files = []

        extension = origUrl.get_extension()

        # I will only try to open these files, they are easy to identify of they
        # echoed by a vulnerable web app and they are on all unix or windows default installs.
        # Feel free to mail me ( Andres Riancho ) if you know about other default files that
        # could be installed on AIX ? Solaris ? and are not /etc/passwd
        if cf.cf.get('target_os') in ['unix', 'unknown']:
            local_files.append("../" * 15 + "etc/passwd")
            local_files.append("../" * 15 + "etc/passwd\0")
            local_files.append("../" * 15 + "etc/passwd\0.html")
            local_files.append("/etc/passwd")

            # This test adds support for finding vulnerabilities like this one
            # http://website/zen-cart/extras/curltest.php?url=file:///etc/passwd
            #local_files.append("file:///etc/passwd")

            local_files.append("/etc/passwd\0")
            local_files.append("/etc/passwd\0.html")
            if extension != '':
                local_files.append("/etc/passwd%00." + extension)
                local_files.append("../" * 15 + "etc/passwd%00." + extension)

        if cf.cf.get('target_os') in ['windows', 'unknown']:
            local_files.append("../" * 15 + "boot.ini\0")
            local_files.append("../" * 15 + "boot.ini\0.html")
            local_files.append("C:\\boot.ini")
            local_files.append("C:\\boot.ini\0")
            local_files.append("C:\\boot.ini\0.html")
            local_files.append("%SYSTEMROOT%\\win.ini")
            local_files.append("%SYSTEMROOT%\\win.ini\0")
            local_files.append("%SYSTEMROOT%\\win.ini\0.html")
            if extension != '':
                local_files.append("C:\\boot.ini%00." + extension)
                local_files.append("%SYSTEMROOT%\\win.ini%00." + extension)

        return local_files

    def _analyze_result(self, mutant, response):
        '''
        Analyze results of the _send_mutant method.
        Try to find the local file inclusions.
        '''

        # I analyze the response searching for a specific PHP error string
        # that tells me that open_basedir is enabled, and our request triggered
        # the restriction. If open_basedir is in use, it makes no sense to keep
        # trying to read "/etc/passwd", that is why this variable is used to
        # determine which tests to send if it was possible to detect the usage
        # of this security feature.

        if not self._open_basedir:
            if 'open_basedir restriction in effect' in response\
                    and 'open_basedir restriction in effect' not in mutant.get_original_response_body():
                self._open_basedir = True

        #
        #   I will only report the vulnerability once.
        #
        if self._has_bug(mutant):
            return

        #
        #   Identify the vulnerability
        #
        file_content_list = self._find_file(response)
        for file_pattern_match in file_content_list:
            if file_pattern_match not in mutant.get_original_response_body():
                v = vuln.vuln(mutant)
                v.set_plugin_name(self.get_name())
                v.set_id(response.id)
                v.set_name('Local file inclusion vulnerability')
                v.set_severity(severity.MEDIUM)
                v.set_desc(
                    'Local File Inclusion was found at: ' + mutant.found_at())
                v['file_pattern'] = file_pattern_match
                v.add_to_highlight(file_pattern_match)
                kb.kb.append_uniq(self, 'lfi', v)
                return

        #
        #   If the vulnerability could not be identified by matching strings that commonly
        #   appear in "/etc/passwd", then I'll check one more thing...
        #   (note that this is run if no vulns were identified)
        #
        #   http://host.tld/show_user.php?id=show_user.php
        if mutant.get_mod_value() == mutant.get_url().get_fileName():
            match, lang = is_source_file(response.get_body())
            if match:
                #   We were able to read the source code of the file that is vulnerable to
                #   local file read
                v = vuln.vuln(mutant)
                v.set_plugin_name(self.get_name())
                v.set_id(response.id)
                v.set_name('Local file read vulnerability')
                v.set_severity(severity.MEDIUM)
                msg = 'An arbitrary local file read vulnerability was found at: '
                msg += mutant.found_at()
                v.set_desc(msg)

                #
                #    Set which part of the source code to match
                #
                match_source_code = match.group(0)
                v['file_pattern'] = match_source_code

                kb.kb.append_uniq(self, 'lfi', v)
                return

        #
        #   Check for interesting errors (note that this is run if no vulns were identified)
        #
        for regex in self.get_include_errors():

            match = regex.search(response.get_body())

            if match and not regex.search(mutant.get_original_response_body()):
                i = info.info(mutant)
                i.set_plugin_name(self.get_name())
                i.set_id(response.id)
                i.set_name('File read error')
                i.set_desc(
                    'A file read error was found at: ' + mutant.found_at())
                kb.kb.append_uniq(self, 'error', i)

    def end(self):
        '''
        This method is called when the plugin wont be used anymore.
        '''
        self.print_uniq(kb.kb.get('lfi', 'lfi'), 'VAR')
        self.print_uniq(kb.kb.get('lfi', 'error'), 'VAR')

    def _find_file(self, response):
        '''
        This method finds out if the local file has been successfully included in
        the resulting HTML.

        @param response: The HTTP response object
        @return: A list of errors found on the page
        '''
        res = []
        for file_pattern_match in self._multi_in.query(response.get_body()):
            res.append(file_pattern_match)

        if len(res) == 1:
            msg = 'A file fragment was found. The section where the file is included is (only'
            msg += ' a fragment is shown): "' + res[0]
            msg += '". This is just an informational message, which might be related to a'
            msg += ' vulnerability and was found on response with id ' + \
                str(response.id) + '.'
            om.out.debug(msg)
        if len(res) > 1:
            msg = 'File fragments have been found. The following is a list of file fragments'
            msg += ' that were returned by the web application while testing for local file'
            msg += ' inclusion: \n'
            for file_pattern_match in res:
                msg += '- "' + file_pattern_match + '" \n'
            msg += 'This is just an informational message, which might be related to a'
            msg += ' vulnerability and was found on response with id ' + \
                str(response.id) + '.'
            om.out.debug(msg)
        return res

    def get_include_errors(self):
        '''
        @return: A list of file inclusion / file read errors generated by the web application.
        '''
        #
        #   In previous versions of the plugin the "Inclusion errors" listed in the _get_file_patterns
        #   method made sense... but... it seems that they trigger false positives...
        #   So I moved them here and report them as something "interesting" if the actual file
        #   inclusion is not possible
        #
        if self._error_compiled_regex:
            return self._error_compiled_regex
        else:
            read_errors = []
            read_errors.append("java.io.FileNotFoundException:")
            read_errors.append('java.lang.Exception:')
            read_errors.append('java.lang.IllegalArgumentException:')
            read_errors.append('java.net.MalformedURLException:')
            read_errors.append('The server encountered an internal error \\(.*\\) that prevented it from fulfilling this request.')
            read_errors.append(
                'The requested resource \\(.*\\) is not available.')
            read_errors.append("fread\\(\\):")
            read_errors.append("for inclusion '\\(include_path=")
            read_errors.append("Failed opening required")
            read_errors.append("<b>Warning</b>:  file\\(")
            read_errors.append("<b>Warning</b>:  file_get_contents\\(")

            self._error_compiled_regex = [re.compile(
                i, re.IGNORECASE) for i in read_errors]
            return self._error_compiled_regex

    def get_long_desc(self):
        '''
        @return: A DETAILED description of the plugin functions and features.
        '''
        return '''
        This plugin will find local file include vulnerabilities. This is done by
        sending to all injectable parameters file paths like "../../../../../etc/passwd"
        and searching in the response for strings like "root:x:0:0:".
        '''
