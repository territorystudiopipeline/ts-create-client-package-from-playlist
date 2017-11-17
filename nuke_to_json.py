import nuke
import os
import re
import sys
import sgtk
import subprocess
import sgtk.util.shotgun as sg
from tank_vendor.shotgun_authentication import ShotgunAuthenticator
import datetime as dt
import filecmp
import nukescripts
import json
import traceback
import glob
import cryptomatte_utilities as cu
from shutil import copy2

new_lighting_pass_file_name = "E_%(shot)s_graphics_territory_lgt_%(element)s_%(desc)s_%(pass)s_%(version)s.%04d.%(ext)s"


accepted_lighting_elements = ['core', 'console', 'driftlink', 'flower', 'chevron', 'chevrons']

accepted_lighting_positions = ['l', 'c', 'r']

accepted_lighting_desc = ['rgba', 'lines', 'ui', 'protractor', 'text3d', 'miscui', 'neuralnet', 'solid']

accepted_lighting_passes = ['colour_passes', 'beauty', 'alpha', 'direct_diffuse',
                            'direct_specular', 'diffuse_albedo', 'indirect_diffuse',
                            'indirect_specular', 'reflection', 'refraction', 'z', 'n',
                            'refraction_opacity', 'crypto_material', 'depth', 'emission',
                            'normals', 'p', 'pref', 'vector', 'id_1', 'id_2', 'id_3', 'id_4', 'id_5', 'id_6', 'id_7', 'id_8', 'id_9',
                            'id_01', 'id_02', 'id_03', 'id_04', 'id_05', 'id_06', 'id_07', 'id_08', 'id_09', 'id_10', 'text3d']

global_version = "v000"

report_str = "Warnings:\n"


def main():
    global report_str
    copy_script()
    open_script()
    read_nodes = get_valid_read_nodes()
    export_to_json(read_nodes)


    # print "ATTEMPTING TO CLEAR CACHE"
    nukescripts.cache_clear("")
    # print "CLEARTED CACHE"

    # print "ATTEMPTING TO CLOSE SCRIPT"
    nuke.scriptClose()
    # print "CLOSED SCRIPT"

    # report_str += "\nExport History:\n"
    # path_mapings = []
    # for node in read_nodes:
    # for node in read_nodes:
    #     path_mapings.append(localise_read_node(node))
    # replace_reads(path_mapings)
    # update_shotgun()

def copy_script():
    src = get_src_nuke_script()
    dst = get_nuke_script()
    # print src, ">>>>>>>", dst
    if os.path.exists(dst):
        os.remove(dst)
    copy2(src,dst)

def export_to_json(nodes):
    # print "STARTING JSON DUMP"
    json_data = get_json_data(nodes)
    json_path = os.path.join(os.path.dirname(get_nuke_script()), get_nuke_script() + "_valid_nodes.json")
    with open(json_path, 'w') as outfile:
        json.dump(json_data, outfile)
    # print "FINISHING JSON DUMP"


def get_json_data(nodes):
    json_data = {"report": report_str, "nodes": []}
    for node in nodes:
        node_data = {}
        node_data['file'] = node['file'].getValue()
        node_data['name'] = node.fullName()
        if node.knob('first'):
            f = node['first'].getValue()
            gf = nuke.Root()['first_frame'].getValue()
            # if f <= gf:
            #     f = gf
            node_data['first'] = f
        if node.knob('last'):
            l = node['last'].getValue()
            gl = nuke.Root()['last_frame'].getValue()
            # if l >= gl:
            #     l = gl
            node_data['last'] = l
        json_data['nodes'].append(node_data)
    return json_data


def open_script():
    global global_version
    script = get_nuke_script()
    global_version = get_version_str(script)

    # print "START OPENING"
    nuke.scriptReadFile(script)
    # print "FINISH OPENING"
    # print "-----------------delete-xreads----starting-----------"
    delete_x_reads()
    # print "-----------------delete-xreads----finished----------"
    # print "-----------------decryptomatte----starting-----------"
    cu.decryptomatte_all()
    # print "-----------------decryptomatte----finished----------"
    # print "-----------------convertGizmosToGroups----starting-----------"
    bakeGizmos()
    # print "-----------------convertGizmosToGroups----finished----------"
    s = nuke.root()
    s.knob('project_directory').setValue("[file dirname [value root.name]]")
    nu_script = script[:-3] + "_localised.nk"
    if os.path.exists(nu_script):
        os.remove(nu_script)
    try:
        # print "START SAVING"
        nuke.scriptSaveAs(nu_script)
        # print "COMPLETED SAVING"
    except Exception:
        pass
        # print "ERROR WHILE SAVING"


