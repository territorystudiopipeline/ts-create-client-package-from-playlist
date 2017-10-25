import json
import os
import re
import sgtk
import subprocess
import sgtk.util.shotgun as sg
from tank_vendor.shotgun_authentication import ShotgunAuthenticator
import datetime as dt
import filecmp
import glob
from shutil import copyfile


new_lighting_pass_file_name = "E_%(shot)s_graphics_territory_lgt_%(element)s_%(desc)s_%(pass)s_%(version)s.%04d.%(ext)s"


accepted_lighting_elements = ['core', 'console', 'driftlink', 'flower']

accepted_lighting_positions = ['l', 'c', 'r']

accepted_lighting_desc = ['rgba', 'lines', 'ui', 'protractor', 'text3d', 'miscUI', 'neuralNet', 'solid']

accepted_lighting_passes = ['colour_passes', 'beauty', 'alpha', 'direct_diffuse',
                            'direct_specular', 'diffuse_albedo', 'indirect_diffuse', 'ambient',
                            'indirect_specular', 'reflection', 'refraction', 'z', 'n', 'rgba',
                            'refraction_opacity', 'crypto_material', 'depth', 'emission',
                            'normals', 'p', 'pref', 'vector', 'id_1', 'id_2', 'id_3', 'id_4', 'id_5', 'id_6',
                            'id_01', 'id_02', 'id_03', 'id_04', 'id_05', 'id_06', 'text3d']

global_version = "v000"

report_str = "Warnings:\n"


def main():
    global report_str
    global global_version
    script = get_nuke_script()
    global_version = get_version_str(script)
    read_nodes = get_valid_read_nodes()
    report_str += "\nExport History:\n"
    path_mapings = []
    i = 1
    for node in read_nodes:
        path_mapings.append(localise_read_node(node))
        i += 1
        print "%d/%d\n\n" % (i, len(read_nodes))
    replace_reads(path_mapings)
    update_shotgun()


def replace_reads(mappings):
    script_path = get_nuke_script()
    nu_script = script_path[:-3] + "_localised.nk"
    filedata = ""
    # Read in the file
    with open(nu_script, 'r') as file:
        filedata = file.read()
    for mapping in mappings:
        if not mapping[1]:
            continue
        # Replace the target string
        mapping[0] = mapping[0].replace("\\", "/")
        mapping[1] = mapping[1].replace("\\", "/")
        if "ELEMENTS" in mapping[1]:
            mapping[1] = "../ELEMENTS" + mapping[1].split("ELEMENTS")[1]
        if "GEOM" in mapping[1]:
            mapping[1] = "../GEOM" + mapping[1].split("GEOM")[1]
        if "VIDREF" in mapping[1]:
            mapping[1] = "../VIDREF" + mapping[1].split("VIDREF")[1]

        mapping[0] = mapping[0].replace("Y:", "//ldn-fs1/projects")
        mapping[0] = mapping[0].replace("######", "%06d")
        mapping[0] = mapping[0].replace("#####", "%05d")
        mapping[0] = mapping[0].replace("####", "%04d")
        mapping[0] = mapping[0].replace("###", "%03d")
        filedata = filedata.replace(mapping[0], mapping[1])
        print "REPLACE", mapping[0], mapping[1]

        mapping[0] = mapping[0].replace("Y:", "//ldn-fs1/projects")
        mapping[0] = mapping[0].replace("%06d", "######")
        mapping[0] = mapping[0].replace("%05d", "#####")
        mapping[0] = mapping[0].replace("%04d", "####")
        mapping[0] = mapping[0].replace("%03d", "###")
        filedata = filedata.replace(mapping[0], mapping[1])
        print "REPLACE", mapping[0], mapping[1]

        mapping[0] = mapping[0].replace("//ldn-fs1/projects", "Y:")
        mapping[0] = mapping[0].replace("######", "%06d")
        mapping[0] = mapping[0].replace("#####", "%05d")
        mapping[0] = mapping[0].replace("####", "%04d")
        mapping[0] = mapping[0].replace("###", "%03d")
        filedata = filedata.replace(mapping[0], mapping[1])
        print "REPLACE", mapping[0], mapping[1]

        mapping[0] = mapping[0].replace("//ldn-fs1/projects", "Y:")
        mapping[0] = mapping[0].replace("%06d", "######")
        mapping[0] = mapping[0].replace("%05d", "#####")
        mapping[0] = mapping[0].replace("%04d", "####")
        mapping[0] = mapping[0].replace("%03d", "###")
        filedata = filedata.replace(mapping[0], mapping[1])
        print "REPLACE", mapping[0], mapping[1]

    # Write the file out again
    with open(nu_script, 'w') as file:
        file.write(filedata)

    new_script_path = get_new_nuke_script()
    os.remove(get_nuke_script())
    os.remove(get_json_path())
    if os.path.exists(new_script_path):
        os.remove(new_script_path)
    os.rename(nu_script, new_script_path)



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
    publish_file = sgc.find_one("PublishedFile", [['id', 'is', int(pub_id)]], ['project', 'sg_notes'])
    note = {}
    note['subject'] = 'Exported %s to %s' % (dt.datetime.now().strftime('%y/%m/%d %H:%M'),
                                             os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(get_nuke_script())))))
    note['content'] = report_str
    note['project'] = publish_file['project']
    note = sgc.create("Note", note)
    new_data = {'sg_notes': publish_file['sg_notes'] + [note]}
    sgc.update("PublishedFile", int(pub_id), new_data)


