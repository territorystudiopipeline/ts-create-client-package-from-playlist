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
import datetime
from shutil import copy

class CopyPlaylistVersionsToFolder(tank.platform.Application):
    
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
        
        self.engine.register_command("copyPlaylistVersionsToFolder", self.copyPlaylistVersionsToFolder, p)


        p = {
            "title": "Preview Copy Playlist Files to Folder",
            "deny_permissions": deny_permissions,
            "deny_platforms": deny_platforms,
            "supports_multiple_selection": False
        }

        self.engine.register_command("copyPlaylistVersionsToFolder_preview", self.copyPlaylistVersionsToFolder_preview, p)

    def returnVersionNumberIntFromStringOrNone(self, fileString):
        regex = "_v\d{4}"
        result = re.search(regex, fileString)
        if not result :
            return None
        versionStringMatch = result.group(0)
        intVersion = int( versionStringMatch[2:] )
        return intVersion

    def copyPlaylistVersionsToFolder_preview(self, entity_type, entity_ids):
        self.copyPlaylistVersionsToFolder(entity_type, entity_ids, preview=True)

    def copyPlaylistVersionsToFolder(self, entity_type, entity_ids, preview=False):

        #Get shotgun
        tank = self.tank
        shotgun = tank.shotgun

        #Get the context
        context = self.tank.context_from_entity(entity_type, entity_ids[0])

        #Get the project
        project = context.project

        #Get the playlist ID
        playlistID = context.entity['id']

        #Get the playlist recipient
        filters = [['playlist', 'is', {'type':'Playlist', 'id':playlistID}]]
        result=shotgun.find_one("Playlist",[['id','is', playlistID] ], ['sg_recipient'])
        if not result['sg_recipient']:
            self.log_warning("There is no 'Recipient' set on this playlist. Aborting...")
            return
        else : 
            recipient = result['sg_recipient']
            self.log_info("\nRecipient : %s\n" % recipient)

        # self.log_info(shotgun.schema_field_read('Version'))
        # self.log_info(context.entity)

        #Find all Versions where playlist matches the ID and the project matches
        filters = [['playlist', 'is', {'type':'Playlist', 'id':playlistID}]]
        fields = ['playlist.Playlist.code', 'sg_sort_order', 'version', 'version.Version.code', 'version.Version.user', 'version.Version.entity', 'version.Version.sg_path_to_movie']
        order=[{'column':'sg_sort_order','direction':'asc'}]
        versionConnections = shotgun.find('PlaylistVersionConnection', filters, fields, order)

        #Store versions to process
        versionConnectionsToProcess = []
        versionConnectionsWithoutPath = []

        #Get playlist name
        playlistName = None

        #Loop through Versions
        for versionConnection in versionConnections:
            version = versionConnection['version']
            pathToMovie = versionConnection['version.Version.sg_path_to_movie']

            if pathToMovie :
                versionConnectionsToProcess.append(versionConnection)
            else : 
                versionConnectionsWithoutPath.append(versionConnection)

            #Set playlist name
            if not playlistName :
                playlistName = versionConnection['playlist.Playlist.code']

        #If we don't have a playlist name, something is wrong
        if not playlistName :
            self.log_warning("Playlist Name not found. Aborting.")
            return

        #Report sunmmary
        self.log_info(" ")
        self.log_info("For playlist '%s' :" % playlistName)
        self.log_info("    There are %s versions with a filename present." % len(versionConnectionsToProcess))
        self.log_info("    There are %s versions WITHOUT a filename present." % len(versionConnectionsWithoutPath))
        self.log_info(" ")

        #Get path to copy to
        projectPath = tank.project_path
        dailiesDir = os.path.join(projectPath, 'clientIO', 'outgoing')
        playlistDir = os.path.join(dailiesDir, playlistName)

        #Log preview state
        if preview :
            self.log_info("In Preview Mode")
            self.log_info(" ")
        else : 
            self.log_info("Not in Preview Mode")
            self.log_info(" ")

        #Check path exists
        if not os.path.exists(dailiesDir):
            self.log_warning('Dailies directory cannot be found : %s' % dailiesDir)
            return

        #Check if playlist dir exists
        if os.path.exists(playlistDir):
            self.log_info("Playlist directory already exists : %s" % playlistDir)
        else : 
            self.log_info("Playlist directory doesn't exist. Making directory : %s" % playlistDir)
            if not preview:
                try :
                    os.makedirs(playlistDir)
                except Exception as e :
                    self.log_warning("Could not make playlist directory. Aborting. Error : %s" % e)
                    return
            else : 
                self.log_info("PREVIEW MODE : Not creating directory.")

        #Store created/existing files
        createdFiles = []
        existingFiles = []
        failed = []

        #Loop through versions to process
        self.log_info(" ")
        for versionConnection in versionConnectionsToProcess:
            version = versionConnection['version']
            user = versionConnection['version.Version.user']
            entity = versionConnection['version.Version.entity']
            pathToMovie = versionConnection['version.Version.sg_path_to_movie']

            #Report individual version
            self.log_info("Processing '%s' (Asset:'%s') by %s" % (version['name'], entity['name'], user['name']))

            #Check the file still exists
            if os.path.exists(pathToMovie):
                self.log_info("Source file found on disk")
            else : 
                self.log_info("Source file NOT found on disk. Skipping.")
                failed.append(pathToMovie)

                #Attempt to see if it's a user problem
                if '/Users/' in pathToMovie : 
                    self.log_info('Source file appears to be on a users machine.')

                continue

            #Do the copy if it doesn't already exist
            fileName = os.path.split(pathToMovie)[1]
            destinationFilePath = os.path.join(playlistDir, fileName)

            if os.path.exists(destinationFilePath):
                self.log_info("File already exists for this Version. Skipping the copy.")
                existingFiles.append(destinationFilePath)
                self.log_info(' ')
            else : 
                self.log_info("Creating a copy : %s >> %s" % (pathToMovie, destinationFilePath))
                if not preview :
                    try : 
                        #Do the copy
                        # cmd = "ln -s %s %s" % (pathToMovie,destinationFilePath)
                        # os.system(cmd)
                        copy(pathToMovie, destinationFilePath)
                        self.log_info("File successfully copied.")
                        createdFiles.append(destinationFilePath)
                    except Exception as e :
                        self.log_warning("Could not copy file. Skipping file. Error : %s" % e)
                        self.log_info(' ')
                        failed.append(pathToMovie)
                        continue
                else : 
                    self.log_info("PREVIEW MODE : Not copying file.")
                    createdFiles.append(destinationFilePath)

            #Special case PSD convert - currently OSX only
            if sys.platform == 'darwin' :
                #If the destination file is a PSD, we can convert it to PSD on the command line
                if os.path.splitext(destinationFilePath)[1] in ['.psd', '.PSD'] :
                    self.log_info( "File is a PSD. Attempting conversion on the command line...")

                    #Make the PNG File path
                    pngFilePath = os.path.join( os.path.dirname(destinationFilePath), "%s.png" % os.path.splitext(destinationFilePath)[0] )
                    if not os.path.exists(pngFilePath):
                        if not preview :
                            cmd = "sips -s format png %s --out %s" % (destinationFilePath, pngFilePath)
                            process = subprocess.Popen(cmd.split())
                            process.wait()
                            self.log_info( "File conversion completed.")
                        else : 
                            self.log_info( "PREVIEW MODE : Not converting file.")
                    else : 
                        self.log_info( "PNG version already exists")

            #Get the versionNumber, sendToValue and sendDate
            self.log_info( "Updating the version info...")
            versionNumber = self.returnVersionNumberIntFromStringOrNone(fileName)
            versionNumberString = 'v%s' % str(versionNumber).zfill(4)
            today = datetime.date.today()
            sendDate = today.strftime('%Y-%m-%d') #30/11/16

            self.log_info("Info to update : %s, %s, %s" % (versionNumberString, recipient, sendDate))
            self.log_info(' ')

            #Update the version with the sent to, send date, and version number info
            updatedData = {
                'sg_version_number': versionNumberString,
                'sg_sent_to': recipient,
                'sg_send_date': sendDate,
            }
            if not preview :
                result = shotgun.update('Version', version['id'], updatedData)
                self.log_info("Version information updated.")
                self.log_info(result)
            else : 
                self.log_info("PREVIEW MODE : Not actually writing Version info")

            self.log_info(" ")


        #Report
        self.log_info("Created %s files" % len(createdFiles))
        self.log_info("Found %s existing files" % len(existingFiles))
        self.log_info("%s files failed" % len(failed))

        self.log_info("Finished")