def delete_x_reads():
    classes = ["Read", "ReadGeo", "ReadGeo2", "Camera", "Camera2"]
    for node in get_all_nodes():
        if node['name'].getValue().startswith("x_") and node.Class() in classes:
            nuke.delete(node)

# def replace_reads(mappings):
#     script_path = get_nuke_script()
#     nu_script = script_path[:-3]+"_localised.nk"
#     filedata = ""
#     # Read in the file
#     with open(nu_script, 'r') as file :
#       filedata = file.read()
#     for mapping in mappings:
#         # Replace the target string
#         mapping[0] = mapping[0].replace("\\","/")
#         mapping[1] = mapping[1].replace("\\","/")
#         if "ELEMENTS" in mapping[1]:
#             mapping[1] = "../ELEMENTS" + mapping[1].split("ELEMENTS")[1]
#         if "GEOM" in mapping[1]:
#             mapping[1] = "../GEOM" + mapping[1].split("GEOM")[1]
#         if "VIDREF" in mapping[1]:
#             mapping[1] = "../VIDREF" + mapping[1].split("VIDREF")[1]
#         filedata = filedata.replace(mapping[0], mapping[1])
#     # Write the file out again
#     with open(nu_script, 'w') as file:
#       file.write(filedata)

#     os.remove(get_nuke_script())
#     os.rename(nu_script, get_nuke_script())


# def get_shotgun_connection():
#     # Instantiate the CoreDefaultsManager. This allows the ShotgunAuthenticator to
#     # retrieve the site, proxy and optional script_user credentials from shotgun.yml
#     cdm = sgtk.util.CoreDefaultsManager()

#     # Instantiate the authenticator object, passing in the defaults manager.
#     authenticator = ShotgunAuthenticator(cdm)

#     # Create a user programmatically using the script's key.
#     user = authenticator.create_script_user(
#         api_script="toolkit_scripts",
#         api_key="09d648cbb268019edefd1db3f1a8d8ea011c354326f23f24d13c477d75306810"
#     )

#     # Tells Toolkit which user to use for connecting to Shotgun.
#     sgtk.set_authenticated_user(user)
#     sgc = sg.create_sg_connection()
#     return sgc

# def update_shotgun():
#     pub_id = os.environ.get("SHOTGUN_PUBLISHED_FILE_ID")
#     sgc = get_shotgun_connection()
#     publish_file = sgc.find_one("PublishedFile",[['id', 'is', int(pub_id)]], ['project', 'sg_notes'])
#     note = {}
#     note['subject'] = 'Exported %s to %s' % (dt.datetime.now().strftime('%y/%m/%d %H:%M'),
#                                              os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(get_nuke_script())))))
#     note['content'] = report_str
#     note['project'] = publish_file['project']
#     note = sgc.create("Note", note)
#     new_data = {'sg_notes' : publish_file['sg_notes'] + [note]}
#     sgc.update("PublishedFile",int(pub_id), new_data)

# def check_missmatching_versions(read_nodes):
#     paths = {}

#     for node in read_nodes:
#         path = get_read_node_path(node)
#         path = os.path.basename(path)
#         if not is_ingest(path):
#             path_without_version = get_path_without_version(path)
#             if path_without_version not in paths:
#                 paths[path_without_version] = {path: [node]}
#             elif path in paths[path_without_version].keys():
#                 paths[path_without_version][path].append(node)
#             else:
#                 paths[path_without_version][path] = [node]
#     e_str = ""
#     for path in paths.keys():
#         if len(paths[path]) != 1:
#             for p in paths[path]:
#                 for n in paths[path][p]:
#                     e_str += " %s," % n.name()
#                 e_str = e_str[:-1] + " %s\n" % (p)
#     if e_str != "":
#         e_str = "Multiple versions of the same element are being used in this script.\n" + e_str
#         raise Exception(e_str)


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

