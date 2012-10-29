# -*- coding: utf-8 -*-

#    This file is part of emesene.
#
#    emesene is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    emesene is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with emesene; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from NetworkManagerHelperDummy import DummyNetworkChecker

try_dbus = True
try:
    from NetworkManagerHelperGio import GioNetworkChecker
    try_dbus = False
except ImportError:
    pass

if try_dbus:
    try:
        from NetworkManagerHelperDBus import DBusNetworkChecker
    except ImportError:
        pass

try:
    from NetworkManagerHelperWin32 import Win32NetworkChecker as NetworkChecker
except ImportError:
    pass