def check_missmatching_versions(read_nodes):
    # print "check_missmatching_versions"
    paths = {}

    for node in read_nodes:
        path = get_read_node_path(node)
        path = os.path.basename(path)
        if not is_ingest(path):
            path_without_version = get_path_without_version(path)
            # print path, path_without_version
            if path_without_version not in paths:
                paths[path_without_version] = {path: [node]}
            elif path in paths[path_without_version].keys():
                paths[path_without_version][path].append(node)
            else:
                paths[path_without_version][path] = [node]
    e_str = ""
    for path in paths.keys():
        if len(paths[path]) != 1:
            for p in paths[path]:
                for n in paths[path][p]:
                    e_str += " %s," % n['name']
                e_str = e_str[:-1] + " %s\n" % (p)
    if e_str != "":
        # print "x10"
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

def get_new_nuke_script():
    path = get_nuke_script()
    folder = os.path.dirname(path)
    script = os.path.basename(path)
    new = "F_%(shot)s_comp_territoryScript_%(version)s.nk"
    dic = {"shot": get_shot_name(script).lower(),
           "version": get_version_str(script)}

    return os.path.join(folder, new % dic)


def localise_path(path):
    if os.name == "posix":
        path = path.replace("\\", "/")
        path = path.replace("//192.168.50.10/filmshare/", "/Volumes/Filmshare/")
        path = path.replace("//ldn-fs1/projects/", "/Volumes/projects/")
    else:
        path = path.replace("/", "\\")
        path = path.replace("Y:", "\\\\ldn-fs1\\projects")
        path = path.replace("\\Volumes\\Filmshare", "\\\\192.168.50.10\\filmshare\\")
        path = path.replace("\\Volumes\\projects", "\\\\ldn-fs1\\projects\\")
    return path


def get_json_data():
    json_path = get_json_path()

    data = None
    with open(json_path) as data_file:
        data = json.load(data_file)
    return data


def get_json_path():
    return os.path.join(os.path.dirname(get_nuke_script()), "valid_nodes.json")


def get_valid_read_nodes():
    global report_str
    data = get_json_data()
    report_str += data['report']
    return data['nodes']


def has_missing_files(node):
    all_files = get_source_files(node)
    for file in all_files:
        f = localise_path(file)
        if not os.path.exists(f):
            # print "---d--", f
            return True
    return False


def is_enabled(read_node):
    return read_node['disable'] == 0