def get_src_nuke_script():
    script = localise_path(os.environ.get("SOURCE_SCRIPT"))
    return script


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


def get_valid_read_nodes():
    global report_str
    all_nodes = get_all_read_nodes()
    fail_on_bad_read_nodes(all_nodes)
    return all_nodes


def fail_on_bad_read_nodes(all_nodes):
    error_messages = []
    mappings = {}
    for node in all_nodes:
        path = node['file'].getValue()
        if path == "":
            continue
        first = 1
        if 'first' in node.knobs().keys():
            first = int(node['first'].getValue())
        last = 1
        if 'last' in node.knobs().keys():
            last = int(node['last'].getValue())

        message = "\n\nNode: %s\nFrames: %d -> %d\nFilename: %s" % (node.fullName(),
                                                                    first,
                                                                    last,
                                                                    path)
        error = ""
        if not get_shot_name(os.path.basename(path)):
            error += "\nERROR: NO SHOT NAME IN FILENAME"
        if path.lower().endswith(".mov"):
            error += "\nERROR: DO NOT READ IN QUICKTIMES"
        if get_version_str(path) is None:
            error += "\nERROR: NO VERSION NUMBER IN FILENAME"
        if is_lyt(path):
            error += "\nERROR: DO NOT USE LAYOUT IN YOUR SCRIPT"
        if is_camera(path) and not is_for_this_shot(path):
            error += "\nERROR: NOT THE CAMERA FOR THIS SHOT"
        if is_disp_map(path) and not is_for_this_shot(path):
            error += "\nERROR: NOT THE DISP MAP FOR THIS SHOT"
        if bad_path(path):
            error += "\nERROR: BAD PATH"
        else:
            if missing_files(node, first, last):
                error += "\nERROR: MISSING FILES"

            src = node['file'].getValue()
            dst = get_dest_path(src)
            if src not in mappings.keys():
                if dst in mappings.values():
                    error += "\nERROR: CLASHING WITH ANOTHER FILENAME"
                    for s, d in mappings.iteritems():
                        if d == dst:
                            error += "\n--> %s" % s
                mappings[src] = dst

        if error != "":
            message += error
            error_messages.append(message)

    shotgun_frame_range = get_shotgun_frame_range()
    scene_frame_range = get_scene_frame_range()
    if shotgun_frame_range != scene_frame_range:
        message = "\nERROR: NUKE SCRIPT HAS INCORRECT FRAME RANGE"
        message += "\nIn the script: %d -> %d" % (scene_frame_range[0], scene_frame_range[1])
        message += "\nOn Shotgun:  %d -> %d" % (shotgun_frame_range[0], shotgun_frame_range[1])
        error_messages.append(message)

    if len(error_messages) == 0:
        print "Passed Error Checking!"
    else:
        r = range(0, 33)
        for i in r:
            print "-" * i
        print "----------ARTIST ERRORS----------"
        for message in error_messages:
            print message
            print "- - - - - - - - -"
        print "---------------------------------"
        r.reverse()
        for i in r:
            print "-" * i
        raise Exception("Kickback To Artist %s" % get_src_nuke_script())
    return all_nodes


def bad_path(path):
    if "######" in path:
        path = path.replace("######", "%06d")
    if "#####" in path:
        path = path.replace("#####", "%05d")
    if "####" in path:
        path = path.replace("####", "%04d")
    if "###" in path:
        path = path.replace("###", "%03d")
    if path.count("%") == 0:
        return False
    if path.count("%") > 1:
        return True
    if path.count("%") == 1:
        rhs = path.split("%")[1]
        if not re.match("\d\dd\..{3,4}$", rhs):
            return True
    return False


def is_lyt(path):
    return "_lyt_" in os.path.basename(path).lower()


def is_for_this_shot(path):
    path_shotname = get_shot_name(os.path.basename(path)).lower()
    script_shotname = get_shot_name(os.path.basename(get_nuke_script())).lower()
    return path_shotname == script_shotname


def is_disp_map(path):
    return "_disp_map_" in os.path.basename(path).lower()


def get_scene_frame_range():
    return nuke.toNode("root")["first_frame"].getValue(), nuke.toNode("root")["last_frame"].getValue()


