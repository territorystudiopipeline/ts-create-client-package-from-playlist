import nuke
import os
import re
import sgtk
import sgtk.util.shotgun as sg
from tank_vendor.shotgun_authentication import ShotgunAuthenticator
import datetime as dt

new_lighting_pass_file_name = "E_%(shot)s_graphics_territory_lgt_%(element)s_%(desc)s_%(pass)s_%(version)s.%04d.%(ext)s"


accepted_lighting_elements = ['core', 'console', 'driftlink', 'flower']

accepted_lighting_positions = ['l', 'c', 'r']

accepted_lighting_desc = ['rgba', 'lines', 'ui', 'protractor', 'text3D', 'miscUI', 'neuralNet', 'solid']

accepted_lighting_passes = ['colour_passes', 'beauty', 'alpha', 'direct_diffuse',
                            'direct_specular', 'diffuse_albedo', 'indirect_diffuse',
                            'indirect_specular', 'reflection', 'refraction', 'z', 'n',
                            'refraction_opacity', 'crypto_material', 'depth', 'emission',
                            'normals', 'p', 'pref', 'vector', 'id_1', 'id_2', 'id_3', 'id_4', 'id_5', 'id_6', ]

global_version = "v000"

report_str = "Warnings:\n"


def main():
    global report_str
    global global_version
    script = get_nuke_script()
    nuke.scriptOpen(script)
    global_version = get_version_str(script)
    read_nodes = get_valid_read_nodes()
    report_str += "\nExport History:\n"
    map(localise_read_node, read_nodes)
    update_shotgun()

def get_shotgun_connection():
    # Instantiate the CoreDefaultsManager. This allows the ShotgunAuthenticator to
    # retrieve the site, proxy and optional script_user credentials from shotgun.yml
    cdm = sgtk.util.CoreDefaultsManager()

    # Instantiate the authenticator object, passing in the defaults manager.
    authenticator = ShotgunAuthenticator(cdm)

    # Create a user programmatically using the script's key.
    user = authenticator.create_script_user(
        api_script="toolkit_scripts",
        api_key="09d648cbb268019edefd1db3f1a8d8ea011c354326f23f24d13c477d75306810"
    )
    # print "User is '%s'" % user

    # Tells Toolkit which user to use for connecting to Shotgun.
    sgtk.set_authenticated_user(user)
    sgc = sg.create_sg_connection()
    return sgc

def update_shotgun():
    pub_id = os.environ.get("SHOTGUN_PUBLISHED_FILE_ID")
    sgc = get_shotgun_connection()
    publish_file = sgc.find_one("PublishedFile",[['id', 'is', int(pub_id)]], ['project', 'sg_notes'])
    note = {}
    note['subject'] = 'Exported %s to %s' % (dt.datetime.now().strftime('%y/%m/%d %H:%M'),
                                             os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(get_nuke_script())))))
    note['content'] = report_str
    note['project'] = publish_file['project']
    note = sgc.create("Note", note)
    new_data = {'sg_notes' : publish_file['sg_notes'] + [note]}
    sgc.update("PublishedFile",int(pub_id), new_data)

def check_missmatching_versions(read_nodes):
    paths = {}
    for node in read_nodes:
        path = get_read_node_path(node)
        path = os.path.basename(path)
        path_without_version = get_path_without_version(path)
        # print path, path_without_version
        if path_without_version not in paths:
            paths[path_without_version] = [path]
        elif path not in paths[path_without_version]:
            paths[path_without_version].append(path)
    e_str = ""
    for path in paths.keys():
        if len(paths[path]) != 1:
            for p in paths[path]:
                e_str += "%s\n" % p
    if e_str != "":
        e_str = "Multiple versions of the same element are being used in this script.\n" + e_str
        raise Exception(e_str)


def get_path_without_version(path):
    regex = re.compile("(.*)(v[0-9]+)(.*$)", re.IGNORECASE)
    search = re.search(regex, path)
    if search and len(search.groups()) == 3:
        return search.group(1) + search.group(3)
    else:
        return path


