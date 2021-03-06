'''
test_sqli.py

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

from ..helper import PluginTest, PluginConfig

class TestSQLI(PluginTest):
    
    target_url = 'http://moth/w3af/audit/sql_injection/select/sql_injection_string.php'
    
    _run_configs = {
        'cfg': {
            'target': target_url + '?name=xxx',
            'plugins': {
                 'audit': (PluginConfig('sqli'),),
                 }
            }
        }
    
    def test_found_sqli(self):
        cfg = self._run_configs['cfg']
        self._scan(cfg['target'], cfg['plugins'])
        vulns = self.kb.getData('sqli', 'sqli')
        self.assertEquals(1, len(vulns))
        # Now some tests around specific details of the found vuln
        vuln = vulns[0]
        self.assertEquals("SELECT * FROM ", vuln['error'])
        self.assertEquals("Unknown database", vuln['db'])
        self.assertEquals(self.target_url, str(vuln.getURL()))