def get_shotgun_frame_range():
    sgc = get_shotgun_connection()
    shotname = get_shot_name(os.path.basename(get_nuke_script()))
    lower_case_shot = sgc.find_one("Shot", [['project.Project.id', 'is', 186], ['code', 'is', shotname.lower()]], ["sg_ts_head_in", "sg_ts_tail_out"])
    if lower_case_shot:
        return lower_case_shot["sg_ts_head_in"], lower_case_shot["sg_ts_tail_out"]
    upper_case_shot = sgc.find_one("Shot", [['project.Project.id', 'is', 186], ['code', 'is', shotname.upper()]], ["sg_ts_head_in", "sg_ts_tail_out"])
    if upper_case_shot:
        return upper_case_shot["sg_ts_cut_in"], upper_case_shot["sg_ts_tail_out"]


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



def missing_files(node, first, last):
    has_files = False
    all_files = get_source_files(node)
    expected_len = last + 1 - first
    if len(all_files) != expected_len and ("%" in node['file'].getValue() or "#" in node['file'].getValue()):
        return True
    for file in all_files:
        f = localise_path(file)
        if not os.path.exists(f):
            return True
    if len(all_files) == 0:
        return True
    return False


def get_all_read_nodes():
    classes = ["Read", "ReadGeo", "ReadGeo2", "Camera", "Camera2"]
    nodes = []
    for node in get_all_nodes():

        if (not node['name'].getValue().startswith("x_") and
                node.Class() in classes and
                is_enabled(node)):
            path = get_read_node_path(node)
            if os.path.basename(path) == "jaeger_colours_v0002.jpg":
                node['name'].setValue("x_" + node['name'].getValue())
            else:
                nodes.append(node)
    return nodes


def get_all_nodes():
    all_nodes = nuke.allNodes()
    all_group_nodes = nuke.allNodes("Group")
    for g in all_group_nodes:
        all_nodes += nuke.allNodes(group=g)
    return all_nodes


def is_enabled(read_node):
    return read_node['disable'].getValue() == 0


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
    # if not matched:
    #     report_str += "Path does not match any expected patterns: %s\n" % path

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
    path = get_read_node_path(read_node)

    r = "\n"
    r += "%s\n" % read_node.name()
    r += "Localised range: %d-%d\n" % (read_node['first'].getValue(), read_node['last'].getValue())
    report_str += r

    source_files = get_source_files(read_node)
    dest_files = []
    for source_file in source_files:
        dest_files.append(get_dest_path(source_file))

    source_files, dest_files = filter_already_existing(source_files, dest_files)
    if len(source_files):
        copied_files = robocopy_files(os.path.dirname(source_files[0]),
                                      os.path.dirname(dest_files[0]),
                                      source_files)

        rename_files(copied_files, dest_files)

    final_dest_path = get_dest_path(path)
    r = "Localised filenames renamed from/to:\n"
    r += "%s\n" % os.path.basename(path)
    r += "-->\n"
    r += "%s\n" % os.path.basename(final_dest_path)
    report_str += r
    return [path, final_dest_path]


def filter_already_existing(source_files, dest_files):
    ss = []
    dd = []
    for i in range(0, len(source_files)):
        s = source_files[i]
        d = dest_files[i]
        if os.path.exists(d):
            if not filecmp.cmp(s, d):
                ss.append(s)
                dd.append(d)
        else:
            ss.append(s)
            dd.append(d)
    return ss, dd


def get_read_node_path(read_node):
    p = read_node['file'].getValue()
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
        for r in range(int(read_node['first'].getValue()), int(read_node['last'].getValue())+1):
            files.append(path % r)
    elif os.path.isfile(orig_path):
        files = [orig_path]
    return files


def is_sequence(path):
    pattern = re.compile("(?:[._-]\d+|[._-]\%\d+d|[._-]#+).([^.]+)$")
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
    # if is_geo(path):
    #     sub_path = get_geo_dest_path(path)


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
    root_of_export = os.path.dirname(os.path.dirname(os.path.dirname(script_path)))

    dest_path = os.path.join(root_of_export, sub_path)
    # print "DEST PATH: %s" % (dest_path)
    return dest_path