def get_nuke_script():
    script = localise_path(os.environ.get("SCRIPT"))
    return script


def localise_path(path):
    if os.name == "posix":
        path = path.replace("\\", "/")
        path = path.replace("//192.168.50.10/filmshare/", "/Volumes/Filmshare/")
        path = path.replace("//ldn-fs1/projects/", "/Volumes/projects/")
    else:
        path = path.replace("/", "\\")
        path = path.replace("\\\\Volumes\\\\Filmshare", "\\\\\\\\192.168.50.10\\\\filmshare\\\\")
        path = path.replace("\\\\Volumes\\\\projects", "\\\\\\\\ldn-fs1\\\\projects\\\\")
    return path


def get_valid_read_nodes():
    global report_str
    valid_nodes = []
    all_nodes = get_all_read_nodes()
    for node in all_nodes:
        if is_enabled(node) and matches_expected_pattern(node):
            if has_missing_files(node):
                report_str += "Missing Files: %s\n" % os.path.basename(get_read_node_path(node))
            else:
                valid_nodes.append(node)
    check_missmatching_versions(valid_nodes)
    return valid_nodes


def has_missing_files(node):
    all_files = get_source_files(node)
    for file in all_files:
        f = localise_path(file)
        if not os.path.exists(f):
            return True
    return False


def get_all_read_nodes():
    classes = ["Read"]
    nodes = []
    for node in nuke.allNodes():
        if node.Class() in classes:
            nodes.append(node)
    return nodes


def is_enabled(read_node):
    return read_node['disable'].getValue() == 0


def matches_expected_pattern(read_node):
    path = get_read_node_path(read_node)
    matched = (is_ingest(path) or
               is_comp(path) or
               is_lighting(path) or
               is_quicktime(path) or
               is_precomp(path))
    if is_lighting(path):
        #report on validity
        get_lighting_parts(os.path.basename(path), report_check=True)
    if not matched:
        report = "Path does not match any expected patterns: %s\n" % path
        report += "Patterns:\n"
        report += "*\\ingest\\*\n"
        report += "*_comp_*\n"
        report += "*_precomp_*\n"
        report += "*_lgt_*\n"
        report += "*.mov\n"

        raise Exception(report)

    return matched


def is_ingest(path):
    return "ingest" in get_folders_of_path(path)


def get_folders_of_path(path):
    folders = []
    while 1:
        path, folder = os.path.split(path)

        if folder != "":
            folders.append(folder)
        else:
            if path != "":
                folders.append(path)

            break

    folders.reverse()
    return folders


def is_comp(path):
    return "_comp_" in os.path.basename(path)


def is_lighting(path):
    is_it = "_lgt_" in os.path.basename(path)
    return is_it


def is_quicktime(path):
    return ".mov" == os.path.splitext(path)[1]


def is_precomp(path):
    return "_precomp_" in os.path.basename(path)


def localise_read_node(read_node):
    global report_str
    path = get_read_node_path(read_node)

    report_str += "\n"
    report_str += "Original Filename: %s\n" % os.path.basename(path)
    source_files = get_source_files(read_node)
    dest_files = []
    for source_file in source_files:
        dest_files.append(get_dest_path(source_file))

    report_str += "Localised filenames:\n"
    report_str += "--> %s\n" % os.path.basename(dest_files[0])
    if len(dest_files) != 1:
        report_str += "...\n"
        report_str += "--> %s\n" % os.path.basename(dest_files[-1])
    
    copied_files = robocopy_files(os.path.dirname(source_files[0]),
                                   os.path.dirname(dest_files[0]),
                                   source_files)



    rename_files(copied_files, dest_files) 

    final_dest_path = get_dest_path(path)
    return [path, final_dest_path]


def get_read_node_path(read_node):
    return read_node['file'].getValue()


