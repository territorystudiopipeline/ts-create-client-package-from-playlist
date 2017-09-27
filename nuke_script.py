import nuke
import os
import re


new_lighting_pass_file_name = "E_%(shot)s_graphics_territory_lgt_%(element)s_%(desc)s_%(pass)s_%(version)s.%04d.%(ext)s"


def main():
    nuke.scriptOpen(get_nuke_script())
    read_paths = get_valid_read_nodes()
    map(localise_read, read_paths)


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
    valid_nodes = []
    all_nodes = get_all_read_nodes()
    for node in all_nodes:
        if is_enabled(node) and matches_expected_pattern(node):
            valid_nodes.append(node)
    return valid_nodes


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
    return "_comp_" in path 


def is_lighting(path):
    return "_lgt_" in path


def is_quicktime(path):
    return ".mov" == os.path.splitext(path)[1]


def is_precomp(path):
    return "_precomp_" in path


def localise_read(read_node):
    path = get_read_node_path(read_node)
    source_files = get_source_files(read_node)
    for source_file in source_files:
        dest_file = get_dest_path(source_file)
        copy_file(source_file, dest_file)
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
    return files


def is_sequence(path):
    pattern = re.compile(".*%\d+d\..*")
    return bool(pattern.match(path))


def get_dest_path(path):
    if is_comp(path):
        sub_path = get_simple_dest_path(path)
    elif is_precomp(path):
        sub_path = get_simple_dest_path(path)
    elif is_ingest(path):
        print path
        sub_path = get_ingest_dest_path(path)
    elif is_lighting(path):
        sub_path = get_lighting_dest_path(path)
    elif is_quicktime(path):
        sub_path = get_quicktime_dest_path(path)


def get_simple_dest_path(path):
    # hrj_0290/work/jason/nuke/renders/comp/hrj_0290_comp_v0004/hrj_0290_comp_v0004.%04d.exr
    # ELEMENTS/hrj_0290_graphics_territory_comp_v0004/hrj_0290_graphics_territory_comp_v0004.%04d.exr
    filename = os.path.basename(path)
    comp_filename = "E_%(shot)s_graphics_territory_%(label)s_%(version)s.%(ext_and_frame)s"
    comp_foldername = "E_%(shot)s_graphics_territory_%(label)s_%(version)s"
    dic = {"shot": get_shot_name(filename),
           "label": get_label(filename),
           "ext_and_frame": get_ext_and_frame(filename),
           "version": get_version_str(filename)}
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
        camelcase[0] = camelcase[0].lower()
    return camelcase


def get_ext_and_frame(path):
    frame = None
    regex = re.compile(".*[._-](\d+)\.[^.]+$", re.IGNORECASE)
    frame_search = re.search(regex, path)
    if len(frame_search.groups()) == 1:
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
    lighting_file_name = "E_%(shot)s_graphics_territory_lgt%(element)s%(desc)s%(pass)s_%(version)s.%(ext_and_frame)s"
    lighting_foldername = "E_%(shot)s_graphics_territory_lgt%(element)s_%(desc)s_%(pass)s_%(version)s"
    dic = {"shot": get_shot_name(filename),
           "label": get_label(filename),
           "ext_and_frame": get_ext_and_frame(filename),
           "element": get_lighting_element(filename),
           "desc": get_lighting_desc(filename),
           "pass": get_lighting_pass(filename),
           "version": get_version_str(filename)}
    new_filename = lighting_file_name % dic
    new_foldername = lighting_foldername % dic
    new_sub_path = os.path.join("ELEMENTS", new_foldername, new_filename)
    return new_sub_path


def get_lighting_element(filename):
    regex = re.compile("[-._]([a-zA-Z0-9]{2,})[-._]v\d+", re.IGNORECASE)
    search = re.search(regex, path)
    if len(search.groups()) == 1:
        s = search.group(1)
        return s


def get_lighting_desc(filename):
    regex = re.compile("[-._]([a-zA-Z0-9]{2,})[-._]v\d+", re.IGNORECASE)
    search = re.search(regex, path)
    if len(search.groups()) == 1:
        s = search.group(1)
        return s


def get_lighting_position(filename):
    regex = re.compile("([lLrRcC])[-._][a-zA-Z0-9]*[-._]?v\d+", re.IGNORECASE)
    search = re.search(regex, path)
    if len(search.groups()) == 1:
        s = search.group(1)
        return s


def get_lighting_pass(filename):
    pass



def get_quicktime_dest_path(path):
    filename = os.path.basename(path)
    new_location = os.path.join("VIDREF", filename)
    return new_location



def copy_file(source, dest):
    print 


main()