def matches_expected_pattern(read_node):
    global report_str
    path = get_read_node_path(read_node)

    matched = (is_ingest(path) or
               is_comp(path) or
               is_lighting(path) or
               is_quicktime(path) or
               is_precomp(path) or
               is_camera(path) or
               is_geo(path))
    if is_lighting(path):
        # report on validity
        get_lighting_parts(path, report_check=True)
    if not matched:
        report_str += "Path does not match any expected patterns: %s\n" % path
        report_str += "Patterns:\n"
        report_str += "*\\ingest\\*\n"
        report_str += "*_comp_*\n"
        report_str += "*_precomp_*\n"
        report_str += "*_lgt_*\n"
        report_str += "*_cameratrack_*\n"
        report_str += "*_lod[1-6]00_*\n"
        report_str += "*.mov\n"
        report_str += "\n"

    return path.startswith("..") == False


def is_camera(path):
    return "_cameratrack_" in os.path.basename(path).lower()


def is_geo(path):
    pattern = re.compile(".*[-_.]lod[1-6]00[-_.].*")
    return bool(pattern.match(os.path.basename(path)))


def is_ingest(path):
    return "ingest" in get_folders_of_path(path)


def get_folders_of_path(path):
    folders = []
    while 1:
        path, folder = os.path.split(path)

        if folder != "":
            folders.append(folder.lower())
        else:
            if path != "":
                folders.append(path.lower())

            break

    folders.reverse()
    return folders


def is_comp(path):
    return "_comp_" in os.path.basename(path).lower()


def is_lighting(path):
    is_it = "_lgt_" in os.path.basename(path).lower()
    return is_it


def is_quicktime(path):
    return ".mov" == os.path.splitext(path)[1].lower()


def is_precomp(path):
    return "_precomp_" in os.path.basename(path).lower()


def localise_read_node(read_node):
    global report_str
    print "Start localise for %s" % get_read_node_path(read_node)
    path = get_read_node_path(read_node)
    final_dest_path = get_dest_path(path)

    r = "\n"
    r += "%s\n" % read_node['name']
    if read_node.get('first') and read_node.get('last'):
        r += "Localised range: %d-%d\n" % (read_node['first'], read_node['last'])

    source_files = get_source_files(read_node)
    dest_files = get_dest_files(read_node, final_dest_path)
    # dest_files = []
    # for source_file in source_files:
    #     dest_files.append(get_dest_path(source_file, path))

    source_files, dest_files = filter_already_existing(source_files, dest_files)
    done = False
    if len(source_files):
        done = basic_copy(source_files, dest_files)
        # copied_files = robocopy_files(os.path.dirname(source_files[0]),
        #                                os.path.dirname(dest_files[0]),
        #                                source_files)

        # rename_files(copied_files, dest_files)

    r += "Localised filenames renamed from/to:\n"
    r += "%s\n" % os.path.basename(path)
    if done:
        r += "-->\n"
    else:
        r += "-/->\n"
    r += "%s\n" % os.path.basename(final_dest_path)
    report_str += r
    print r
    if done:
        return [path, final_dest_path]
    else:
        return [path, final_dest_path]


def filter_already_existing(source_files, dest_files):
    ss = []
    dd = []
    for i in range(0, len(source_files)):
        s = source_files[i]
        d = dest_files[i]
        if os.path.exists(s) and os.path.exists(d):
            if not filecmp.cmp(s, d):
                ss.append(s)
                dd.append(d)
        else:
            ss.append(s)
            dd.append(d)
    return ss, dd


def get_read_node_path(read_node):
    p = read_node['file']
    p = localise_path(p)
    return p