def get_non_rename_dest_path(path):
    new_filename = os.path.basename(path)
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
    if filename.endswith(".exr.exr"):
        filename = filename.replace(".exr.exr", ".exr")
    if filename.endswith("..exr"):
        filename = filename.replace("..exr", ".exr")
    comp_filename = "E_%(shot)s_graphics_territory_%(label)s_%(version)s.%(ext_and_frame)s"
    comp_foldername = "E_%(shot)s_graphics_territory_%(label)s_%(version)s"

    dic = {"shot": get_shot_name(filename),
           "label": get_simple_label(filename),
           "ext_and_frame": get_ext_and_frame(filename),
           "version": get_rename_version_str(path)}

    if dic['shot'] == None:
        dic['shot'] = get_shot_name(get_nuke_script())

    new_filename = comp_filename % dic
    new_filename = remove_double_spaces(new_filename, preference=".")
    new_foldername = comp_foldername % dic
    new_foldername = remove_double_spaces(new_foldername, preference="_")

    if new_filename.endswith(".abc"):
        new_sub_path = os.path.join(dic['shot'].upper(), "GEOM", "GCH" + new_foldername[1:], "GCH" + new_filename[1:])
    else:
        new_sub_path = os.path.join(dic['shot'].upper(), "ELEMENTS", new_foldername, new_filename)
    return new_sub_path


def get_simple_label(filename):
    # label = filename.lower()
    label = filename
    if get_shot_name(label):
        label = label.replace(get_shot_name(label), "")
    label = label.replace(get_rename_version_str(label), "")
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

def get_shot_name(path):
    global report_str
    # print path
    regex = re.compile("([a-zA-Z]{3}_[0-9]{4})", re.IGNORECASE)
    shot_search = re.search(regex, path)
    if shot_search and len(shot_search.groups()) == 1:
        return shot_search.group(1)


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
    regex = re.compile(".*[._-](\d+)\.[^.]+$", re.IGNORECASE)
    frame_search = re.search(regex, path)
    if frame_search and len(frame_search.groups()) == 1:
        frame = frame_search.group(1)
    ext = os.path.splitext(path)[1]
    if frame:
        return frame + ext
    else:
        return ext


def get_rename_version_str(path):
    if is_ingest(path):
        return get_version_str(path)
    else:
        return global_version


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
    regex_str += "[-._]"
    regex_str += "([a-zA-Z0-9]*)"  # lighting dec
    regex_str += "[-._]?"
    regex_str += "v[0-9]+"
    regex_str += "[-._]?[_]?"
    regex_str += "([a-zA-Z0-9_-]*)"  # lighting pass
    regex_str += "[._-][._-]?"
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
        # if report_check:
        #     if element.lower() not in accepted_lighting_elements:
        #         report_str += "Lighting Element '%s' from '%s' not recognised\n" % (element, filename)

        #     if position.lower() not in accepted_lighting_positions:
        #         report_str += "Lighting position '%s' from '%s' not recognised\n" % (position, filename)

        #     if desc and desc.lower() not in accepted_lighting_desc:
        #         report_str += "Lighting desc '%s' from '%s' not recognised\n" % (desc, filename)

        #     if light_pass and light_pass.lower() not in accepted_lighting_passes:
        #         report_str += "Lighting Pass '%s' from '%s' not recognised\n" % (light_pass, filename)

    # else:
    #     report_str += "Path does not match expected lighting pattern: %s\n" % filename
    return return_dict


def get_quicktime_dest_path(path):
    filename = os.path.basename(path)
    new_location = os.path.join("VIDREF", filename)
    return new_location


def robocopy_files(source_folder, dest_folder, files):
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)

    command = ["robocopy.exe"]
    command.append("%s" % source_folder)
    command.append("%s" % dest_folder)
    for f in files:
        command.append("%s" % os.path.basename(f))
    command.append("/MT")
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
        if s == d:
            return
        if "client_io" not in s:
            1 / 0
        if "client_io" not in d:
            1 / 0
        if os.path.exists(d):
            if filecmp.cmp(s, d):
                os.remove(s)
            else:
                raise Exception("Cannot rename beacuse another file already exists: %s" % d)
        else:
            os.rename(s, d)






def getAllNodes(topLevel):
    '''
    recursively return all nodes starting at topLevel. Default topLevel is nuke.root()
    '''
    allNodes = nuke.allNodes(group=topLevel)
    for n in allNodes:
        allNodes = allNodes + getAllNodes(n)
    return allNodes


