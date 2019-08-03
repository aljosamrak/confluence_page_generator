import re
from gitlab import GitlabGetError


def grep_from_file(project, file_path, revision, regex_pattern):
    content = _get_file(project, file_path, revision)
    if content is None:
        return None

    matches = re.search(regex_pattern, content)
    return None if matches is None else matches.group(1)

cache = dict()

def _get_file(project, file_path, revision):
    key = (project, revision, file_path)
    if key in cache:
        content = cache[key]
    else:
        try:
            _file = project.files.get(file_path=file_path, ref=revision)
        except GitlabGetError:
            return None

        if _file is None:
            return None
        content = _file.decode().decode('utf-8')
        cache[key] = content
    return content