def get_source_files(read_node):
    files = []
    orig_path = get_read_node_path(read_node)
    path = orig_path
    if "######" in path:
        path = path.replace("######", "%06d")
    if "#####" in path:
        path = path.replace("#####", "%05d")
    if "####" in path:
        path = path.replace("####", "%04d")
    if "###" in path:
        path = path.replace("###", "%03d")
    if "%" in path:
        # print "YES"

        for r in range(int(read_node['first']), int(read_node['last'])):
            # print path , r
            files.append(path % r)
        # if len(files) == 0:
        #     # print "GLOB", path.split("%")[0] + "[0-9]*" + path.split("%")[1][3:]
        #     files = glob.glob(path.split("%")[0] + "[0-9]*" + path.split("%")[1][3:])

    elif not path.endswith(".mov"):
        # print "NO"
        files = [orig_path]
    return files


def get_dest_files(read_node, dest_path):
    files = []
    path = dest_path
    if "######" in path:
        path = path.replace("######", "%06d")
    if "#####" in path:
        path = path.replace("#####", "%05d")
    if "####" in path:
        path = path.replace("####", "%04d")
    if "###" in path:
        path = path.replace("###", "%03d")
    if "%" in path:
        for r in range(int(read_node['first']), int(read_node['last'])):
            # print path , r, os.path.exists(path % r)
            files.append(path % r)
        # if len(files) == 0:
        #     # print "GLOB", path.split("%")[0] + "[0-9]*" + path.split("%")[1][3:]
        #     files = glob.glob(path.split("%")[0] + "[0-9]*" + path.split("%")[1][3:])

    elif not path.endswith(".mov"):
        # print "NO"
        files = [dest_path]
    return files


def is_sequence(path):
    pattern = re.compile("(?:[._-]?\d+|[._-]?\%\d+d|[._-]?#+).([^.]+)$")
    return bool(re.search(pattern, os.path.basename(path)))


def get_dest_path(path):
    sub_path = get_simple_dest_path(path)
    # if is_quicktime(path):
    #     sub_path = get_qt_dest_path(path)
    # el


    # if is_comp(path):
    #     sub_path = get_simple_dest_path(path)
    # elif is_precomp(path):
    #     sub_path = get_simple_dest_path(path)
    # elif is_lighting(path):
    #     sub_path = get_lighting_dest_path(path)
    if is_geo(path):
        sub_path = get_geo_dest_path(path)


    # elif is_camera(path):
    #     sub_path = get_camera_dest_path(path)
    # elif is_ingest(path):
    #     sub_path = get_ingest_dest_path(path)

    # if special_rename(path):
    #     sub_path = special_rename(path)
    # el
    if not sub_path:
        sub_path = get_non_rename_dest_path(path)


    sub_path = sub_path.replace("__", "_")
    script_path = get_nuke_script()
    root_of_export = os.path.dirname(os.path.dirname(script_path))

    dest_path = os.path.join(root_of_export, sub_path)
    return dest_path


def get_non_rename_dest_path(path):
    new_filename = os.path.basename(path)
    ##########################
    version = get_version_str(new_filename)
    ext_and_frame = get_ext_and_frame(new_filename)
    if version not in ['', None]:
        new_filename = new_filename.replace(version, "")
        new_filename = new_filename.replace("s" + version[1:], "")
    new_filename = new_filename.replace(ext_and_frame, "")
    new_filename = "E_" + new_filename + "_" + version + "." + ext_and_frame
    for a in ['-', '_', '.']:
        for aa in ['-', '_', '.']:
            f = a + aa
            r = aa
            if "." in f:
                r = '.'
            new_filename = new_filename.replace(f, r)
    new_filename = new_filename.replace(".v", "_v")
    new_filename = new_filename.replace("E_s_", "E_")
    new_filename = "_".join(new_filename.split("_")[:3]+["graphics", "territory"]+new_filename.split("_")[3:])

    ##########################



    parts_of_filename = re.split("[._-]?", new_filename)
    if len(parts_of_filename) == 1:
        new_foldername = parts_of_filename[0]
    elif len(parts_of_filename) == 2:
        new_foldername = parts_of_filename[0]
    elif len(parts_of_filename) >= 3:
        if bool(re.match("^([0-9]*|%[0-9]+d|#+)$", parts_of_filename[-2])):
            new_foldername = new_filename[:-(len(parts_of_filename[-1]) + len(parts_of_filename[-2]) + 2)]
        else:
            new_foldername = new_filename[:-(len(parts_of_filename[-1]) + 1)]



    if new_filename.endswith(".abc"):
        new_sub_path = os.path.join("GEOM", new_foldername, new_filename)
    else:
        new_sub_path = os.path.join("ELEMENTS", new_foldername, new_filename)

    return new_sub_path


