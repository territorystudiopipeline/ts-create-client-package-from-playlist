# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
App that copies all of the versions in the chosen playlist to a dated folder in the folder structure.
"""

import tank
import sys
import os
import subprocess
import re
import glob
import traceback
import datetime
from shutil import copy


class CopyPlaylistVersionsToFolder(tank.platform.Application):

    all_files = set()
    copied = set()
    not_copied = set()
    already_existing = set()

    def init_app(self):
        entity_types = self.get_setting("entity_types")
        deny_permissions = self.get_setting("deny_permissions")
        deny_platforms = self.get_setting("deny_platforms")

        p = {
            "title": "Copy Playlist Files to Folder",
            "deny_permissions": deny_permissions,
            "deny_platforms": deny_platforms,
            "supports_multiple_selection": False
        }

        self.engine.register_command(
            "copyPlaylistVersionsToFolder", self.copyPlaylistVersionsToFolder, p)

        p = {
            "title": "Preview Copy Playlist Files to Folder",
            "deny_permissions": deny_permissions,
            "deny_platforms": deny_platforms,
            "supports_multiple_selection": False
        }

        self.engine.register_command(
            "copyPlaylistVersionsToFolder_preview", self.copyPlaylistVersionsToFolder_preview, p)

    def returnVersionNumberIntFromStringOrNone(self, fileString):
        regex = "_[vV]\d+"
        result = re.search(regex, fileString)
        if not result:
            return None
        versionStringMatch = result.group(0)
        intVersion = int(versionStringMatch[2:])
        return intVersion

    def copyPlaylistVersionsToFolder_preview(self, entity_type, entity_ids):
        self.copyPlaylistVersionsToFolder(
            entity_type, entity_ids, preview=True)

    def copyPlaylistVersionsToFolder(self, entity_type, entity_ids, preview=False):
        try:
            playlist = self.get_playlist(entity_type, entity_ids)
            versions = self.get_playlist_versions(playlist)
            published_files = self.get_published_files(versions)
            self.copy_files_to_playlist_location(playlist, published_files, preview)
            self.log_info("")
            if not preview:
                self.update_version_info(playlist, versions)
            self.log_info("")
            self.log_info("Finished")
            self.log_info("Total files found: %d" % len(self.all_files))
            self.log_info("Files copied: %d" % len(self.copied))
            self.log_info("Files already existing: %d" % len(self.already_existing))
            if preview:
                self.log_info("PREVIEW MODE, no files copied.")

        except Exception, e:
            self.log_exception(traceback.format_exc())
            self.log_exception(str(e))

    def update_version_info(self, playlist, versions):
        for version in versions:
            today = datetime.date.today()
            sendDate = today.strftime('%Y-%m-%d')
            update_data = {'sg_sent_to': playlist['sg_recipient'],
                           'sg_send_date': sendDate}

            self.log_info("Updating send_date and sent_to on %s" % (version['name']))
            self.tank.shotgun.update('Version', version['id'], update_data)

    def get_playlist(self, entity_type, entity_ids):
        context = self.tank.context_from_entity(entity_type, entity_ids[0])
        playlistID = context.entity['id']
        result = self.tank.shotgun.find_one(
            "Playlist", [['id', 'is', playlistID]], ['sg_recipient', 'code'])
        if not result.get('sg_recipient'):
            raise Exception("Playlist has no recipient")
        return result

    def get_playlist_versions(self, playlist):
        filters = [
            ['playlist', 'is', {'type': 'Playlist', 'id': playlist['id']}]]
        fields = ['playlist.Playlist.code',
                  'sg_sort_order',
                  'version',
                  'version.Version.code']
        versionConnections = self.tank.shotgun.find(
            'PlaylistVersionConnection', filters, fields)
        versions = []
        for connection in versionConnections:
            versions.append(connection['version'])
        return versions

    def get_published_files(self, versions):
        published_files = []
        for version in versions:
            published_files += self.tank.shotgun.find("PublishedFile",
                                                      [['version.Version.id', 'is', version['id']]],
                                                      ['path',
                                                       'sg_publish_path',
                                                       'code'])
        return published_files

    def copy_files_to_playlist_location(self, playlist, published_files, preview):
        output_folder = self.get_ouput_folder(playlist)
        filepaths = self.get_filepath_list(published_files)
        self.log_info("For playlist %s :" % playlist['code'])
        self.log_info("")
        self.log_info("Copying the following files into %s:" % output_folder)
        self.log_info("")
        for path in filepaths:
            self.log_info(os.path.basename(path))

        self.log_info("")
        for path in filepaths:
            self.copy_file(path, output_folder, preview)

    def get_ouput_folder(self, playlist):
        projectPath = self.tank.project_path
        dailiesDir = os.path.join(projectPath, 'client_io', 'out')

        playlistDir = os.path.join(dailiesDir, playlist['code'])
        return playlistDir

    def get_filepath_list(self, published_files):
        paths = []
        for published_file in published_files:
            if published_file.get('sg_publish_path'):
                paths.append(published_file['sg_publish_path']['local_path'])
            elif published_file.get('path'):
                paths.append(published_file['path']['local_path'])
        return paths

    def copy_file(self, source, dest_folder, preview):
        files = [source]
        if self.is_sequence(source):
            files = self.get_sequence_files(source)
            dest_folder = os.path.join(dest_folder, self.get_sequence_sub_folder(source))
            if not os.path.exists(dest_folder):
                os.mkdir(dest_folder)
        for file in files:
            self.all_files.add(file)
            nu_path = os.path.join(dest_folder, os.path.basename(file))
            if os.path.exists(nu_path):
                self.already_existing.add(file)
            else:
                if not preview:
                    copy(file, nu_path)
                    self.copied.add(file)

    def is_sequence(self, path):
        pattern = re.compile(".*%\d+d\..*")
        return bool(pattern.match(path))

    def get_sequence_files(self, path):
        FRAME_REGEX = re.compile("(.*)(%\d+d)(.+)$", re.IGNORECASE)
        search = re.search(FRAME_REGEX, path)
        frames = []
        if search and len(search.groups()) == 3:
            frames = glob.glob(search.group(1) + "*" + search.group(3))
        return frames

    def get_sequence_sub_folder(self, path):
        FRAME_REGEX = re.compile("(.*).(%\d+d)(.+)$", re.IGNORECASE)
        search = re.search(FRAME_REGEX, path)
        sub_folder = os.path.basename(search.group(1))
        return sub_folder
