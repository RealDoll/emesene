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
#
#    module created by Andrea Stagi stagi.andrea(at)gmail.com
#

import os
import re
import shutil
import tempfile

try:
    import json
except ImportError:
    import simplejson as json

import logging
log = logging.getLogger('e3.common.Collections')

import extension
import Info
import MetaData
from Github import Github
from utils import AsyncAction

class ExtensionDescriptor(object):

    def __init__(self):
        self.files = {}
        self.metadata = {}

    def add_file(self, file_name, blob):
        self.files[file_name] = blob

class Collection(object):

    def __init__(self, theme, dest_folder):
        self.dest_folder = dest_folder
        self.extensions_descs = {}
        self.theme = theme
        self.github = Github("emesene")
        self._stop = False
        self._tree = None
        self.progress = 0.0

    def save_files(self, type_, label):
        self._stop = False
        element = self.extensions_descs[type_].get(label)
        if element is None:
            return

        keys = element.files.keys()
        tmp_dir = tempfile.mkdtemp()
        for k, path in enumerate(keys):
            if self._stop:
                self.remove(tmp_dir)
                return

            self.progress = k / float(len(keys))

            split_path = path.split("/")
            path_to_create = tmp_dir
            for part in split_path[:-1]:
                path_to_create = os.path.join(path_to_create, part)
            try:
                os.makedirs(path_to_create)
            except OSError:
                pass

            try:
                rq = self.github.get_raw(self.theme, element.files[path])
            except Exception, ex:
                log.exception(str(ex))
                self.remove(tmp_dir)
                return

            f = open(os.path.join(path_to_create, split_path[-1]), "wb")
            f.write(rq)
            f.close()

        self.remove(self.get_abspath(type_, label))
        path = self.get_path(type_, label)
        split_path = os.path.split(path)
        first_path = split_path[0] if split_path[1] else ''
        self.move(os.path.join(tmp_dir, path), os.path.join(self.dest_folder, first_path))
        self.remove(tmp_dir)
        self.progress = 0.0

    def download(self, download_item=None):
        self.progress = 0.0
        if download_item is not None:
            for element in self.extensions_descs.iterkeys():
                self.save_files(element, download_item)

    def remove(self, path):
        try:
            shutil.rmtree(path)
        except OSError, e:
            if e.errno != 2: # code 2 - no such file or directory
                raise

    def move(self, src, dst):
        shutil.move(src, dst)

    def stop(self):
        self._stop = True

    def set_tree(self, result):
        self._tree = result

    def plugin_name_from_file(self, file_name):
        pass

    def get_path(self, type_, label):
        pass

    def get_abspath(self, type_, label):
        ''' Get the full path of the plugin from the path of the file'''
        return os.path.join(self.dest_folder, self.get_path(type_, label))

    def fetch(self, refresh=True):
        if not refresh and self._tree is not None:
            return

        self._stop = False
        self._tree = None
        self.progress = 0.0

        AsyncAction(self.set_tree, self.github.fetch_tree, self.theme)

        while self._tree is None:
            if self._stop:
                return

        self.progress = 0.5

        for i, item in enumerate(self._tree['tree']):

            if item.get('type') != 'blob':
                continue

            file_name = item.get('path')

            (type_, name) = self.plugin_name_from_file(file_name)

            if type_ is None:
                continue

            if not self.check_version(type_, name):
                continue

            try:
                extype = self.extensions_descs[type_]
            except KeyError:
                extype = self.extensions_descs[type_] = {}

            try:
                pl = extype[name]
            except KeyError:
                pl = extype[name] = ExtensionDescriptor()

            pl.add_file(file_name, item.get('sha'))
            self.progress = i / float(len(self._tree['tree']) * 2) + 0.5
        self.progress = 0.0

    def has_item(self, type_, name):
        current_ext = self.extensions_descs.get(type_, {}).get(name)
        if not current_ext:
            return False
        return True

    def fetch_all_metadata(self, refresh=True):
        self._stop = False
        for type_, exts in self.extensions_descs.iteritems():
            try:
                for name in exts.iterkeys():
                    if self._stop:
                        return
                    self.fetch_metadata(type_, name, refresh)
            except RuntimeError:
                self._stop = True
                return

    def fetch_metadata(self, type_, name, refresh=False):
        '''fetch metadata if available'''
        current_ext = self.extensions_descs.get(type_, {}).get(name)
        if not current_ext:
            return None

        if not refresh and current_ext.metadata:
            return current_ext.metadata

        for path in current_ext.files.keys():
            if os.path.basename(path) == 'meta.json':
                try:
                    rq = self.github.get_raw(self.theme, current_ext.files[path])
                except Exception, ex:
                    log.exception(str(ex))
                    return None
                current_ext.metadata = json.loads(rq)
                return current_ext.metadata

        current_ext.metadata = {}
        return current_ext.metadata

    def version_value(self, version):
        '''return an integer version value'''
        if isinstance(version, int):
            return version

        stripped_version = re.sub(r'[^\d.]+', '', version)
        split_version = stripped_version.split(".")
        split_version.reverse()
        value = 0
        for i, val in enumerate(split_version):
            value += (int(val) << (i * 8))

        return value

    def check_version(self, type_, name):
        '''check whether the current version of emesene is compatible'''
        meta = self.fetch_metadata(type_, name)
        if not meta or not meta.get('required emesene version'):
            return True

        if self.version_value(meta.get('required emesene version')) > \
           self.version_value(Info.EMESENE_VERSION):
            return False

        return True

    def check_updates(self, type_, path):
        '''check whether updates are available'''
        name = os.path.basename(path)
        meta = self.fetch_metadata(type_, name)
        if not meta or not meta.get('version') or not meta.get('required emesene version'):
            return False

        local_meta = MetaData.get_metadata_from_path(path)
        if not local_meta or not local_meta.get('required emesene version'):
            return True

        if self.version_value(meta.get('required emesene version')) > \
           self.version_value(Info.EMESENE_VERSION):
            return False

        if not local_meta.get('version'):
            return True

        if self.version_value(meta.get('version')) > self.version_value(local_meta.get('version')):
            return True

        return False