def get_qt_dest_path(path):
    filename = os.path.basename(path)
    new_sub_path = os.path.join("VIDREF", filename)
    return new_sub_path


def get_geo_dest_path(path):
    filename = os.path.basename(path)
    geo_filename = "GCH_%(shot)s_graphics_territory_%(label)s_%(version)s.%(ext_and_frame)s"
    geo_foldername = "GCH_%(shot)s_graphics_territory_%(label)s_%(version)s"
    dic = {"shot": get_shot_name(filename),
           "label": get_label(filename),
           "ext_and_frame": get_ext_and_frame(filename),
           "version": get_rename_version_str(path)}
    if None in dic.values():
        return None
    new_filename = geo_filename % dic
    new_foldername = geo_foldername % dic
    new_sub_path = os.path.join("GEOM", new_foldername, new_filename)
    return new_sub_path


def get_simple_dest_path(path):
    # hrj_0290/work/jason/nuke/renders/comp/hrj_0290_comp_v0004/hrj_0290_comp_v0004.%04d.exr
    # ELEMENTS/hrj_0290_graphics_territory_comp_v0004/hrj_0290_graphics_territory_comp_v0004.%04d.exr
    filename = os.path.basename(path)
    comp_filename = "E_%(shot)s_graphics_territory_%(label)s_%(version)s.%(ext_and_frame)s"
    comp_foldername = "E_%(shot)s_graphics_territory_%(label)s_%(version)s"

    dic = {"shot": get_shot_name(filename).lower(),
           "label": get_simple_label(filename),
           "ext_and_frame": get_ext_and_frame(filename),
           "version": get_rename_version_str(path)}

    if None in dic.values():
        return None

    new_filename = comp_filename % dic
    new_filename = remove_double_spaces(new_filename, preference=".")
    new_foldername = comp_foldername % dic
    new_foldername = remove_double_spaces(new_foldername, preference="_")

    if new_filename.endswith(".abc"):
        new_sub_path = os.path.join("GEOM", "GCH" + new_foldername[1:], "GCH" + new_filename[1:])
    else:
        new_sub_path = os.path.join("ELEMENTS", new_foldername, new_filename)
    return new_sub_path


def remove_double_spaces(filename, preference=None):
    for a in ['-', '_', '.']:
        for aa in ['-', '_', '.']:
            f = a + aa
            r = aa
            if preference and preference in f:
                r = preference
            filename = filename.replace(f, r)
        filename = filename.strip(a)
    return filename


def get_simple_label(filename):
    # label = filename.lower()
    label = filename
    label = label.replace(get_shot_name(label), "")
    label = label.replace(get_rename_version_str(label), "")
    label = label.replace(get_shot_name(label), "")
    label = label.replace(get_ext_and_frame(label), "")
    label = label.replace("_lgt_", "")
    label = label.replace("_LGT_", "")
    label = label.replace("_lyt_", "_")
    label = label.replace("_LYT_", "_")
    if label.lower().startswith("e_"):
        label = label[2:]
    # if label.startswith("s_"):
    #     label = label[2:]
    if label.lower().startswith("ghc_"):
        label = label[4:]
    if label.lower().startswith("lyt_"):
        label = label[4:]
    if label.lower().startswith("lgt_"):
        label = label[4:]
    label = label.replace(" ", "_")
    label = remove_double_spaces(label, "_")
    label = remove_double_spaces(label, "_")
    return label


