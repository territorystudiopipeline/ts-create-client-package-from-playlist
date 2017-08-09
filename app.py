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
        regex = "_[vV]\d+"
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
            self.log_info("\nRecipient : %s" % recipient)

        # self.log_info(shotgun.schema_field_read('Version'))
        # self.log_info(context.entity)

        #Find all Versions where playlist matches the ID and the project matches
        filters = [['playlist', 'is', {'type':'Playlist', 'id':playlistID}]]
        fields = ['playlist.Playlist.code', 'sg_sort_order', 'version', 'version.Version.code', 'version.Version.user', 'version.Version.entity', 'version.Version.sg_path_to_movie', 'version.Version.sg_path_to_frames']
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
            pathToFrames = versionConnection['version.Version.sg_path_to_frames']

            #Find versions with paths
            if pathToMovie == None and pathToFrames == None : 
                versionConnectionsWithoutPath.append(versionConnection)
            else : 
                versionConnectionsToProcess.append(versionConnection)

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
        self.log_info("....There are %s versions with a filename present." % len(versionConnectionsToProcess))
        self.log_info("....There are %s versions WITHOUT a filename present.\n" % len(versionConnectionsWithoutPath))

        #Get path to copy to
        projectPath = tank.project_path
        dailiesDir = os.path.join(projectPath, 'client_io', 'test_out')
        playlistDir = os.path.join(dailiesDir, playlistName)


        self.log_info("Making Directory :")

        #Check path exists
        if not os.path.exists(dailiesDir):
            self.log_warning('%s directory cannot be found.' % dailiesDir)
            return

        #Check if playlist dir exists
        if os.path.exists(playlistDir):
            self.log_info("....Playlist directory already exists")
        else : 
            self.log_info("....Playlist directory doesn't exist. Making directory...")
            if not preview:
                try :
                    os.makedirs(playlistDir)
                except Exception as e :
                    self.log_warning("....Could not make playlist directory. Aborting. Error : %s" % e)
                    return
            else : 
                self.log_info("....PREVIEW MODE : Not creating directory.")

        #Store created/existing files
        createdFiles = []
        existingFiles = []
        failed = []

        #Loop through versions to process
        for versionConnection in versionConnectionsToProcess:
            version = versionConnection['version']
            user = versionConnection['version.Version.user']
            entity = versionConnection['version.Version.entity']
            pathToMovie = versionConnection['version.Version.sg_path_to_movie']
            pathToFrames = versionConnection['version.Version.sg_path_to_frames']

            #Check for an entity connection
            if entity == None : 
                entityConnection = False
                self.log_info("\nProcessing '%s' by %s" % (version['name'], user['name']))
            else : 
                entityConnection = True
                self.log_info("\nProcessing '%s' (Asset:'%s') by %s" % (version['name'], entity['name'], user['name']))


            #Check whether we need to use the path_to_movie or path_to_frames
            sourcePath = None
            if pathToMovie == None : 
                if pathToFrames == None : 
                    self.log_info("....There are no files associated with this version. Skipping.")
                    continue
                else :
                    sourcePath = pathToFrames
            else : 
                sourcePath = pathToMovie 
            
            #Check mac or windows and change filepath accordingly
            if os.name == "posix":
                sourcePath = sourcePath.replace("Y:\\","/Volumes/FilmShare/")
                sourcePath = sourcePath.replace("\\\\192.168.50.10\\filmshare\\","/Volumes/FilmShare/")
                sourcePath = sourcePath.replace("\\\\192.168.50.10\\FILMSHARE\\","/Volumes/FilmShare/")
                sourcePath = sourcePath.replace("\\\\192.168.50.10\\FilmShare\\","/Volumes/FilmShare/")
                sourcePath = sourcePath.replace("\\\\192.168.50.10\\Filmshare\\","/Volumes/FilmShare/")
                sourcePath = sourcePath.replace("\\","/")
            else:
                sourcePath = sourcePath.replace("/Volumes/FilmShare/", "Y:\\")
                sourcePath = sourcePath.replace("/Volumes/Filmshare/", "Y:\\")
                sourcePath = sourcePath.replace("/Volumes/filmshare/", "Y:\\")
                sourcePath = sourcePath.replace("/Volumes/FILMSHARE/", "Y:\\")
                sourcePath = sourcePath.replace("/","\\")


            #Check the file still exists
            if not os.path.exists(sourcePath):
                self.log_info("....Source file NOT found on disk.")
                failed.append(sourcePath)

                #Attempt to see if it's a user problem
                if '/Users/' in sourcePath : 
                    self.log_info("....(It appears to be on a users machine)")

                continue

            #Do the copy if it doesn't already exist
            fileName = os.path.split(sourcePath)[1]
            destinationFilePath = os.path.join(playlistDir, fileName)

            if os.path.exists(destinationFilePath):
                self.log_info("....Destination file already exists for this Version.")
                existingFiles.append(destinationFilePath)
            else : 
                self.log_info("....Copying file...")
                if not preview :
                    try : 
                        #Do the copy
                        # cmd = "ln -s %s %s" % (sourcePath,destinationFilePath)
                        # os.system(cmd)
                        copy(sourcePath, destinationFilePath)
                        self.log_info("....File successfully copied.")
                        createdFiles.append(destinationFilePath)
                    except Exception as e :
                        self.log_warning("....Could not copy file. Skipping file. Error : %s" % e)
                        failed.append(sourcePath)
                        continue
                else : 
                    self.log_info("....PREVIEW MODE : Not copying file.")
                    createdFiles.append(destinationFilePath)

            #Special case PSD convert - currently OSX only
            if sys.platform == 'darwin' :
                #If the destination file is a PSD, we can convert it to PSD on the command line
                if os.path.splitext(destinationFilePath)[1] in ['.psd', '.PSD'] :
                    self.log_info( "....File is a PSD. Attempting conversion on the command line...")

                    #Make the PNG File path
                    pngFilePath = os.path.join( os.path.dirname(destinationFilePath), "%s.png" % os.path.splitext(destinationFilePath)[0] )
                    if not os.path.exists(pngFilePath):
                        if not preview :
                            cmd = "sips -s format png %s --out %s" % (destinationFilePath, pngFilePath)
                            process = subprocess.Popen(cmd.split())
                            process.wait()
                            self.log_info( "....File conversion completed.")
                        else : 
                            self.log_info( "....PREVIEW MODE : Not converting file.")
                    else : 
                        self.log_info( "....PNG version already exists")

            #We only update the version info if there is an entity present on the version
            if not entityConnection:
                self.log_info("....Version has no entity connection. Skipping the version info update...")
                continue

            #Get the versionNumber, sendToValue and sendDate
            self.log_info( "....Updating the version info...")

            try : 
                versionNumber = self.returnVersionNumberIntFromStringOrNone(fileName)
                
                if not versionNumber : 
                    versionNumber = 1

                self.log_info("Version Number : %s" % versionNumber)
                
                versionNumberString = 'v%s' % str(versionNumber).zfill(4)
                today = datetime.date.today()
                sendDate = today.strftime('%Y-%m-%d') #30/11/16

                #Get the previous version sent
                #Look at the versions on the entity. Get their sg_sent_to and sg_version_number fields.
                #Isolate versions that are sent to same person. Get version with highest sg_version_number that is lower than current
                filters = [ ['entity', 'is', {'type':'Asset', 'id': entity['id'] } ] ]
                fields = ['name', 'id', 'sg_sent_to', 'sg_version_number']
                allEntityVersions = shotgun.find('Version', filters, fields)
                
                #Skip versions with no sentTo/versionNumber info or sentTo that don't match the current recipient, and THIS version
                releventEntityVersions = [x for x in allEntityVersions if (x['sg_sent_to'] and x['sg_version_number']) and x['sg_sent_to'] == recipient and x['id'] != version['id']]

                #Loop through and get latest
                previousVersionSent = 'None'
                previousVersionSentInt = -1
                for entityVersion in releventEntityVersions : 
                    
                    #Get the other version's version number
                    ent_versionNumber = entityVersion['sg_version_number']

                    if not ent_versionNumber :
                        intEnt_versionNumber = 0                    
                    intEnt_versionNumber = int(ent_versionNumber[1:])

                    #Set previous version sent var ONLY if ent_versionNumber is less than current
                    if intEnt_versionNumber < versionNumber :
                        if intEnt_versionNumber > previousVersionSentInt :
                            previousVersionSentInt = intEnt_versionNumber
                            previousVersionSent = ent_versionNumber

                self.log_info("....Info to update : %s, %s, %s, %s" % (versionNumberString, recipient, sendDate, previousVersionSent))

                #Update the version with the sent to, send date, and version number info
                updatedData = {
                    'sg_version_number': versionNumberString,
                    'sg_sent_to': recipient,
                    'sg_send_date': sendDate,
                    'sg_previous_sent_version':previousVersionSent
                }

                if not preview :
                    result = shotgun.update('Version', version['id'], updatedData)
                    self.log_info("....Version information updated.")
                else : 
                    self.log_info("....PREVIEW MODE : Not actually writing Version info")

                self.log_info(" ")

            except Exception as e :
                self.log_warning(e)


        #Report
        self.log_info("\nFinished")
        self.log_info("....Created %s files" % len(createdFiles))
        self.log_info("....Found %s existing files" % len(existingFiles))
        self.log_info("....%s files failed" % len(failed))