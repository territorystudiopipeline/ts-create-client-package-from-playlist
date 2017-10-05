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
import os
import subprocess as sub
import re
import glob
import traceback
import datetime
from shutil import copy


video_exts = [".3g2", ".3gp", ".amv", ".avi", ".f4a", ".f4b", ".f4p", ".f4v", ".flv",
              ".flv", ".m2v", ".m4p", ".mkv", ".mov", ".mp2", ".mp4", ".mpe", ".mpeg",
              ".mpg", ".mpv", ".ogg", ".ogv", ".qt", ".rm", ".svi", ".vob", ".wmv", ".yuv"]

nuke_exts = [".nk"]


class CopyPlaylistVersionsToFolder(tank.platform.Application):

    all_movs = set()
    movs_copied = set()
    movs_not_copied = set()
    movs_missing = set()
    movs_already_existing = set()

    all_nks = set()
    nks_copied = set()
    nks_not_copied = set()
    nks_missing = set()
    nks_already_existing = set()
    nks_submitted_for_export = set()

    def init_app(self):
        deny_permissions = self.get_setting("deny_permissions")
        deny_platforms = self.get_setting("deny_platforms")

        p = {
            "title": "(Testing) Create Client package",

            "deny_permissions": deny_permissions,
            "deny_platforms": deny_platforms,
            "supports_multiple_selection": False
        }

        self.engine.register_command(
            "createClientPackage", self.create_client_package, p)

        p = {
            "title": "(Testing) Preview Create Client package",

            "deny_permissions": deny_permissions,
            "deny_platforms": deny_platforms,
            "supports_multiple_selection": False
        }

        self.engine.register_command(
            "previewCreateClientPackage", self.create_client_package_preview, p)

    def returnVersionNumberIntFromStringOrNone(self, fileString):
        regex = "_[vV]\d+"
        result = re.search(regex, fileString)
        if not result:
            return None
        versionStringMatch = result.group(0)
        intVersion = int(versionStringMatch[2:])
        return intVersion

    def create_client_package_preview(self, entity_type, entity_ids):
        self.create_client_package(
            entity_type, entity_ids, preview=True)

    def create_client_package(self, entity_type, entity_ids, preview=False):
        try:
            playlist = self.get_playlist(entity_type, entity_ids)
            versions = self.get_playlist_versions(playlist)
            published_files = self.get_published_files(playlist, versions)
            self.copy_files_to_playlist_location(playlist, published_files, preview)
            self.log_info("")
            if not preview:
                self.update_version_info(playlist, versions)
            self.log_info("")
            self.log_info("Finished")
            self.log_info("--------")
            self.log_info("Quicktimes chosen: %d" % len(self.all_movs))
            self.log_info("Quicktimes missing: %d" % len(self.movs_missing))
            self.log_info("Quicktimes copied: %d" % len(self.movs_copied))
            self.log_info("Quicktimes already existing: %d" % len(self.movs_already_existing))
            self.log_info("")
            self.log_info("Scripts chosen: %d" % len(self.all_nks))
            self.log_info("Scripts missing: %d" % len(self.nks_missing))
            self.log_info("Scripts copied: %d" % len(self.nks_copied))
            # self.log_info("Scripts already existing: %d" % len(self.nks_already_existing))
            self.log_info("Deadline jobs sent for export: %d" % len(self.nks_submitted_for_export))

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
            "Playlist", [['id', 'is', playlistID]], ['sg_published_files', 'sg_recipient', 'code'])
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

    def get_published_files(self, playlist, versions):
        published_files = []
        for version in versions:
            published_files += self.tank.shotgun.find("PublishedFile",
                                                      [['version.Version.id', 'is', version['id']]],
                                                      ['path',
                                                       'sg_publish_path',
                                                       'code',
                                                       'entity'])
        if playlist.get('sg_published_files'):
            for pf in playlist.get('sg_published_files'):
                published_files += self.tank.shotgun.find("PublishedFile",
                                                          [['id', 'is', pf['id']]],
                                                          ['path',
                                                           'sg_publish_path',
                                                           'code',
                                                           'entity'])
        return published_files

    def copy_files_to_playlist_location(self, playlist, published_files, preview):
        output_folder = self.get_ouput_folder(playlist)
        filepath_dicts = self.get_filepath_dicts(published_files)
        self.log_info("For playlist %s :" % playlist['code'])
        self.log_info("")
        self.log_info("Creating package in the following folder")
        self.log_info("%s" % output_folder)
        self.log_info("")
        # for d in filepath_dicts:
        #     if self.is_video(d['copy_path']) or self.is_nuke_script(d['copy_path']):
        #         self.log_info(os.path.basename(d['copy_path']))
        # self.log_info("")
        for d in filepath_dicts:
            if self.is_video(d['copy_path']):
                self.copy_video(d, output_folder, preview)
            elif self.is_nuke_script(d['copy_path']):
                nu_path = self.copy_nk(d, output_folder, preview)
                if nu_path:
                    job_id = self.create_nuke_package_job(nu_path, d['id'])
                    job_id = self.create_copy_job(nu_path, d['id'], job_id)

    def is_video(self, path):
        return os.path.splitext(path)[1].lower() in video_exts

    def is_nuke_script(self, path):
        return os.path.splitext(path)[1].lower() in nuke_exts

    def copy_video(self, published_file, output_folder, preview):
        src = published_file['copy_path']
        self.all_movs.add(src)
        dest_folder = os.path.join(output_folder,
                                   published_file['entity']['name'].upper(),
                                   "VIDREF")
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)
        nu_path = os.path.join(dest_folder, os.path.basename(src))
        if os.path.exists(nu_path):
            self.movs_already_existing.add(src)
        else:
            if os.path.exists(src):
                if not preview:
                    copy(src, nu_path)
                    self.movs_copied.add(src)
            else:
                self.log_exception("MISSING FILE: " + str(src))
                self.movs_missing.add(src)

    def copy_nk(self, published_file, output_folder, preview):
        src = published_file['copy_path']
        self.all_nks.add(src)
        dest_folder = os.path.join(output_folder,
                                   published_file['entity']['name'].upper(),
                                   "NUKE")
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)
        nu_path = os.path.join(dest_folder, os.path.basename(src))


    
        if os.path.exists(src):
            if not preview:
                if os.path.exists(nu_path):
                    os.remove(nu_path)
                copy(src, nu_path)
                self.nks_copied.add(src)
                return nu_path
        else:
            self.log_exception("MISSING FILE: " + str(src))
            self.nks_missing.add(src)

    def create_copy_job(self, nuke_script, id, previous_job_id):
        d_path = "/Applications/Thinkbox/Deadline8/Resources/deadlinecommand"
        python_exe = '"Y:\__pipeline\software\python\windows_nt\\2.7\python.exe"'
        current_folder = os.path.dirname(os.path.realpath(__file__))
        python_script = os.path.join(current_folder, "json_to_export.py")
        python_script = python_script.replace("/Volumes/FilmShare/", "\\\\\\\\192.168.50.10\\\\filmshare\\\\")
        python_script = python_script.replace("/Volumes/projects/", "\\\\\\\\ldn-fs1\\\\projects\\\\")
        python_script = python_script.replace("/", "\\\\")

        nuke_script = nuke_script.replace("/Volumes/FilmShare/", "\\\\\\\\192.168.50.10\\\\filmshare\\\\")
        nuke_script = nuke_script.replace("/Volumes/projects/", "\\\\\\\\ldn-fs1\\\\projects\\\\")
        nuke_script = nuke_script.replace("/", "\\\\")

        args = '%s' % (python_script)
        job_name = "Export Nuke Script for Client (job 2/2): %s" % nuke_script.split("\\")[-1]
        cmd = '%s -SubmitCommandLineJob' % d_path
        cmd += ' -executable %s' % python_exe
        cmd += ' -arguments "%s"' % args
        cmd += ' -frames 1  -prop LimitGroups=nuker -pool poola -priority 55 -name "%s"' % job_name
        cmd += ' -prop JobDependencies=%s' % (previous_job_id)
        cmd += ' -prop "EnvironmentKeyValue0=SCRIPT=%s"' % (nuke_script)
        cmd += ' -prop "EnvironmentKeyValue1=SHOTGUN_PUBLISHED_FILE_ID=%s"' % (id)
        cmd += ' -prop "EnvironmentKeyValue2=NUKE_PATH=\\\\\\\\ldn-fs1\\\\projects\\\\dng02_mae\\\\__pipeline\\\\configs\\\\nuke\\\\dotNuke_170928"'
        cmd += ' -prop "EnvironmentKeyValue3=PYTHONPATH=\\\\\\\\ldn-fs1\\\\projects\\\\dng02_mae\\\\_shotgun\\\\install\\\\core\\\\python"'
        out = sub.check_output(cmd, shell=True)
        self.nks_submitted_for_export.add(nuke_script)
        job_id = re.findall('.*JobID=(.+)\\n.*', out)[0]
        return job_id

    def create_nuke_package_job(self, nuke_script, id):
        d_path = "/Applications/Thinkbox/Deadline8/Resources/deadlinecommand"
        nuke_exe = '"C:\\Program Files\\Nuke10.5v4\\Nuke10.5.exe"'
        current_folder = os.path.dirname(os.path.realpath(__file__))
        nuke_python_script = os.path.join(current_folder, "nuke_to_json.py")
        nuke_python_script = nuke_python_script.replace("/Volumes/FilmShare/", "\\\\\\\\192.168.50.10\\\\filmshare\\\\")
        nuke_python_script = nuke_python_script.replace("/Volumes/projects/", "\\\\\\\\ldn-fs1\\\\projects\\\\")
        nuke_python_script = nuke_python_script.replace("/", "\\\\")

        nuke_script = nuke_script.replace("/Volumes/FilmShare/", "\\\\\\\\192.168.50.10\\\\filmshare\\\\")
        nuke_script = nuke_script.replace("/Volumes/projects/", "\\\\\\\\ldn-fs1\\\\projects\\\\")
        nuke_script = nuke_script.replace("/", "\\\\")

        args = '-t %s' % (nuke_python_script)
        job_name = "Export Nuke Script for Client (job 1/2): %s" % nuke_script.split("\\")[-1]
        cmd = '%s -SubmitCommandLineJob' % d_path
        cmd += ' -executable %s' % nuke_exe
        cmd += ' -arguments "%s"' % args
        cmd += ' -frames 1  -prop LimitGroups=nuker -pool poola -priority 55 -name "%s"' % job_name
        cmd += ' -prop "EnvironmentKeyValue0=SCRIPT=%s"' % (nuke_script)
        cmd += ' -prop "EnvironmentKeyValue1=SHOTGUN_PUBLISHED_FILE_ID=%s"' % (id)
        cmd += ' -prop "EnvironmentKeyValue2=NUKE_PATH=\\\\\\\\ldn-fs1\\\\projects\\\\dng02_mae\\\\__pipeline\\\\configs\\\\nuke\\\\dotNuke_170928"'
        cmd += ' -prop "EnvironmentKeyValue3=PYTHONPATH=\\\\\\\\ldn-fs1\\\\projects\\\\dng02_mae\\\\_shotgun\\\\install\\\\core\\\\python"'
        out = sub.check_output(cmd, shell=True)
        self.nks_submitted_for_export.add(nuke_script)
        job_id = re.findall('.*JobID=(.+)\\n.*', out)[0]
        return job_id


    def get_ouput_folder(self, playlist):
        projectPath = self.tank.project_path
        dailiesDir = os.path.join(projectPath, 'client_io', 'out')

        playlistDir = os.path.join(dailiesDir, playlist['code'])
        return playlistDir

    def get_filepath_dicts(self, published_files):
        for published_file in published_files:
            # if published_file.get('sg_publish_path'):
            #     p = self.get_localised_path(published_file['sg_publish_path'])
            #     if p:
            #         published_file['copy_path'] = p
            #     # paths.append(published_file['sg_publish_path']['local_path'])
            # el
            if published_file.get('path'):
                p = self.get_localised_path(published_file['path'])
                if p:
                    published_file['copy_path'] = p
                # paths.append(published_file['path']['local_path'])
        return published_files

    def get_localised_path(self, path_obj):
        if path_obj.get("local_path"):
            return path_obj["local_path"]
        elif path_obj.get("url"):
            url = path_obj.get("url")
            nuPath = url.replace("file://", "//")
            if os.name == "posix":
                nuPath = nuPath.replace("\\", "/")
                nuPath = nuPath.replace("Y:/", "/Volumes/FilmShare/")
                nuPath = nuPath.replace("//192.168.50.10/filmshare/", "/Volumes/FilmShare/")
                nuPath = nuPath.replace("//192.168.50.10/FILMSHARE/", "/Volumes/FilmShare/")
                nuPath = nuPath.replace("//192.168.50.10/FilmShare/", "/Volumes/FilmShare/")
                nuPath = nuPath.replace("//192.168.50.10/Filmshare/", "/Volumes/FilmShare/")
                nuPath = nuPath.replace("//ldn-fs1/projects/", "/Volumes/projects/")
            else:
                nuPath = nuPath.replace("/", "\\")
                nuPath = nuPath.replace("\\Volumes\\projects\\", "\\\\ldn-fs1\\projects\\")
                nuPath = nuPath.replace("\\Volumes\\FilmShare\\", "Y:\\")
                nuPath = nuPath.replace("\\Volumes\\Filmshare\\", "Y:\\")
                nuPath = nuPath.replace("\\Volumes\\filmshare\\", "Y:\\")
                nuPath = nuPath.replace("\\Volumes\\FILMSHARE\\", "Y:\\")
                nuPath = nuPath.replace("\\\\192.168.50.10\\filmshare\\", "Y:\\")
                nuPath = nuPath.replace("\\\\192.168.50.10\\FILMSHARE\\", "Y:\\")
                nuPath = nuPath.replace("\\\\192.168.50.10\\FilmShare\\", "Y:\\")
                nuPath = nuPath.replace("\\\\192.168.50.10\\Filmshare\\", "Y:\\")
            return nuPath

    def copy_file(self, source, dest_folder, preview):
        files = [source]
        if self.is_sequence(source):
            files = self.get_sequence_files(source)
            if len(files) == 0:
                self.log_exception("MISSING FILE: " + str(file))
                self.movs_missing.add(file)
            dest_folder = os.path.join(dest_folder, self.get_sequence_sub_folder(source))
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)
        for file in files:
            self.all_movs.add(file)
            nu_path = os.path.join(dest_folder, os.path.basename(file))
            if os.path.exists(nu_path):
                self.movs_already_existing.add(file)
            else:
                if not preview:
                    if os.path.exists(file):
                        copy(file, nu_path)
                        self.movs_copied.add(file)
                    else:
                        self.log_exception("MISSING FILE: " + str(file))
                        self.movs_missing.add(file)

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
