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
import re
from shutil import copyfile

class CopyPlaylistVersionsToFolder(tank.platform.Application):
    
    def init_app(self):
        entity_types = self.get_setting("entity_types")
        deny_permissions = self.get_setting("deny_permissions")
        deny_platforms = self.get_setting("deny_platforms")

        p = {
            "title": "Copy Playlist Versions to Folder",
            "deny_permissions": deny_permissions,
            "deny_platforms": deny_platforms,
            "supports_multiple_selection": False
        }
        
        self.engine.register_command("copyPlaylistVersionsToFolder", self.copyPlaylistVersionsToFolder, p)

    def copyPlaylistVersionsToFolder(self, entity_type, entity_ids):

        #Get the context
        context = self.tank.context_from_entity(entity_type, entity_ids[0])

        #Get the project
        project = context.project

        #Get the playlist ID
        playlistID = context.entity['id']

        #Get shotgun
        shotgun = self.tank.shotgun

        #Find all Versions where playlist matches the ID and the project matches
        # filters = [
        #     ['project', 'is', project],
        #     ['playlist', 'is', {'type':'Playlist', 'id':playlistID}]]
        
        filters = [['playlist', 'is', {'type':'Playlist', 'id':playlistID}]]
        fields = ['playlist.Playlist.code', 'sg_sort_order', 'version', 'version.Version.code', 'version.Version.user', 'version.Version.entity', 'version.Version.sg_path_to_movie']
        order=[{'column':'sg_sort_order','direction':'asc'}]
        versionConnections = shotgun.find('PlaylistVersionConnection', filters, fields, order)

        #Store versions to process
        versionsToProcess = []
        versionsWithoutPath = []

        #Get playlist name
        playlistName = None

        #Loop through Versions
        for versionConnection in versionConnections:
            version = versionConnection['version']
            user = versionConnection['version.Version.user']
            entity = versionConnection['version.Version.entity']
            pathToMovie = versionConnection['version.Version.sg_path_to_movie']

            #Report
            message = '%s (%s) by %s : %s' % (version['name'], entity['name'], user['name'], pathToMovie)
            self.log_info(message)
            self.log_info(' ')

            if pathToMovie :
                versionsToProcess.append(version)
            else : 
                versionsWithoutPath.append(version)

            #Set playlist name
            if not playlistName :
                playlistName = versionConnection['playlist.Playlist.code']

        #Report 
        self.log_info(" ")
        self.log_info("For playlist '%s' :" % playlistName)
        self.log_info("    There are %s versions with a filename present." % len(versionsToProcess))
        self.log_info("    There are %s versions WITHOUT a filename present." % len(versionsWithoutPath))