def get_source_files(read_node):
    files = []
    path = get_read_node_path(read_node)
    if is_sequence(path):
        for r in range(int(read_node['first'].getValue()),
                       int(read_node['last'].getValue())):
            files.append(path % r)
    else:
        files = [path]
    return files[:1]


def is_sequence(path):
    pattern = re.compile(".*%\d+d\..*")
    return bool(pattern.match(path))


def get_dest_path(path):
    sub_path = ""
    if is_comp(path):
        sub_path = get_simple_dest_path(path)
    elif is_precomp(path):
        sub_path = get_simple_dest_path(path)
    elif is_ingest(path):
        # print path
        sub_path = get_ingest_dest_path(path)
    elif is_lighting(path):
        sub_path = get_lighting_dest_path(path)
    elif is_quicktime(path):
        sub_path = get_quicktime_dest_path(path)
    script_path = get_nuke_script()
    root_of_export = os.path.dirname(os.path.dirname(script_path))
    if sub_path == "":
        raise Exception("Could not get a path to copy this file to: %s" % path)
    dest_path = os.path.join(root_of_export, sub_path)
    return dest_path


def get_simple_dest_path(path):
    # hrj_0290/work/jason/nuke/renders/comp/hrj_0290_comp_v0004/hrj_0290_comp_v0004.%04d.exr
    # ELEMENTS/hrj_0290_graphics_territory_comp_v0004/hrj_0290_graphics_territory_comp_v0004.%04d.exr
    filename = os.path.basename(path)
    comp_filename = "E_%(shot)s_graphics_territory_%(label)s_%(version)s.%(ext_and_frame)s"
    comp_foldername = "E_%(shot)s_graphics_territory_%(label)s_%(version)s"
    dic = {"shot": get_shot_name(filename),
           "label": get_label(filename),
           "ext_and_frame": get_ext_and_frame(filename),
           "version": global_version}
    new_filename = comp_filename % dic
    new_foldername = comp_foldername % dic
    new_sub_path = os.path.join("ELEMENTS", new_foldername, new_filename)
    return new_sub_path


def get_shot_name(path):
    regex = re.compile("([a-zA-Z]{3}_[0-9]{4})", re.IGNORECASE)
    shot_search = re.search(regex, path)
    if len(shot_search.groups()) == 1:
        return shot_search.group(1)
    else:
        raise Exception("Could not find shotname in: %s" % (path))


def get_label(path):
    regex = re.compile("[a-zA-Z]{3}_[0-9]{4}(.*)v\d*", re.IGNORECASE)
    shot_search = re.search(regex, path)
    if len(shot_search.groups()) == 1:
        label = shot_search.group(1)
        camelcase = camelcase_string(label)
        return camelcase
    else:
        raise Exception("Could not find descriptive label in: %s" % (path))


def camelcase_string(s):
    parts = s.split("_")
    camelcase = ""
    for part in parts:
        camelcase += part.title()
    if len(camelcase) != 0:
        camelcase = camelcase[0].lower() + camelcase[1:]
    return camelcase


def get_ext_and_frame(path):
    frame = None
    regex = re.compile(".*[._-](\d+)\.[^.]+$", re.IGNORECASE)
    frame_search = re.search(regex, path)
    if frame_search and len(frame_search.groups()) == 1:
        frame = frame_search.group(1)
    ext = os.path.splitext(path)[1]
    if frame:
        return frame + ext
    else:
        return ext


def get_version_str(path):
    regex = re.compile("(v\d+)", re.IGNORECASE)
    version_search = re.search(regex, path)
    if len(version_search.groups()) == 1:
        version_str = version_search.group(1)
        return version_str
    else:
        raise Exception("Could not find version str in: %s" % (path))


def get_ingest_dest_path(path):
    filename = os.path.basename(path)
    foldername = os.path.basename(os.path.dirname(path))
    new_location = os.path.join("ELEMENTS", foldername, filename)
    return new_location


