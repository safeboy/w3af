'''
test_payload_handler.py

Copyright 2012 Andres Riancho

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
import commands
import unittest

from plugins.attack.payloads.payload_handler import (payload_to_file,
                                                     is_payload,
                                                     exec_payload,
                                                     runnable_payloads,
                                                     get_payload_instance,
                                                     get_payload_list)

from core.data.kb.exec_shell import exec_shell
from core.data.kb.read_shell import read_shell


class TestPayloadHandler(unittest.TestCase):
    
    def test_get_payload_list(self):
        payload_list = get_payload_list()
        
        KNOWN_NAMES = (
                       'cpu_info',
                       'arp_cache',
                       'current_user',
                       'users',
                       'udp',
                       )
        
        for known_name in KNOWN_NAMES:
            self.assertTrue( known_name in payload_list, 
                             '%s not in %s' % (known_name, payload_list) )
        
        self.assertTrue( len(payload_list), len(set(payload_list)))
        
        self.assertFalse( '__init__' in payload_list )
        self.assertFalse( '__init__.py' in payload_list )
        
    def test_get_payload_instance(self):
        for payload_name in get_payload_list():
            payload_inst = get_payload_instance(payload_name, None)
            
            self.assertTrue( payload_inst.require() in ('linux', 'windows') )
    
    def test_runnable_payloads_exec(self):
        shell = FakeExecShell( None )
        runnable = runnable_payloads(shell)
        
        EXCEPTIONS = set(['portscan',])
        all = get_payload_list()
        all_but_exceptions = set(all) - EXCEPTIONS
        
        self.assertEquals(
                          set(runnable),
                          all_but_exceptions
                          )
    
    def test_runnable_payloads_read(self):
        shell = FakeReadShell( None )
        runnable = runnable_payloads(shell)
        
        EXPECTED = ('apache_run_user','cpu_info','firefox_stealer','get_hashes')
        NOT_EXPECTED = ('msf_linux_x86_meterpreter_reverse_tcp','portscan','w3af_agent')
        
        for name in EXPECTED:
            self.assertTrue(name in runnable)

        for name in NOT_EXPECTED:
            self.assertFalse(name in runnable)

    def test_exec_payload_exec(self):
        shell = FakeExecShell(None)
        result = exec_payload(shell, 'os_fingerprint', use_api=True)
        self.assertEquals({'os': 'Linux'}, result)
        
    def test_exec_payload_read(self):
        shell = FakeReadShell(None)
        result = exec_payload(shell, 'os_fingerprint', use_api=True)
        self.assertEquals({'os': 'Linux'}, result)

        result = exec_payload(shell, 'cpu_info', use_api=True)
        # On my box the result is:
        #
        # {'cpu_info': 'AMD Phenom(tm) II X4 945 Processor', 'cpu_cores': '4'}
        #
        # But because others will also run this, I don't want to make it so
        # strict
        self.assertTrue('cpu_info' in result)
        self.assertTrue('cpu_cores' in result)
        self.assertGreater( int(result['cpu_cores']) , 0 )
        self.assertLess( int(result['cpu_cores']) , 12 )

    def test_is_payload(self):
        self.assertTrue( is_payload('cpu_info') )
        self.assertFalse( is_payload('andres_riancho') )
            

class FakeExecShell(exec_shell):
 
    def execute(self, command):
        return commands.getoutput(command)
    
    def end( self ):
        pass
        
    def getName( self ):
        return 'FakeExecShell'
    
class FakeReadShell(read_shell):
 
    def read(self, filename):
        return file(filename).read()
    
    def end( self ):
        pass
        
    def getName( self ):
        return 'FakeReadShell'   