def getOutputs(node):
    '''
    Return a dictionary of the nodes and pipes that are connected to node
    '''
    # print "getOutputs 0"
    depDict = {}
    # print "getOutputs 1"
    dependencies = node.dependent(nuke.INPUTS | nuke.HIDDEN_INPUTS, forceEvaluate = False)
    # print dependencies
    # print "getOutputs 2"
    for d in dependencies:
        # print "getOutputs 3"
        depDict[d] = []
        # print "getOutputs 4"
        for i in range(d.inputs()):
            # print "getOutputs 5"
            if d.input(i) == node:
                # print "getOutputs 6"
                depDict[d].append(i)
                # print "getOutputs 7"
            # print "getOutputs 8"
        # print "getOutputs 9"
    # print "getOutputs 10"
    return depDict


def isGizmo(node):
    '''
    return True if node is gizmo
    '''
    return 'gizmo_file' in node.knobs()


def gizmoIsDefault(gizmo):
    '''Check if gizmo is in default install path'''
    installPath = os.path.dirname(nuke.EXE_PATH)
    gizmoPath = gizmo.filename()
    installPathSet = set(installPath.split('/'))
    gizmoPathSet = set(gizmoPath.split('/'))
    gizmoPathSet.issubset(installPathSet)
    gizmoIsDefault = os.path.commonprefix([installPath, gizmoPath]) == installPath
    return gizmoIsDefault


def getParent(n):
    '''
    return n's parent node, return nuke.root()n is on the top level
    '''
    return nuke.toNode('.'.join(n.fullName().split('.')[:-1])) or nuke.root()


def bakeGizmo(gizmo):
    '''
    copy gizmo to group and replace it in the tree, so all inputs and outputs use the new group.
    returns the new group node
    '''
    # print "start baking"
    try:
        parent = getParent(gizmo)
    except Exception as e:
        # print e
        # print "Cannot get parent"
        return
    groupName = nuke.tcl(
        'global no_gizmo; set no_gizmo 1; in %s {%s -New} ; return [value [stack 0].name]' % (parent.fullName(), gizmo.Class()))
    group = nuke.toNode('.'.join((parent.fullName(), groupName)))
    group.setSelected(False)
    if getOutputs(gizmo):
        # RECONNECT OUTPUTS IF THERE ARE ANY
        for node, pipes in getOutputs(gizmo).iteritems():
            for i in pipes:
                node.setInput(i, group)
    # RECONNECT INPUTS
    for i in range(gizmo.inputs()):
        group.setInput(i, gizmo.input(i))

    group.setXYpos(gizmo.xpos(), gizmo.ypos())
    # COPY VALUES
    group.readKnobs(gizmo.writeKnobs(nuke.TO_SCRIPT))
    gizmoName = gizmo.name()
    nuke.delete(gizmo)
    group.setName(gizmoName)

    # print "end baking"
    # return group


def bakeGizmos(topLevel=nuke.root(), excludeDefaults=False):
    for n in getAllNodes(topLevel):
        n.setSelected(False)
    gs = []
    for n in getAllNodes(topLevel):
        try:
            if isGizmo(n):
               gs.append(n)
        except Exception as e:
            pass
            # print "x=x=x=x=x Exception", str(e)
    for n in gs:
        name = n['name'].getValue()
        # print "---------| we will be looking at %s |---------" % name
    for n in gs:
        # print "---------| new loop %s|---------"
        name = n['name'].getValue()
        # print "---------| looking at %s |---------" % name

        try:

            if isGizmo(n):
                # if not gizmoIsDefault(n):
                #     # ALWAYS BAKE CUSTOM GIZMOS
                # print "---------| starting bake %s |---------" % name
                bakeGizmo(n)
                # print "---------| finish bake %s |---------" % name

                # elif not excludeDefaults:
                #     # BAKE NON-DEFAULT GIZMOS IF REQUESTED
                    # print "---------| starting bake %s |---------" % name
                #     bakeGizmo(n)
                    # print "---------| finish bake %s |---------" % name
        except Exception as e:
            pass
            # print "x-x-x-x-x Exception", str(e)
            # traceback.print_tb(e.__traceback__)
        # print "---------| end of loop |---------"



main()