def get_lighting_dest_path(path):
    filename = os.path.basename(path)
    dic = get_lighting_parts(filename)
    if dic['desc']:
        lighting_folder = "E_%(shot)s_graphics_territory_%(element)s_%(position)s_%(desc)s_%(pass)s_%(version)s"
    else:
        lighting_folder = "E_%(shot)s_graphics_territory_%(element)s_%(position)s_%(pass)s_%(version)s"
    if dic['frame']:
        lighting_file = lighting_folder + ".%(frame)s.%(ext)s"
    else:
        lighting_file = lighting_folder + ".%(ext)s"
    new_filename = lighting_file % dic
    new_foldername = lighting_folder % dic
    new_sub_path = os.path.join("ELEMENTS", new_foldername, new_filename)
    return new_sub_path


def get_lighting_parts(filename, report_check = False):
    global report_str
    regex_str = "([a-zA-Z]{3}_[0-9]{4})"  # shot
    regex_str += "_lgt_"
    regex_str += "([a-zA-Z0-9]*)"  # element
    regex_str += "[-._]?"
    regex_str += "([a-zA-Z]?)"  # position
    regex_str += "[-._]?"
    regex_str += "([a-zA-Z0-9]*)"  # lighting dec
    regex_str += "[-._]"
    regex_str += "v[0-9]+"
    regex_str += "[_]?"
    regex_str += "([a-zA-Z0-9_-]*)"  # lighting pass
    regex_str += "[._-]?"
    regex_str += "([0-9]*|%[0-9]+d|#+)"  # frame
    regex_str += "\."
    regex_str += "([^.]+)"  # ext
    regex_str += "$"
    regex = re.compile(regex_str, re.IGNORECASE)
    search = re.search(regex, filename)
    e_str = ""
    if search and len(search.groups()) == 7:
        shot = search.group(1)
        element = search.group(2)
        position = search.group(3)
        desc = search.group(4)
        light_pass = search.group(5)
        frame = search.group(6)
        ext = search.group(7)

        return_dict = {}
        return_dict["shot"] = shot
        return_dict["frame"] = frame
        return_dict["ext"] = ext
        return_dict["element"] = element
        return_dict["position"] = position
        return_dict["desc"] = desc
        return_dict["pass"] = light_pass
        return_dict["version"] = global_version
        if report_check:
            if element.lower() not in accepted_lighting_elements:
                report_str += "Lighting Element '%s' from '%s' not recognised\n" % (element, filename)

            if position.lower() not in accepted_lighting_positions:
                report_str += "Lighting position '%s' from '%s' not recognised\n" % (position, filename)

            if desc and desc.lower() not in accepted_lighting_desc:
                report_str += "Lighting desc '%s' from '%s' not recognised\n" % (desc, filename)

            if light_pass and light_pass.lower() not in accepted_lighting_passes:
                report_str += "Lighting Pass '%s' from '%s' not recognised\n" % (light_pass, filename)
        return return_dict

        
    else:
        e_str = "Path does not match expected lighting pattern: %s" % filename
    raise Exception(e_str)



def get_quicktime_dest_path(path):
    filename = os.path.basename(path)
    new_location = os.path.join("VIDREF", filename)
    return new_location


def robocopy_files(source_folder, dest_folder, files):
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)
    command = ["robocopy.exe"]
    command.append("'%s'" % source_folder)
    command.append("'%s'" % dest_folder)
    for f in files:
        command.append("'%s'" % f)
    command.append("/MT")
    print " ".join(command)
    copied_files = []
    for f in files:
        copied_files.append(os.path.join(dest_folder, os.path.basename(f)))
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if err:
        raise Exception(err)
    return copied_files

def rename_files(sources, dests):
    for i in range(0, len(sources)):
        s = sources[i]
        d = dests[i]
        if "clientIO" not in s: 1/0
        if "clientIO" not in d: 1/0
        os.rename(s, d)


main()