def get_shot_name(path):
    global report_str
    regex = re.compile("([a-zA-Z]{3}_[0-9]{4})", re.IGNORECASE)
    shot_search = re.search(regex, path)
    if shot_search and len(shot_search.groups()) == 1:
        return shot_search.group(1)
    script_shot_name = re.search(regex, get_nuke_script())
    if script_shot_name and len(script_shot_name.groups()) == 1:
        return script_shot_name.group(1)
    else:
        report_str += "Could not find shotname in: %s\n"
        return ""


def get_label(path):
    global report_str
    regex = re.compile("[a-zA-Z]{3}_[0-9]{4}(.*)v\d*", re.IGNORECASE)
    shot_search = re.search(regex, path)
    if len(shot_search.groups()) == 1:
        label = shot_search.group(1)
        camelcase = camelcase_string(label)
        return camelcase
    else:
        report_str += "Could not find descriptive label in: %s\n"


def camelcase_string(s):
    # parts = s.split("_")
    # camelcase = ""
    # for part in parts:
    #     camelcase += part.title()
    # if len(camelcase) != 0:
    #     camelcase = camelcase[0].lower() + camelcase[1:]
    return s


def get_ext_and_frame(path):
    frame = None
    regex = re.compile(".*([-_.]\d+|#+|%\d+d)\.[^.]+$", re.IGNORECASE)
    frame_search = re.search(regex, path)
    if frame_search and len(frame_search.groups()) == 1:
        frame = frame_search.group(1)
    ext = os.path.splitext(path)[1]
    if frame:
        return frame + ext
    else:
        return ext


def get_rename_version_str(path):
    # if is_ingest(path):
    return get_version_str(path)
    # else:
    #     return global_version


def get_version_str(path):
    regex = re.compile(".*[-._ ](v\d+)[ -._].*", re.IGNORECASE)
    version_search = re.search(regex, path)
    if version_search and len(version_search.groups()) == 1:
        version_str = version_search.group(1)
        return version_str
    regex = re.compile(".*[-._](s\d+)[-._].*", re.IGNORECASE)
    version_search = re.search(regex, path)
    if version_search and len(version_search.groups()) == 1:
        version_str = version_search.group(1)
        if version_str not in [None, '']:
            version_str = 'v' + version_str[1:]
        return version_str
    else:
        return "v0001"



def get_ingest_dest_path(path):
    filename = os.path.basename(path)
    foldername = os.path.basename(os.path.dirname(path))
    new_location = os.path.join("ELEMENTS", foldername, filename)
    return new_location


def get_lighting_dest_path(path):
    dic = get_lighting_parts(path)
    if dic == {}:
        return
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


def get_lighting_parts(path, report_check=False):
    global report_str
    filename = os.path.basename(path)
    regex_str = "([a-zA-Z]{3}_[0-9]{4})"  # shot
    regex_str += "_lgt_"
    regex_str += "([a-zA-Z0-9]*)"  # element
    regex_str += "[-._]?"
    regex_str += "([a-zA-Z]?)"  # position
    regex_str += "[-._]?"
    regex_str += "([a-zA-Z0-9]*)"  # lighting dec
    regex_str += "[-._]"
    regex_str += "v[0-9]+"
    regex_str += "[-._]?[_]?"
    regex_str += "([a-zA-Z0-9_-]*?)"  # lighting pass
    regex_str += "[._-]?[._-]?"
    regex_str += "([0-9]*|%[0-9]+d|#+)"  # frame
    regex_str += "\."
    regex_str += "([^.]+)"  # ext
    regex_str += "$"
    regex = re.compile(regex_str, re.IGNORECASE)
    search = re.search(regex, filename)
    e_str = ""
    return_dict = {}
    if search and len(search.groups()) == 7:
        shot = search.group(1)
        element = search.group(2)
        position = search.group(3)
        desc = search.group(4)
        light_pass = search.group(5)
        frame = search.group(6)
        ext = search.group(7)

        return_dict["shot"] = shot
        return_dict["frame"] = frame
        return_dict["ext"] = ext
        return_dict["element"] = element
        return_dict["position"] = position
        return_dict["desc"] = desc
        return_dict["pass"] = light_pass
        return_dict["version"] = get_rename_version_str(path)
        if report_check:
            if element.lower() not in accepted_lighting_elements:
                report_str += "Lighting Element '%s' from '%s' not recognised\n" % (element, filename)

            if position.lower() not in accepted_lighting_positions:
                report_str += "Lighting position '%s' from '%s' not recognised\n" % (position, filename)

            if desc and desc.lower() not in accepted_lighting_desc:
                report_str += "Lighting desc '%s' from '%s' not recognised\n" % (desc, filename)

            if light_pass and light_pass.lower() not in accepted_lighting_passes:
                report_str += "Lighting Pass '%s' from '%s' not recognised\n" % (light_pass, filename)

    else:
        report_str += "Path does not match expected lighting pattern: %s\n" % filename
    return return_dict



