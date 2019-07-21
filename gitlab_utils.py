import re
from gitlab import GitlabGetError


def grep_from_file(project, file_path, revision, regex_pattern):
    try:
        _file = project.files.get(file_path=file_path, ref=revision)
    except GitlabGetError:
        return None

    if _file is None:
        return None
    content = _file.decode()

    matches = re.search(regex_pattern, content)
    if matches is None:
        return None

    return matches.group(1)
