# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from fwunit.srx import scripts
from nose.tools import eq_, with_setup
from fwunit.ip import IP, IPSet
from fwunit.types import Rule
from fwunit.test.util.srx_xml import FakeSRX

F = None


def install():
    global F
    F = FakeSRX()
    F.install()


def uninstall():
    F.uninstall()


@with_setup(install, uninstall)
def test_run_no_globals():
    fake_cfg = {
        'firewall': 'fw',
        'ssh_username': 'uu',
        'ssh_password': 'pp',
        'application-map': {'junos-ssh': 'ssh', 'junos-ping': 'ping'},
    }
    z = F.add_zone('untrust')
    F.add_address(z, 'host1', '9.0.9.1/32')
    F.add_address(z, 'host2', '9.0.9.2/32')
    F.add_address(z, 'puppet', '9.0.9.2/32')
    F.add_address_set(z, 'hosts', 'host1', 'host2')
    F.add_interface(z, 'reth0')

    z = F.add_zone('trust')
    F.add_address(z, 'trustedhost', '10.0.9.2/32')
    F.add_address(z, 'dmz', '10.1.0.0/16')
    F.add_address(z, 'shadow', '10.1.99.99/32')
    F.add_interface(z, 'reth1')

    F.add_policy(('trust', 'trust'),
                 dict(sequence=1, name='ssh', src='any', dst='any', app='junos-ssh', action='permit'))
    F.add_policy(('trust', 'trust'),
                 dict(sequence=10, name='deny', src='any', dst='any', app='any', action='deny'))
    F.add_policy(('trust', 'untrust'),
                 dict(sequence=1, name='ssh', src='any', dst='any', app='junos-ssh', action='permit'))
    F.add_policy(('trust', 'untrust'),
                 dict(sequence=2, name='puppet', src='any', dst='puppet', app='puppet', action='permit'))
    F.add_policy(('trust', 'untrust'),
                 dict(sequence=10, name='deny', src='any', dst='any', app='any', action='deny'))
    F.add_policy(('untrust', 'trust'),
                 dict(sequence=1, name='no-shadow-ping', src='any', dst='shadow', app='junos-ping', action='deny'))
    F.add_policy(('untrust', 'trust'),
                 dict(sequence=2, name='ping', src='any', dst='dmz', app='junos-ping', action='permit'))
    F.add_policy(('untrust', 'trust'),
                 dict(sequence=3, name='admin-puppet', src='puppet', dst='trustedhost', app='junos-ssh', action='permit'))
    F.add_policy(('untrust', 'trust'),
                 dict(sequence=4, name='admin', src='any-ipv6', dst='trustedhost', app='junos-ssh', action='permit'))
    F.add_policy(('untrust', 'trust'),
                 dict(sequence=10, name='deny', src='any', dst='any', app='any', action='deny'))
    F.add_policy(('untrust', 'untrust'),
                 dict(sequence=10, name='deny', src='any', dst='any', app='any', action='deny'))

    rules = scripts.run(fake_cfg, {})
    for r in rules.itervalues():
        r.sort()
    exp = {
        'ping': [
            Rule(src=IPSet([IP('0.0.0.0/0')]) - IPSet([IP('10.0.0.0/8')]),
                 dst=IPSet([IP('10.1.0.0/16')]) - IPSet([IP('10.1.99.99')]),
                 app='ping', name='ping'),
        ],
        'puppet': [
            Rule(src=IPSet([IP('10.0.0.0/8')]), dst=IPSet([IP('9.0.9.2')]), app='puppet',
                 name='puppet'),
        ],
        'ssh': [
            Rule(src=IPSet([IP('9.0.9.2')]), dst=IPSet([IP('10.0.9.2')]), app='ssh',
                 name='admin-puppet'),
            Rule(src=IPSet([IP('10.0.0.0/8')]), dst=IPSet([IP('0.0.0.0/0')]), app='ssh',
                 name='ssh'),
        ],
    }
    eq_(rules, exp)


@with_setup(install, uninstall)
def test_run_global_policies_and_addrbook():
    fake_cfg = {
        'firewall': 'fw',
        'ssh_username': 'uu',
        'ssh_password': 'pp',
        'application-map': {'junos-ssh': 'ssh', 'junos-ping': 'ping'},
    }

    z = F.add_zone('untrust')
    F.add_address(z, 'untrust-host', '9.0.9.1/32')
    F.add_interface(z, 'reth0')

    z = F.add_zone('trust')
    F.add_address(z, 'trust-host', '10.9.1.1/32')
    F.add_interface(z, 'reth1')

    ab = F.add_addrbook('global')
    F.add_address(ab, 'global-host', '10.1.1.1/32')

    ab = F.add_addrbook('public')
    F.add_address(ab, 'public-host', '2.2.1.1/32')
    F.add_attach(ab, 'trust')
    F.add_attach(ab, 'untrust')

    F.add_policy(('trust', 'untrust'),
                 dict(sequence=1, name='ssh', src='trust-host', dst='untrust-host', app='junos-ssh', action='permit'))
    F.add_policy(('untrust', 'trust'),
                 dict(sequence=1, name='puppet', src='public-host', dst='global-host', app='puppet', action='permit'))
    F.add_policy('global',
                 dict(sequence=10, name='ping', src='any', dst='any', app='junos-ping', action='permit'))
    F.add_policy('global',
                 dict(sequence=11, name='deny', src='any', dst='any', app='any', action='deny'))

    rules = scripts.run(fake_cfg, {})
    for r in rules.itervalues():
        r.sort()
    exp = {
        'ping': [
            Rule(src=IPSet([IP('0.0.0.0/0')]), dst=IPSet([IP('0.0.0.0/0')]),
                 app='ping', name='ping'),
        ],
        'puppet': [
            Rule(src=IPSet([IP('2.2.1.1')]), dst=IPSet([IP('10.1.1.1')]),
                 app='puppet', name='puppet'),
        ],
        'ssh': [
            Rule(src=IPSet([IP('10.9.1.1')]), dst=IPSet([IP('9.0.9.1')]),
                 app='ssh', name='ssh'),
        ],
    }
    eq_(rules, exp)