def get_quicktime_dest_path(path):
    filename = os.path.basename(path)
    new_location = os.path.join("VIDREF", filename)
    return new_location


def basic_copy(sources, dests):
    done = False
    dest_folder = os.path.dirname(dests[0])
    for i in range(0, len(sources)):
        s = sources[i]
        d = dests[i]
        if "client_io" not in d:
            raise Exception("You are exporting outside of the client_io folder. What?")
        print s, os.path.exists(s)
        if os.path.exists(s) and not os.path.exists(d):
            print os.path.basename(s), "-->", os.path.basename(d)
            if not os.path.exists(dest_folder):
                os.makedirs(dest_folder)
            copyfile(s, d)
        if not done and os.path.exists(d):
            done = True
    return done

def robocopy_files(source_folder, dest_folder, files):

    print dest_folder
    print dest_folder
    print dest_folder
    print dest_folder
    print dest_folder
    print os.path.exists(dest_folder)
    print os.path.exists(dest_folder)
    print os.path.exists(dest_folder)
    print os.path.exists(dest_folder)
    print os.path.exists(dest_folder)
    print os.path.exists(dest_folder)

    print os.path.isdir(dest_folder)
    print os.path.isdir(dest_folder)
    print os.path.isdir(dest_folder)
    print os.path.isdir(dest_folder)
    print os.path.isdir(dest_folder)
    print os.path.isdir(dest_folder)

    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)

    print dest_folder
    print dest_folder
    print dest_folder
    print dest_folder
    print dest_folder
    print os.path.exists(dest_folder)
    print os.path.exists(dest_folder)
    print os.path.exists(dest_folder)
    print os.path.exists(dest_folder)
    print os.path.exists(dest_folder)
    print os.path.exists(dest_folder)

    print os.path.isdir(dest_folder)
    print os.path.isdir(dest_folder)
    print os.path.isdir(dest_folder)
    print os.path.isdir(dest_folder)
    print os.path.isdir(dest_folder)
    print os.path.isdir(dest_folder)

    command = ["robocopy.exe"]
    command.append("%s" % source_folder)
    command.append("%s" % dest_folder)
    for f in files:
        command.append("%s" % os.path.basename(f))
    command.append("/MT")
    copied_files = []

    for f in files:
        copied_files.append(os.path.join(dest_folder, os.path.basename(f)))
    print " ".join(command)
    p = subprocess.Popen(command)
    out, err = p.communicate()
    print out
    print err
    if err:
        raise Exception(err)
    return copied_files


def rename_files(sources, dests):
    for i in range(0, len(sources)):
        s = sources[i]
        d = dests[i]
        if s == d:
            return
        if "client_io" not in s:
            1 / 0
        if "client_io" not in d:
            1 / 0
        print s, ">>>", d
        if os.path.exists(d):
            print "FILE EXISTS"
            if filecmp.cmp(s, d):
                print "DELETE IT"
                os.remove(s)
                print "I DELETED IT"
            else:
                print "DONT DELETE IT"
                raise Exception("Cannot rename beacuse another file already exists: %s" % d)
        else:
            os.rename(s, d)


main()