class PluginsCollection(Collection):

    def plugin_name_from_file(self, file_name):
        ps = file_name.find("/")

        if ps != -1:
            return ("plugin", file_name[:ps])
        else:
            return (None, None)

    def get_path(self, type_, label):
        ''' Get the path of the plugin'''
        return label

class SupportedPluginsCollection(PluginsCollection):
    def __init__(self, dest_folder):
        PluginsCollection.__init__(self, 'emesene-supported-plugins',
                                   dest_folder)

extension.category_register('supported plugins collection',
                            SupportedPluginsCollection, single_instance=True)

class CommunityPluginsCollection(PluginsCollection):
    def __init__(self, dest_folder):
        PluginsCollection.__init__(self, 'emesene-community-plugins',
                                   dest_folder)

extension.category_register('community plugins collection',
                            CommunityPluginsCollection, single_instance=True)

class ThemesCollection(Collection):

    def plugin_name_from_file(self, file_name):

        ps = file_name.find("/")
        ps = file_name.find("/", ps + 1)

        if ps != -1:
            path = file_name[:ps]
            return path.split("/")
        else:
            return (None, None)

    def get_path(self, type_, label):
        ''' Get the path of the theme'''
        return os.path.join(type_, label)

class SupportedThemesCollection(ThemesCollection):
    def __init__(self, dest_folder):
        ThemesCollection.__init__(self, 'emesene-supported-themes',
                                  dest_folder)

extension.category_register('supported themes collection',
                            SupportedThemesCollection, single_instance=True)

class CommunityThemesCollection(ThemesCollection):
    def __init__(self, dest_folder):
        ThemesCollection.__init__(self, 'emesene-community-themes',
                                  dest_folder)

extension.category_register('community themes collection',
                            CommunityThemesCollection, single_instance=True)
